"""The stateful backend an entry runs against.

Multi-turn, agentic, vision, and failing-tools entries execute against live Python
API server instances rather than being scored on a single text response. Everything
describing that execution context lives here.

``ToolEnvironment`` is deliberately a **null object**: a stateless single-turn AST
entry carries ``ToolEnvironment()`` -- empty, never ``None``, never absent. That is
what lets ``TestEntry`` expose zero ``Optional`` fields on its base and lets the
inference loop read ``entry.environment.involved_classes`` without a single
``.get(..., [])``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bfcl_eval.schemas.function_doc import FunctionDoc
from bfcl_eval.schemas.serde import dump_extras, split_known


class HoldoutCondition(str, Enum):
    """When a withheld tool becomes available to the model."""

    # Release once the conversation reaches a given turn index.
    AFTER_N_TURNS = "after_n_turns"
    # Release once a named function has been invoked N times.
    AFTER_N_INVOKE = "after_n_invoke"


@dataclass(slots=True)
class MissedClassRule:
    """A rule that withholds tools and releases them partway through an episode.

    Two on-disk shapes, one concept::

        multi_turn_miss_func: {"condition": "after_n_turns", "value": 3,
                               "holdout_functions": ["sort"]}
        failing_tools:        {"condition": "after_n_invoke", "n": 1,
                               "target_function": "WeatherComAPI.compare_locations",
                               "holdout_classes": ["YahooWeatherAPI"]}

    ``holdout_docs`` is populated by the loader from the per-class function-doc
    files. ``released`` and ``invocations`` are runtime state written during
    inference; neither is serialized back.

    Mutable, because the two runtime fields genuinely change mid-episode.
    """

    condition: HoldoutCondition
    holdout_functions: tuple[str, ...] = ()
    holdout_classes: tuple[str, ...] = ()
    # Wire key ``value``. Turn index for AFTER_N_TURNS.
    turn_index: int | None = None
    # Wire key ``n``. Invocation threshold for AFTER_N_INVOKE.
    invoke_threshold: int | None = None
    target_function: str | None = None

    # Filled by the loader; the docs stripped out of ``entry.functions``.
    holdout_docs: list[FunctionDoc] = field(default_factory=list, repr=False)
    # Runtime state, not on disk.
    released: bool = field(default=False, compare=False)
    invocations: int = field(default=0, compare=False)

    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    _WIRE_KEYS = frozenset(
        {
            "condition",
            "holdout_functions",
            "holdout_classes",
            "value",
            "n",
            "target_function",
            "holdout_func_docs",
        }
    )

    def __post_init__(self) -> None:
        if self.condition is HoldoutCondition.AFTER_N_TURNS:
            if self.turn_index is None:
                raise ValueError("an after_n_turns holdout rule requires 'value'")
        elif self.condition is HoldoutCondition.AFTER_N_INVOKE:
            if self.invoke_threshold is None or self.target_function is None:
                raise ValueError("an after_n_invoke holdout rule requires 'n' and 'target_function'")

    @property
    def holdout_function_names(self) -> list[str]:
        return [doc.name for doc in self.holdout_docs]

    @property
    def bare_target_function(self) -> str | None:
        """``"ClassName.func"`` -> ``"func"``; decoded model calls use bare names."""
        if self.target_function is None:
            return None
        return self.target_function.split(".", 1)[-1]

    @property
    def expects_empty_turn(self) -> bool:
        """``after_n_turns`` entries carry a literal empty turn at the holdout index."""
        return self.condition is HoldoutCondition.AFTER_N_TURNS

    def is_triggered(self, *, turn_index: int) -> bool:
        """Whether this rule fires at the start of ``turn_index``.

        Unifies the two divergent copies of holdout logic in ``base_handler``.
        """
        if self.released:
            return False
        if self.condition is HoldoutCondition.AFTER_N_TURNS:
            return turn_index == self.turn_index
        return False

    def record_invocation(self) -> bool:
        """Count one call of ``target_function``; return True once the threshold is met."""
        if self.released or self.condition is not HoldoutCondition.AFTER_N_INVOKE:
            return False
        self.invocations += 1
        return self.invocations >= (self.invoke_threshold or 0)

    @classmethod
    def from_dict(cls, raw: dict) -> "MissedClassRule":
        known, annotations, extras = split_known(raw, cls._WIRE_KEYS)
        return cls(
            condition=HoldoutCondition(known["condition"]),
            holdout_functions=tuple(known.get("holdout_functions") or ()),
            holdout_classes=tuple(known.get("holdout_classes") or ()),
            turn_index=known.get("value"),
            invoke_threshold=known.get("n"),
            target_function=known.get("target_function"),
            holdout_docs=[FunctionDoc.from_dict(d) for d in known.get("holdout_func_docs") or []],
            extras=dump_extras({}, annotations, extras),
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"condition": self.condition.value}
        if self.holdout_classes:
            out["holdout_classes"] = list(self.holdout_classes)
        if self.invoke_threshold is not None:
            out["n"] = self.invoke_threshold
        if self.target_function is not None:
            out["target_function"] = self.target_function
        if self.turn_index is not None:
            out["value"] = self.turn_index
        if self.holdout_functions:
            out["holdout_functions"] = list(self.holdout_functions)
        if self.holdout_docs:
            # Injected by the loader, not present in the shipped dataset files. Emitted
            # only once populated, so a raw-file round trip stays exact.
            out["holdout_func_docs"] = [doc.to_dict() for doc in self.holdout_docs]
        return dump_extras(out, self.extras)


@dataclass(frozen=True, slots=True)
class FailureInjection:
    """One patch applied to a backend method to simulate a tool failure."""

    method: str  # e.g. "WeatherComAPI.compare_locations"
    patch: str  # e.g. "feature_suspended"

    @property
    def class_name(self) -> str:
        return self.method.split(".", 1)[0]

    @property
    def function_name(self) -> str:
        return self.method.split(".", 1)[-1]

    @classmethod
    def from_dict(cls, raw: dict) -> "FailureInjection":
        return cls(method=raw["method"], patch=raw["patch"])

    def to_dict(self) -> dict:
        return {"method": self.method, "patch": self.patch}


@dataclass(slots=True)
class ToolEnvironment:
    """Backend classes, their starting state, holdout rules, and injected failures.

    ``initial_config`` values stay opaque ``dict``s on purpose: they are per-backend
    state blobs (GorillaFileSystem trees, TwitterAPI stores, ...) whose structure is
    already known to each backend's own ``_load_scenario``. Modeling them here would
    duplicate ~20 classes for no reader.

    On disk, ``failing_tools`` entries express ``initial_config`` values as *path
    strings* pointing into ``server_initial_config_variant/``; the loader resolves
    them to dicts.
    """

    involved_classes: list[str] = field(default_factory=list)
    initial_config: dict[str, Any] = field(default_factory=dict)
    holdout_rules: list[MissedClassRule] = field(default_factory=list)
    failure_injections: list[FailureInjection] = field(default_factory=list)

    @property
    def is_stateful(self) -> bool:
        return bool(self.involved_classes)

    @property
    def primary_class(self) -> str:
        return self.involved_classes[0]

    def pending_holdouts(self) -> list[MissedClassRule]:
        return [rule for rule in self.holdout_rules if not rule.released]
