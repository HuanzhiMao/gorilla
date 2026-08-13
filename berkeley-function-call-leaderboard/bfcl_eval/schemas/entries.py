"""Test entries -- one class per shape a dataset entry actually takes.

The base carries six **total** fields. There are no ``Optional`` fields on it: a
stateless AST entry gets an empty :class:`~bfcl_eval.schemas.environment.ToolEnvironment`
and an empty ``depends_on`` rather than ``None``. That is what lets the inference
loop and the twenty-odd provider handlers stay generic -- they read
``entry.functions`` and ``entry.environment.involved_classes`` with no ``.get()``
and no ``isinstance``.

Category-specific payload lives on subclasses, and there are only a handful of such
fields because most of the apparent heterogeneity is really the presence or absence
of a tool environment. Consumers should dispatch in this order:

1. base accessors -- the overwhelming majority of call sites;
2. ``entry.category.<trait>`` -- anything that varies by category;
3. ``match entry: case MemoryTestEntry(...)`` -- only where a subclass-only field is
   actually read.

Entries are **mutable**. The pipeline rewrites them during inference (holdout
release, memory system-prompt injection, backend tool refresh, provider-specific
turn rewriting), and they are already deep-copied per model. What the model buys is
not immutability but that every mutation has a name -- ``entry.release_holdout(rule)``
replaces an ``extend`` and a flag assignment three lines apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from bfcl_eval.constants.enums import Modality
from bfcl_eval.schemas.category import CategoryFamily, TestCategory
from bfcl_eval.schemas.environment import (
    FailureInjection,
    MissedClassRule,
    ToolEnvironment,
)
from bfcl_eval.schemas.function_doc import FunctionDoc
from bfcl_eval.schemas.message import Conversation, Message, Turn
from bfcl_eval.schemas.serde import dump_extras, split_known

# Wire keys the base class and the shared tool environment own.
_BASE_WIRE_KEYS = frozenset(
    {
        "id",
        "question",
        "function",
        "involved_classes",
        "initial_config",
        "missed_classes",
        "failure_injection",
        "depends_on",
    }
)

# Loader-internal key, not a wire key. A pre-parse stage sets it on the raw dict when
# an entry belongs to a *different* category than the one being loaded: one memory load
# yields both the ``memory_kv`` questions and the ``memory_kv_prereq`` conversations
# they depend on, and only the stage that pulls those two lists together knows which is
# which. Passing a ``TestCategory`` forward is what removes the need to recover it by
# re-splitting the entry id downstream.
#
# ``parse_test_entry`` pops it before ``split_known`` runs, so it can never reach
# ``extras`` and can never round-trip back out to disk.
CATEGORY_STAMP = "__category__"


@dataclass(kw_only=True)
class TestEntry:
    """One test case, in whatever shape its category takes."""

    # Not a pytest test class, despite the name.
    __test__ = False

    id: str
    category: TestCategory
    conversation: Conversation
    functions: list[FunctionDoc] = field(default_factory=list)
    environment: ToolEnvironment = field(default_factory=ToolEnvironment)
    depends_on: list[str] = field(default_factory=list)

    # ``_``-prefixed dataset authoring metadata (``_comment``, ``_source``, ...).
    annotations: dict[str, Any] = field(default_factory=dict, repr=False)
    # Keys present on disk that nothing reads (``path``, ``excluded_function``) and
    # anything a future dataset drop adds before the model catches up.
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    # Which optional wire keys the source object carried. Needed because absence and
    # emptiness are different: a memory prereq entry has ``"depends_on": []``, and a
    # round trip must not silently drop it.
    present_keys: frozenset[str] = field(default_factory=frozenset, repr=False, compare=False)

    # ---- ergonomics ------------------------------------------------------

    @property
    def base_category(self) -> str:
        return self.category.base_name

    @property
    def modality(self) -> Modality:
        return self.category.modality

    @property
    def num_turns(self) -> int:
        return len(self.conversation)

    @property
    def first_turn(self) -> Turn:
        return self.conversation.first_turn

    @property
    def is_multi_turn(self) -> bool:
        return self.category.is_multi_turn

    def iter_messages(self) -> Iterator[tuple[int, int, Message]]:
        return self.conversation.iter_messages()

    def function_named(self, name: str) -> FunctionDoc | None:
        return next((doc for doc in self.functions if doc.name == name), None)

    # ---- named mutations -------------------------------------------------

    def release_holdout(self, rule: MissedClassRule) -> list[FunctionDoc]:
        """Make a withheld tool group available and mark the rule spent.

        One atomic operation, replacing an ``entry["function"].extend(...)`` and a
        separate ``rule["_released"] = True`` that had to be kept in sync by hand.
        """
        self.functions.extend(rule.holdout_docs)
        rule.released = True
        return rule.holdout_docs

    def replace_backend_tools(self, docs: list[FunctionDoc], replaced_names: set[str]) -> None:
        """Swap in a refreshed tool list for one backend, mid-episode."""
        self.functions = [doc for doc in self.functions if doc.name not in replaced_names]
        self.functions.extend(docs)

    # ---- serialization ---------------------------------------------------

    def _emits(self, key: str, value: Any) -> bool:
        """Emit a modeled optional key if the source had it, or if it is non-empty."""
        return key in self.present_keys or bool(value)

    def _specific_to_dict(self) -> dict:
        """Subclass hook: the wire keys only this subclass owns."""
        return {}

    def to_dict(self, *, redact_binary: bool = False) -> dict:
        environment = self.environment
        out: dict[str, Any] = {"id": self.id}
        out.update(self._specific_to_dict())
        out["question"] = self.conversation.to_list(redact_binary=redact_binary)

        if self._emits("involved_classes", environment.involved_classes):
            out["involved_classes"] = environment.involved_classes
        if self._emits("initial_config", environment.initial_config):
            out["initial_config"] = environment.initial_config
        if self._emits("failure_injection", environment.failure_injections):
            out["failure_injection"] = [f.to_dict() for f in environment.failure_injections]
        if self._emits("missed_classes", environment.holdout_rules):
            out["missed_classes"] = [rule.to_dict() for rule in environment.holdout_rules]
        if self._emits("depends_on", self.depends_on):
            out["depends_on"] = self.depends_on
        if self._emits("function", self.functions):
            out["function"] = [doc.to_dict() for doc in self.functions]

        return dump_extras(out, self.annotations, self.extras)


@dataclass(kw_only=True)
class AstTestEntry(TestEntry):
    """Single-turn categories scored by comparing the parsed call to an expectation.

    Covers simple / multiple / parallel / parallel_multiple / live_* and the
    relevance and irrelevance categories, which share the same ``{id, question,
    function}`` shape and differ only in having no ground truth.

    Every entry in these categories has exactly one turn; the corpus invariant test
    checks that rather than a constructor assertion, so a malformed future entry
    fails a test run instead of crashing a benchmark run.
    """

    @property
    def prompt_turn(self) -> Turn:
        return self.conversation[0]


@dataclass(kw_only=True)
class MultiTurnTestEntry(TestEntry):
    """multi_turn_base / _miss_func / _miss_param / _long_context."""

    @property
    def long_context(self) -> bool:
        return self.category.long_context

    @property
    def holdout_turn_indices(self) -> list[int]:
        """Turns left empty because a tool is withheld until that point."""
        return self.conversation.empty_turn_indices()


@dataclass(kw_only=True)
class FreeTextAnswerTestEntry(TestEntry):
    """Scored on the final answer rather than on the calls that produced it.

    The base for every category whose deliverable is a natural-language answer the
    model reaches by working a tool backend over several steps: web_search, geoguessr,
    memory, vision_web_search. Contrast :class:`AstTestEntry` (scored on the emitted
    call), :class:`MultiTurnTestEntry` (scored on resulting backend state) and
    :class:`FailingToolsTestEntry` (scored on call constraints).

    web_search and geoguessr use it directly, because neither adds a wire key and a
    subclass per family would carry no information. That is a claim about entry
    *shape* alone. The two remain different families and diverge elsewhere -- most
    visibly in ``TestCategory.is_agentic``, which covers web_search but not geoguessr.

    Named for the shape and not the task for exactly that reason: as
    ``AgenticTestEntry`` it read as the class-level spelling of ``is_agentic`` while
    holding a different set of categories.
    """


@dataclass(kw_only=True)
class MemoryTestEntry(FreeTextAnswerTestEntry):
    """memory_kv / memory_vector / memory_rec_sum."""

    scenario: str | None = None

    @property
    def backend(self) -> str | None:
        return self.category.memory_backend

    def _specific_to_dict(self) -> dict:
        return {} if self.scenario is None else {"scenario": self.scenario}


@dataclass(kw_only=True)
class MemoryPrereqTestEntry(MemoryTestEntry):
    """A memory-write conversation that must run before its dependent entries.

    Carries ``topic`` in addition to ``scenario``, and is the reason ``depends_on``
    must distinguish "absent" from "present but empty": the first prereq entry in a
    chain legitimately depends on nothing.
    """

    topic: str | None = None

    def _specific_to_dict(self) -> dict:
        out: dict[str, Any] = {}
        if self.topic is not None:
            out["topic"] = self.topic
        out.update(super()._specific_to_dict())
        return out


@dataclass(kw_only=True)
class VisionTestEntry(FreeTextAnswerTestEntry):
    """vision_web_search_*.

    ``image_file_name`` and ``img_source`` exist on disk but are consumed by the
    loader, which rebuilds the entry around a base64 image attached to the user
    message. Both are therefore optional here: a freshly parsed entry has them, a
    post-load entry does not.
    """

    image_file_name: str | None = None
    img_source: str | None = None

    @property
    def image(self):
        """The single attached image, once the loader has resolved it."""
        return self.conversation[0][0].images[0]

    def _specific_to_dict(self) -> dict:
        out: dict[str, Any] = {}
        if self.image_file_name is not None:
            out["image_file_name"] = self.image_file_name
        if self.img_source is not None:
            out["img_source"] = self.img_source
        return out


@dataclass(kw_only=True)
class FailingToolsTestEntry(TestEntry):
    """Error-recovery scenarios: a tool is patched to fail and the model must adapt.

    Note ``scenario_category``: these entries carry a top-level ``"category"`` key
    holding a domain label like ``"Weather"``, which is *not* a BFCL test category.
    Renaming it at the boundary is exactly the kind of collision an untyped dict
    hides -- ``entry["category"]`` in a generic helper would quietly return
    ``"Weather"``.
    """

    scenario_category: str | None = None

    def _specific_to_dict(self) -> dict:
        return {} if self.scenario_category is None else {"category": self.scenario_category}


# Extra wire keys owned by each subclass, beyond the base set.
_SUBCLASS_WIRE_KEYS: dict[type[TestEntry], frozenset[str]] = {
    AstTestEntry: frozenset(),
    MultiTurnTestEntry: frozenset(),
    FreeTextAnswerTestEntry: frozenset(),
    MemoryTestEntry: frozenset({"scenario"}),
    MemoryPrereqTestEntry: frozenset({"scenario", "topic"}),
    VisionTestEntry: frozenset({"image_file_name", "img_source"}),
    FailingToolsTestEntry: frozenset({"category"}),
}


def entry_class_for(category: TestCategory) -> type[TestEntry]:
    """Pick the entry class for one entry, given the category *that entry* belongs to.

    A memory category's file yields both the questions and the prerequisite
    write-conversations that must run first, and those have a different shape -- so the
    argument is the per-entry category rather than the one being loaded. It arrives via
    :data:`CATEGORY_STAMP`, which is why this needs no entry id to inspect.

    Every family is listed, and there is no fall-through: a family added to the
    registry without a shape raises here rather than silently parsing as an
    :class:`AstTestEntry` and losing whatever wire keys it carries. Because the arms
    are disjoint, none of this depends on the order they are written in -- which the
    ``is_memory_prereq``-before-``is_memory`` if-chain this replaced did.
    ``test_entry_class_covers_every_family`` pins the totality.
    """
    match category.spec.family:
        case CategoryFamily.MEMORY_PREREQ:
            return MemoryPrereqTestEntry
        case CategoryFamily.MEMORY:
            return MemoryTestEntry
        case CategoryFamily.MULTI_TURN:
            return MultiTurnTestEntry
        case CategoryFamily.FAILING_TOOLS:
            return FailingToolsTestEntry
        case CategoryFamily.VISION_WEB_SEARCH:
            return VisionTestEntry
        # One shape, two families: neither adds a wire key. See
        # `FreeTextAnswerTestEntry` on why that is not the same set as `is_agentic`.
        case CategoryFamily.WEB_SEARCH | CategoryFamily.GEOGUESSR:
            return FreeTextAnswerTestEntry
        case (
            CategoryFamily.SIMPLE
            | CategoryFamily.MULTIPLE
            | CategoryFamily.PARALLEL
            | CategoryFamily.PARALLEL_MULTIPLE
            | CategoryFamily.RELEVANCE
            | CategoryFamily.IRRELEVANCE
        ):
            return AstTestEntry

    # Unreachable while the match above is exhaustive -- which is the point: a type
    # checker flags this line as dead today and stops doing so the moment a family is
    # added without an arm, at which point the raise is what fires at run time.
    raise ValueError(f"no entry class registered for family {category.spec.family}")


def parse_test_entry(raw: dict, category: TestCategory) -> TestEntry:
    """Build a typed entry from one raw JSON object.

    ``category`` is the category being loaded, and is what an entry belongs to unless a
    pre-parse stage stamped it otherwise -- see :data:`CATEGORY_STAMP`. This is the one
    point where an entry's category is decided; from here on it is a field, and no
    consumer should re-derive it from the id.
    """
    entry_id = raw["id"]
    entry_category = raw.pop(CATEGORY_STAMP, None) or category
    cls = entry_class_for(entry_category)
    wire_keys = _BASE_WIRE_KEYS | _SUBCLASS_WIRE_KEYS[cls]

    known, annotations, extras = split_known(raw, wire_keys)

    environment = ToolEnvironment(
        involved_classes=known.get("involved_classes", []),
        initial_config=known.get("initial_config", {}),
        holdout_rules=[MissedClassRule.from_dict(r) for r in known.get("missed_classes") or []],
        failure_injections=[
            FailureInjection.from_dict(f) for f in known.get("failure_injection") or []
        ],
    )

    common: dict[str, Any] = {
        "id": entry_id,
        "category": entry_category,
        "conversation": Conversation.from_list(known["question"]),
        "functions": [FunctionDoc.from_dict(f) for f in known.get("function") or []],
        "environment": environment,
        "depends_on": known.get("depends_on", []),
        "annotations": annotations,
        "extras": extras,
        "present_keys": frozenset(known) & wire_keys,
    }

    if cls is MemoryPrereqTestEntry:
        return cls(**common, scenario=known.get("scenario"), topic=known.get("topic"))
    if cls is MemoryTestEntry:
        return cls(**common, scenario=known.get("scenario"))
    if cls is VisionTestEntry:
        return cls(
            **common,
            image_file_name=known.get("image_file_name"),
            img_source=known.get("img_source"),
        )
    if cls is FailingToolsTestEntry:
        return cls(**common, scenario_category=known.get("category"))
    return cls(**common)
