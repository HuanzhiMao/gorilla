"""Test categories as a value object over a declarative registry.

Category dispatch in BFCL is currently ~30 predicate functions doing substring
matching on category strings, called from roughly 200 sites. That works, but it
encodes three real behaviors as *coincidences* of spelling:

* ``is_agentic("vision_web_search_base")`` is true only because ``"web_search"``
  happens to be a substring. That is how the structured-answer system prompt reaches
  vision entries.
* ``is_true_audio(c)`` is ``"audio" in c``, so it is also true for the
  ``text_audio`` modality -- which is what makes clarification available there.
* The runner if-chain must test ``geoguessr`` before ``agentic`` and
  ``vision_web_search`` before ``web_search``, an ordering nothing records.

This module makes each of those an explicit field on a :class:`CategorySpec` row.
Every field without a default is a decision a new category is *forced* to make.

Behavior is preserved exactly, including the two audio quirks above: every trait here
was checked against the corresponding legacy predicate for every registered category
before the predicates were retired.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from bfcl_eval.constants.enums import Language, Modality
from bfcl_eval.constants.eval_config import (
    MODALITY_DATASET_PATH,
    MODALITY_POSSIBLE_ANSWER_PATH,
)
from bfcl_eval.schemas.ground_truth import GroundTruthKind


class CategoryFamily(str, Enum):
    """What kind of task a category poses."""

    SIMPLE = "simple"
    MULTIPLE = "multiple"
    PARALLEL = "parallel"
    PARALLEL_MULTIPLE = "parallel_multiple"
    IRRELEVANCE = "irrelevance"
    RELEVANCE = "relevance"
    MULTI_TURN = "multi_turn"
    WEB_SEARCH = "web_search"
    MEMORY = "memory"
    MEMORY_PREREQ = "memory_prereq"
    VISION_WEB_SEARCH = "vision_web_search"
    GEOGUESSR = "geoguessr"
    FAILING_TOOLS = "failing_tools"


class StageId(str, Enum):
    """One transform in the dataset-loading pipeline.

    Declaring the sequence per category on :class:`CategorySpec` means "which
    transforms apply to my category?" is answered by reading one row, rather than by
    tracing an if/elif chain inside the loader. Implementations live in
    ``bfcl_eval.dataset_loader.stages``; this enum is the contract between the two.

    Stages before ``PARSE`` operate on raw JSON objects, because they change an
    entry's identity or rebuild it wholesale. Everything after operates on typed
    ``TestEntry`` objects.

    ``ASSIGN_IDS`` is first for every category: ids are the join key between prompts,
    results and ground truth, so nothing else should ever have to reconstruct one.
    """

    # Give every entry its final id: `<modality>:<base_name>_<index>`. Runs first, so
    # every later stage -- and anything that stores an id, such as `depends_on` -- sees
    # the id the entry will keep.
    ASSIGN_IDS = "assign_ids"
    # Expand a memory category into its questions plus the prerequisite
    # write-conversations they depend on.
    MEMORY_PREREQ_LINK = "memory_prereq_link"
    # Rebuild a vision entry around the base64 image its question refers to.
    VISION_ATTACH_IMAGE = "vision_attach_image"
    # Swap transcript text for audio bytes, or for ASR output.
    AUDIO_MATERIALIZE = "audio_materialize"

    # The dict -> TestEntry boundary.
    PARSE = "parse"

    # Replace `initial_config` path strings with the JSON they point at.
    RESOLVE_INITIAL_CONFIG = "resolve_initial_config"
    # Prepend the system prompt asking for a parseable final answer.
    STRUCTURED_ANSWER_PROMPT = "structured_answer_prompt"
    # Materialize the tool list from the entry's backend classes.
    RESOLVE_TOOLS = "resolve_tools"
    # Move withheld tools off the tool list and onto their holdout rules.
    RESOLVE_HOLDOUT_DOCS = "resolve_holdout_docs"
    # Fold Java/JavaScript type information into tool descriptions.
    LANGUAGE_HINT = "language_hint"


class EvalStrategy(str, Enum):
    """Which runner scores a category.

    Replaces the order-sensitive if-chain in ``evaluate_task`` with a dict lookup.
    """

    AST = "ast"
    MULTI_TURN_STATE = "multi_turn_state"
    SUBSTRING_ANSWER = "substring_answer"
    GEO_DISTANCE = "geo_distance"
    RELEVANCE = "relevance"
    FUNC_CALL_CONSTRAINT = "func_call_constraint"


@dataclass(frozen=True, slots=True)
class CategorySpec:
    """One row per base category name.

    ``dataset_file`` / ``ground_truth_file`` are ``None`` when the file is simply
    ``f"{base_name}.json"``; several categories share a single source file and name
    it explicitly.
    """

    base_name: str
    family: CategoryFamily
    eval_strategy: EvalStrategy
    ground_truth_kind: GroundTruthKind
    supported_modalities: frozenset[Modality]
    # This category's loading pipeline, in order.
    load_stages: tuple[StageId, ...] = ()

    language: Language = Language.PYTHON
    is_live: bool = False
    long_context: bool = False
    # Whether the model gets multiple tool-calling steps rather than one shot.
    is_multi_step: bool = False
    # Whether this category's backend returns images from tool calls, as
    # ``StreetViewAPI.capture_view`` does. Distinct from a category whose *question*
    # carries an image: a model can accept image input and still have no way to
    # receive one as a tool result, so the two are gated separately.
    tools_return_images: bool = False
    # Whether the loader prepends the agentic response-format system prompt.
    # True for web_search, memory, geoguessr, and vision_web_search -- the last of
    # which currently gets it only because `is_agentic` matches its name by
    # substring. Making it a field is what stops that being load-bearing spelling.
    requires_structured_answer: bool = False
    # "kv" | "vector" | "rec_sum" for memory categories.
    #
    # Mirrors `extract_memory_backend_type`, which splits on "memory_" and so
    # yields "kv_prereq" for a prereq category. Preserved verbatim because the
    # memory-artifact directory layout depends on it.
    memory_backend: str | None = None
    scoring: bool = True
    dataset_file: str | None = None
    ground_truth_file: str | None = None
    # A category that exists only as an entry-id label, never as something you can
    # ask the loader for. The memory prerequisite conversations are generated as a
    # side effect of loading their parent memory category, so ``bfcl generate
    # --test-category text:memory_kv_prereq`` is not a thing -- but ids like
    # ``text:memory_kv_prereq_22-student-0`` must still resolve to a category.
    is_derived: bool = False

    def dataset_file_name(self) -> str:
        return self.dataset_file or f"{self.base_name}.json"

    def ground_truth_file_name(self) -> str:
        return self.ground_truth_file or f"{self.base_name}.json"


@dataclass(frozen=True, slots=True, order=True)
class TestCategory:
    """A modality-prefixed category, e.g. ``text:multi_turn_miss_func``.

    Parsed once at load time; all downstream dispatch reads the traits below rather
    than re-matching substrings.
    """

    # Not a pytest test class, despite the name.
    __test__ = False

    modality: Modality
    spec: CategorySpec = field(compare=False)

    # ---- construction ----------------------------------------------------

    @classmethod
    def parse(cls, value: str) -> "TestCategory":
        """``"text:simple_python"`` -> ``TestCategory``.

        Replaces ``parse_full_category`` / ``get_base_category`` /
        ``get_category_modality``.

        Strict on purpose, and the only constructor. Every caller is a boundary where a
        name arrives as text -- the ``--test-category`` flag, the evaluator's category
        argument -- and where an unrecognized one is a typo that should be reported
        rather than absorbed. There is deliberately no entry-id overload: an entry
        carries its category as a field (``TestEntry.category``), assigned once at load
        time, so downstream code reads it instead of decoding the id string.
        """
        modality_str, separator, base_name = value.partition(":")
        if not separator:
            raise ValueError(f"{value!r} is not a modality-prefixed category")
        try:
            spec = CATEGORY_SPECS[base_name]
        except KeyError:
            raise ValueError(f"unregistered test category: {value!r}") from None
        modality = Modality(modality_str)
        if modality not in spec.supported_modalities:
            raise ValueError(f"category {base_name!r} is not available in modality {modality_str!r}")
        return cls(modality=modality, spec=spec)

    # ---- identity --------------------------------------------------------

    @property
    def base_name(self) -> str:
        return self.spec.base_name

    @property
    def value(self) -> str:
        return f"{self.modality.value}:{self.spec.base_name}"

    def __str__(self) -> str:
        return self.value

    def with_modality(self, modality: Modality) -> "TestCategory":
        return replace(self, modality=modality)

    # ---- family traits ---------------------------------------------------

    @property
    def is_multi_turn(self) -> bool:
        return self.spec.family is CategoryFamily.MULTI_TURN

    @property
    def is_memory(self) -> bool:
        return self.spec.family in (CategoryFamily.MEMORY, CategoryFamily.MEMORY_PREREQ)

    @property
    def is_memory_prereq(self) -> bool:
        return self.spec.family is CategoryFamily.MEMORY_PREREQ

    @property
    def is_web_search(self) -> bool:
        """Text web search only -- vision web search is a separate family."""
        return self.spec.family is CategoryFamily.WEB_SEARCH

    @property
    def is_vision_web_search(self) -> bool:
        return self.spec.family is CategoryFamily.VISION_WEB_SEARCH

    @property
    def is_geoguessr(self) -> bool:
        return self.spec.family is CategoryFamily.GEOGUESSR

    @property
    def is_geoguessr_type1(self) -> bool:
        """Scored by geodesic distance rather than substring match."""
        return self.spec.eval_strategy is EvalStrategy.GEO_DISTANCE

    @property
    def is_failing_tools(self) -> bool:
        return self.spec.family is CategoryFamily.FAILING_TOOLS

    @property
    def is_relevance_or_irrelevance(self) -> bool:
        return self.spec.family in (CategoryFamily.RELEVANCE, CategoryFamily.IRRELEVANCE)

    @property
    def is_agentic(self) -> bool:
        """Note this includes ``vision_web_search``.

        The legacy predicate is ``"web_search" in c or "memory" in c``, which matches
        vision web search by substring. That is relied upon: it is how those entries
        receive the structured-answer system prompt.
        """
        return self.spec.family in (
            CategoryFamily.WEB_SEARCH,
            CategoryFamily.MEMORY,
            CategoryFamily.MEMORY_PREREQ,
            CategoryFamily.VISION_WEB_SEARCH,
        )

    @property
    def is_live(self) -> bool:
        return self.spec.is_live

    @property
    def is_non_live(self) -> bool:
        return not (self.is_live or self.is_multi_turn or self.is_agentic)

    @property
    def contains_multi_turn_irrelevance(self) -> bool:
        return self.base_name in ("multi_turn_miss_func", "multi_turn_miss_param")

    @property
    def contains_multi_step_interaction(self) -> bool:
        return self.is_multi_turn or self.is_agentic or self.contains_vision_input or self.is_failing_tools

    @property
    def requires_structured_answer(self) -> bool:
        return self.spec.requires_structured_answer

    @property
    def long_context(self) -> bool:
        return self.spec.long_context

    # ---- modality traits -------------------------------------------------

    @property
    def is_vision(self) -> bool:
        return self.is_vision_web_search or self.is_geoguessr

    @property
    def contains_vision_input(self) -> bool:
        return self.is_vision

    @property
    def tools_return_images(self) -> bool:
        """Whether a tool call in this category can come back as an image."""
        return self.spec.tools_return_images

    @property
    def is_true_audio(self) -> bool:
        """Both audio modalities.

        The legacy predicate is ``"audio" in test_category``, which is true for
        ``text_audio`` as well as ``true_audio``. Preserved deliberately: it is what
        enables clarification for both, and narrowing it would change scoring.
        """
        return self.modality in (Modality.TRUE_AUDIO, Modality.TEXT_AUDIO)

    @property
    def is_text_audio(self) -> bool:
        return self.modality is Modality.TEXT_AUDIO

    @property
    def contains_native_audio_input(self) -> bool:
        return self.is_true_audio

    @property
    def allows_clarification(self) -> bool:
        return self.is_true_audio

    @property
    def language(self) -> Language:
        return self.spec.language

    @property
    def is_java(self) -> bool:
        return self.spec.language is Language.JAVA

    @property
    def is_javascript(self) -> bool:
        return self.spec.language is Language.JAVASCRIPT

    @property
    def memory_backend(self) -> str | None:
        return self.spec.memory_backend

    @property
    def prereq_variant(self) -> "TestCategory":
        """The derived ``*_prereq`` category a memory load also yields entries for.

        A registry lookup rather than ``f"{base_name}_prereq"`` built at the call site,
        so a missing pairing fails here instead of labelling entries with a category
        that was never registered.
        """
        if self.spec.family is not CategoryFamily.MEMORY:
            raise ValueError(f"{self.value} has no prerequisite variant")
        return TestCategory(
            modality=self.modality, spec=CATEGORY_SPECS[f"{self.base_name}_prereq"]
        )

    @property
    def is_loadable(self) -> bool:
        """Whether ``load_dataset_entries`` accepts this category directly."""
        return not self.spec.is_derived

    @property
    def load_stages(self) -> tuple[StageId, ...]:
        """The loading pipeline for this (modality, category) pair.

        ``AUDIO_MATERIALIZE`` is a *modality* concern rather than a category one: the
        same base category is delivered as text and as speech, and only the spoken
        form needs its messages turned into audio. It therefore prepends here rather
        than appearing on any spec row -- ahead of ``ASSIGN_IDS``, because it rewrites
        message content and has no interest in ids.
        """
        if self.modality in (Modality.TRUE_AUDIO, Modality.TEXT_AUDIO):
            return (StageId.AUDIO_MATERIALIZE, *self.spec.load_stages)
        return self.spec.load_stages

    # ---- file resolution -------------------------------------------------

    def dataset_path(self) -> Path:
        return MODALITY_DATASET_PATH[self.modality] / self.spec.dataset_file_name()

    def ground_truth_path(self) -> Path | None:
        """``None`` for categories that ship no ground-truth file."""
        if self.spec.ground_truth_kind is GroundTruthKind.NONE:
            return None
        # Audio modalities reuse the text ground-truth files.
        modality = (
            Modality.TEXT
            if self.modality in (Modality.TRUE_AUDIO, Modality.TEXT_AUDIO)
            else self.modality
        )
        return MODALITY_POSSIBLE_ANSWER_PATH[modality] / self.spec.ground_truth_file_name()

    @property
    def ground_truth_kind(self) -> GroundTruthKind:
        return self.spec.ground_truth_kind

    @property
    def eval_strategy(self) -> EvalStrategy:
        return self.spec.eval_strategy


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Every category runs these, in this order, after its own materialization stages.
# Shared rather than repeated per row because they genuinely are universal: each one
# no-ops for the categories it does not apply to.
COMMON_STAGES: tuple[StageId, ...] = (
    StageId.PARSE,
    StageId.RESOLVE_INITIAL_CONFIG,
    StageId.STRUCTURED_ANSWER_PROMPT,
    StageId.RESOLVE_TOOLS,
    StageId.RESOLVE_HOLDOUT_DOCS,
    StageId.LANGUAGE_HINT,
)


def _pipeline(*materialize: StageId) -> tuple[StageId, ...]:
    """``ASSIGN_IDS``, this category's materialization stages, then the common tail.

    ``ASSIGN_IDS`` leads unconditionally: the materialization stages copy ids into
    ``depends_on`` and into rebuilt entries, so they must see final ones.
    """
    return (StageId.ASSIGN_IDS, *materialize, *COMMON_STAGES)


TEXT_ONLY = frozenset({Modality.TEXT})
VISION_ONLY = frozenset({Modality.VISION})
# Single-turn and multi-turn text categories are also delivered as audio.
TEXT_AND_AUDIO = frozenset({Modality.TEXT, Modality.TRUE_AUDIO, Modality.TEXT_AUDIO})


def _ast(
    base_name: str,
    family: CategoryFamily,
    *,
    language: Language = Language.PYTHON,
    is_live: bool = False,
) -> CategorySpec:
    return CategorySpec(
        base_name=base_name,
        family=family,
        eval_strategy=EvalStrategy.AST,
        ground_truth_kind=GroundTruthKind.AST_CALLS,
        supported_modalities=TEXT_AND_AUDIO,
        load_stages=_pipeline(),
        language=language,
        is_live=is_live,
    )


def _relevance(base_name: str, family: CategoryFamily, *, is_live: bool = False) -> CategorySpec:
    """relevance / irrelevance ship no ground-truth file at all."""
    return CategorySpec(
        base_name=base_name,
        family=family,
        eval_strategy=EvalStrategy.RELEVANCE,
        ground_truth_kind=GroundTruthKind.NONE,
        supported_modalities=TEXT_AND_AUDIO,
        load_stages=_pipeline(),
        is_live=is_live,
    )


def _multi_turn(base_name: str, *, long_context: bool = False) -> CategorySpec:
    return CategorySpec(
        base_name=base_name,
        family=CategoryFamily.MULTI_TURN,
        eval_strategy=EvalStrategy.MULTI_TURN_STATE,
        ground_truth_kind=GroundTruthKind.MULTI_TURN_CALLS,
        supported_modalities=TEXT_AND_AUDIO,
        load_stages=_pipeline(),
        long_context=long_context,
        is_multi_step=True,
    )


def _web_search(base_name: str) -> CategorySpec:
    """Both web-search categories draw questions and answers from one shared file.

    Needs no materialization stage of its own: ``ASSIGN_IDS`` already renames the
    shared file's ids after the category reading them.
    """
    return CategorySpec(
        base_name=base_name,
        family=CategoryFamily.WEB_SEARCH,
        eval_strategy=EvalStrategy.SUBSTRING_ANSWER,
        ground_truth_kind=GroundTruthKind.TEXT_ANSWERS,
        supported_modalities=TEXT_ONLY,
        load_stages=_pipeline(),
        is_multi_step=True,
        requires_structured_answer=True,
        dataset_file="web_search.json",
        ground_truth_file="web_search.json",
    )


def _memory(backend: str, *, prereq: bool) -> CategorySpec:
    base_name = f"memory_{backend}_prereq" if prereq else f"memory_{backend}"
    return CategorySpec(
        base_name=base_name,
        family=CategoryFamily.MEMORY_PREREQ if prereq else CategoryFamily.MEMORY,
        eval_strategy=EvalStrategy.SUBSTRING_ANSWER,
        ground_truth_kind=GroundTruthKind.TEXT_ANSWERS,
        supported_modalities=TEXT_ONLY,
        load_stages=_pipeline(StageId.MEMORY_PREREQ_LINK),
        is_multi_step=True,
        # The prerequisite write-conversations are explicitly excluded from the
        # structured-answer prompt: they populate memory, they do not answer anything.
        requires_structured_answer=not prereq,
        # Mirrors extract_memory_backend_type: split on "memory_" keeps the suffix.
        memory_backend=f"{backend}_prereq" if prereq else backend,
        dataset_file="memory.json",
        ground_truth_file="memory.json",
        is_derived=prereq,
    )


def _vision_web_search(base_name: str) -> CategorySpec:
    """All eight image-perturbation variants share one prompt and one answer file."""
    return CategorySpec(
        base_name=base_name,
        family=CategoryFamily.VISION_WEB_SEARCH,
        eval_strategy=EvalStrategy.SUBSTRING_ANSWER,
        ground_truth_kind=GroundTruthKind.TEXT_ANSWERS,
        supported_modalities=VISION_ONLY,
        load_stages=_pipeline(StageId.VISION_ATTACH_IMAGE),
        is_multi_step=True,
        requires_structured_answer=True,
        dataset_file="vision_web_search_base.json",
        ground_truth_file="vision_base.json",
    )


def _geoguessr(base_name: str, *, coordinate: bool) -> CategorySpec:
    return CategorySpec(
        base_name=base_name,
        family=CategoryFamily.GEOGUESSR,
        eval_strategy=EvalStrategy.GEO_DISTANCE if coordinate else EvalStrategy.SUBSTRING_ANSWER,
        ground_truth_kind=(
            GroundTruthKind.COORDINATE if coordinate else GroundTruthKind.TEXT_ANSWERS
        ),
        supported_modalities=VISION_ONLY,
        load_stages=_pipeline(),
        is_multi_step=True,
        # The question is pure text: every image the model sees arrives as the result
        # of a StreetViewAPI call.
        tools_return_images=True,
        requires_structured_answer=True,
    )


_SPEC_LIST: list[CategorySpec] = [
    # ---- text, non-live AST ----
    _ast("simple_python", CategoryFamily.SIMPLE),
    _ast("simple_java", CategoryFamily.SIMPLE, language=Language.JAVA),
    _ast("simple_javascript", CategoryFamily.SIMPLE, language=Language.JAVASCRIPT),
    _ast("multiple", CategoryFamily.MULTIPLE),
    _ast("parallel", CategoryFamily.PARALLEL),
    _ast("parallel_multiple", CategoryFamily.PARALLEL_MULTIPLE),
    _relevance("irrelevance", CategoryFamily.IRRELEVANCE),
    # ---- text, live (user-contributed) ----
    _ast("live_simple", CategoryFamily.SIMPLE, is_live=True),
    _ast("live_multiple", CategoryFamily.MULTIPLE, is_live=True),
    _ast("live_parallel", CategoryFamily.PARALLEL, is_live=True),
    _ast("live_parallel_multiple", CategoryFamily.PARALLEL_MULTIPLE, is_live=True),
    _relevance("live_irrelevance", CategoryFamily.IRRELEVANCE, is_live=True),
    _relevance("live_relevance", CategoryFamily.RELEVANCE, is_live=True),
    # ---- multi-turn ----
    _multi_turn("multi_turn_base"),
    _multi_turn("multi_turn_miss_func"),
    _multi_turn("multi_turn_miss_param"),
    _multi_turn("multi_turn_long_context", long_context=True),
    # ---- agentic: web search ----
    _web_search("web_search_base"),
    _web_search("web_search_no_snippet"),
    # ---- agentic: memory ----
    *[_memory(backend, prereq=False) for backend in ("kv", "vector", "rec_sum")],
    *[_memory(backend, prereq=True) for backend in ("kv", "vector", "rec_sum")],
    # ---- failing tools ----
    CategorySpec(
        base_name="failing_tools",
        family=CategoryFamily.FAILING_TOOLS,
        eval_strategy=EvalStrategy.FUNC_CALL_CONSTRAINT,
        ground_truth_kind=GroundTruthKind.CALL_CONSTRAINTS,
        supported_modalities=TEXT_ONLY,
        load_stages=_pipeline(),
        is_multi_step=True,
    ),
    # ---- vision ----
    *[
        _vision_web_search(f"vision_web_search_{variant}")
        for variant in (
            "base",
            "crop_169",
            "crop_43",
            "resize_169",
            "resize_43",
            "bw",
            "edge",
            "rg",
        )
    ],
    _geoguessr("geoguessr_type1", coordinate=True),
    _geoguessr("geoguessr_type1_competition", coordinate=True),
    _geoguessr("geoguessr_type2", coordinate=False),
    _geoguessr("geoguessr_type3", coordinate=False),
]

# base category name -> spec. The single source of truth for category behavior.
CATEGORY_SPECS: dict[str, CategorySpec] = {spec.base_name: spec for spec in _SPEC_LIST}

assert len(CATEGORY_SPECS) == len(_SPEC_LIST), "duplicate base_name in the category registry"


def all_categories() -> list[TestCategory]:
    """Every registered (modality, base category) pair, sorted by name."""
    return sorted(
        (
            TestCategory(modality=modality, spec=spec)
            for spec in _SPEC_LIST
            for modality in spec.supported_modalities
        ),
        key=lambda category: category.value,
    )
