"""Ground-truth ("possible answer") entries.

The ``ground_truth`` field is a **tagged union with no tag** on disk: its shape is
decided entirely by which category the file belongs to. Five distinct payload shapes
exist, plus a sixth "there is no ground-truth file at all" case:

===========================  ====================================================
Kind                         Payload
===========================  ====================================================
``AST_CALLS``                ``list[dict]``, each with exactly one ``{name: params}``
``MULTI_TURN_CALLS``         ``list[list[str]]`` -- turn -> executable call strings
``TEXT_ANSWERS``             ``list[str]`` -- any one is an acceptable answer
``COORDINATE``               ``list[str]`` of exactly one ``"lat, lng"``
``CALL_CONSTRAINTS``         ``dict`` of must/must-not-call specs plus rubrics
``NONE``                     no file (relevance / irrelevance)
===========================  ====================================================

Ground truth is **frozen**: eval code has no business mutating expectations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from bfcl_eval.schemas.serde import dump_extras, split_known

# A parameter whose acceptable-value list contains this sentinel may be omitted
# from the model's call entirely.
OMITTED = ""


class GroundTruthKind(str, Enum):
    """Which ground-truth payload shape a category uses."""

    AST_CALLS = "ast_calls"
    MULTI_TURN_CALLS = "multi_turn_calls"
    TEXT_ANSWERS = "text_answers"
    COORDINATE = "coordinate"
    CALL_CONSTRAINTS = "call_constraints"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ExpectedFunctionCall:
    """One AST-checker expectation: a function name plus per-parameter alternatives.

    On disk this is a dict with **exactly one** key::

        {"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}

    That single-key invariant is currently assumed, unchecked, by three separate
    ``list(possible_answer.values())[0]`` / ``list(...keys())[0]`` unwraps in the AST
    checker. Tuple-unpacking in ``from_dict`` turns the assumption into an enforced
    one at zero cost.
    """

    name: str
    # parameter name -> list of acceptable values.
    params: Mapping[str, list[Any]]

    @property
    def param_names(self) -> frozenset[str]:
        return frozenset(self.params)

    def accepted_values(self, param: str) -> list[Any]:
        """Acceptable values for ``param``, **including** the ``""`` sentinel.

        Returned verbatim because the checker's current handling of ``""`` is
        load-bearing for scoring; see :func:`is_omittable` for the semantic view.
        """
        return self.params[param]

    def is_omittable(self, param: str) -> bool:
        """Whether ``param`` may be absent from the model's call.

        Note the corpus conflates "may be omitted" with "the empty string is an
        acceptable value". Disambiguating that changes scores, so nothing in the
        checker uses this yet.
        """
        return OMITTED in self.params.get(param, ())

    @classmethod
    def from_dict(cls, raw: dict) -> "ExpectedFunctionCall":
        try:
            ((name, params),) = raw.items()
        except ValueError:
            raise ValueError(
                f"an AST ground-truth call must have exactly one function key, got {sorted(raw)}"
            ) from None
        return cls(name=name, params=MappingProxyType(dict(params)))

    def to_dict(self) -> dict:
        return {self.name: dict(self.params)}


@dataclass(frozen=True, slots=True)
class ResponseRubric:
    """One scoring checkpoint for a ``failing_tools`` entry.

    Present in the dataset but not yet read by any checker; modeled so it survives a
    round trip and so the follow-up that consumes it has a type to consume.
    """

    checkpoint_id: str | None = None
    weight: Any = None
    check_condition: dict[str, Any] | None = None
    expected_response: tuple[str, ...] = ()
    extras: dict[str, Any] = field(default_factory=dict, repr=False)
    annotations: dict[str, Any] = field(default_factory=dict, repr=False)

    _WIRE_KEYS = frozenset({"checkpoint_id", "weight", "check_condition", "expected_response"})

    @classmethod
    def from_dict(cls, raw: dict) -> "ResponseRubric":
        known, annotations, extras = split_known(raw, cls._WIRE_KEYS)
        expected = known.get("expected_response")
        return cls(
            checkpoint_id=known.get("checkpoint_id"),
            weight=known.get("weight"),
            check_condition=known.get("check_condition"),
            expected_response=tuple(expected) if expected is not None else (),
            extras=extras,
            annotations=annotations,
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {}
        if self.checkpoint_id is not None:
            out["checkpoint_id"] = self.checkpoint_id
        if self.weight is not None:
            out["weight"] = self.weight
        if self.check_condition is not None:
            out["check_condition"] = self.check_condition
        if self.expected_response:
            out["expected_response"] = list(self.expected_response)
        return dump_extras(out, self.annotations, self.extras)


@dataclass(frozen=True, kw_only=True)
class GroundTruth:
    """Base class. Subclasses add exactly one typed payload."""

    id: str | None = None
    annotations: dict[str, Any] = field(default_factory=dict, repr=False)
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    # Wire keys owned by the base; subclasses extend this.
    _WIRE_KEYS = frozenset({"id", "ground_truth"})

    # The kind this class implements. Set on every concrete subclass.
    KIND: GroundTruthKind = GroundTruthKind.NONE

    def _payload_to_json(self) -> Any:
        raise NotImplementedError

    @property
    def payload(self) -> Any:
        """The ``ground_truth`` value as it appears on disk.

        Score files embed the raw expectation next to the failing model output, so
        the evaluator needs the JSON form even once it works with typed objects.
        """
        return self._payload_to_json()

    def _extra_wire_fields(self) -> dict:
        """Category-specific sibling keys that live next to ``ground_truth``."""
        return {}

    def to_dict(self) -> dict:
        out: dict[str, Any] = {}
        if self.id is not None:
            out["id"] = self.id
        out["ground_truth"] = self._payload_to_json()
        out.update(self._extra_wire_fields())
        return dump_extras(out, self.annotations, self.extras)


@dataclass(frozen=True, kw_only=True)
class AstGroundTruth(GroundTruth):
    """simple_* / multiple / parallel / parallel_multiple / live_*."""

    KIND = GroundTruthKind.AST_CALLS

    calls: tuple[ExpectedFunctionCall, ...] = ()

    @property
    def only(self) -> ExpectedFunctionCall:
        """The single expected call, for the simple/multiple categories."""
        return self.calls[0]

    def _payload_to_json(self) -> Any:
        return [call.to_dict() for call in self.calls]


@dataclass(frozen=True, kw_only=True)
class MultiTurnGroundTruth(GroundTruth):
    """multi_turn_*. ``turns[i]`` holds the executable call strings for turn ``i``.

    An empty inner list marks a turn the model is expected to refuse -- the holdout
    turn in ``multi_turn_miss_func``.
    """

    KIND = GroundTruthKind.MULTI_TURN_CALLS

    turns: tuple[tuple[str, ...], ...] = ()

    def turn(self, index: int) -> tuple[str, ...]:
        return self.turns[index]

    def holdout_turn_indices(self) -> tuple[int, ...]:
        return tuple(i for i, turn in enumerate(self.turns) if not turn)

    def _payload_to_json(self) -> Any:
        return [list(turn) for turn in self.turns]


@dataclass(frozen=True, kw_only=True)
class TextAnswerGroundTruth(GroundTruth):
    """web_search / memory / geoguessr type2-3 / vision_web_search.

    Any one of ``answers`` counts as correct.
    """

    KIND = GroundTruthKind.TEXT_ANSWERS

    answers: tuple[str, ...] = ()
    # Provenance, unused by scoring but round-tripped.
    # ``str`` for memory, ``list[dict]`` for web_search.
    source: Any = None
    num_hops: int | None = None
    ground_truth_source: str | None = None
    reasoning: tuple[str, ...] | None = None

    _WIRE_KEYS = frozenset(
        {"id", "ground_truth", "source", "num_hops", "ground_truth_source", "reasoning"}
    )

    def _payload_to_json(self) -> Any:
        return list(self.answers)

    def _extra_wire_fields(self) -> dict:
        out: dict[str, Any] = {}
        if self.source is not None:
            out["source"] = self.source
        if self.num_hops is not None:
            out["num_hops"] = self.num_hops
        if self.ground_truth_source is not None:
            out["ground_truth_source"] = self.ground_truth_source
        if self.reasoning is not None:
            out["reasoning"] = list(self.reasoning)
        return out


@dataclass(frozen=True, kw_only=True)
class CoordinateGroundTruth(TextAnswerGroundTruth):
    """geoguessr_type1 / type1_competition: exactly one ``"lat, lng"`` string.

    The wire shape is identical to :class:`TextAnswerGroundTruth`; the difference is
    that these are scored by geodesic distance rather than substring match.
    """

    KIND = GroundTruthKind.COORDINATE

    @property
    def coordinate(self) -> tuple[float, float]:
        (only,) = self.answers
        latitude, longitude = (float(part) for part in only.split(","))
        return latitude, longitude


@dataclass(frozen=True, kw_only=True)
class CallConstraintGroundTruth(GroundTruth):
    """failing_tools -- the only category whose ``ground_truth`` is a dict.

    Each spec string is either ``"Class.method"`` or ``"Class.method(arg=value)"``.
    The outer list is a disjunction of acceptable call sequences.
    """

    KIND = GroundTruthKind.CALL_CONSTRAINTS

    must_be_called: tuple[tuple[str, ...], ...] = ()
    must_not_be_called: tuple[tuple[str, ...], ...] = ()
    rubrics: tuple[ResponseRubric, ...] = ()
    # Any payload keys we do not model, so the dict round-trips exactly.
    payload_extras: dict[str, Any] = field(default_factory=dict, repr=False)

    def _payload_to_json(self) -> Any:
        out: dict[str, Any] = {
            "must_be_called_functions": [list(group) for group in self.must_be_called],
            "must_not_be_called_functions": [list(group) for group in self.must_not_be_called],
        }
        if self.rubrics:
            out["response_rubrics"] = [rubric.to_dict() for rubric in self.rubrics]
        return dump_extras(out, self.payload_extras)


@dataclass(frozen=True, kw_only=True)
class NoGroundTruth(GroundTruth):
    """relevance / irrelevance: there is no ground-truth file for these categories.

    A null object so callers need no ``ground_truth is None`` special case.
    """

    KIND = GroundTruthKind.NONE

    def _payload_to_json(self) -> Any:  # pragma: no cover - never serialized
        raise TypeError("relevance/irrelevance categories have no ground truth to serialize")

    def to_dict(self) -> dict:  # pragma: no cover - never serialized
        raise TypeError("relevance/irrelevance categories have no ground truth to serialize")


GROUND_TRUTH_CLASSES: dict[GroundTruthKind, type[GroundTruth]] = {
    GroundTruthKind.AST_CALLS: AstGroundTruth,
    GroundTruthKind.MULTI_TURN_CALLS: MultiTurnGroundTruth,
    GroundTruthKind.TEXT_ANSWERS: TextAnswerGroundTruth,
    GroundTruthKind.COORDINATE: CoordinateGroundTruth,
    GroundTruthKind.CALL_CONSTRAINTS: CallConstraintGroundTruth,
    GroundTruthKind.NONE: NoGroundTruth,
}


def parse_ground_truth(raw: dict, kind: GroundTruthKind) -> GroundTruth:
    """Build the ground-truth object for ``kind`` from one raw JSON object."""
    cls = GROUND_TRUTH_CLASSES[kind]
    known, annotations, extras = split_known(raw, cls._WIRE_KEYS)
    payload = known.get("ground_truth")
    common = {"id": known.get("id"), "annotations": annotations, "extras": extras}

    if kind is GroundTruthKind.NONE:
        return NoGroundTruth(**common)

    if kind is GroundTruthKind.AST_CALLS:
        return AstGroundTruth(
            **common, calls=tuple(ExpectedFunctionCall.from_dict(d) for d in payload)
        )

    if kind is GroundTruthKind.MULTI_TURN_CALLS:
        return MultiTurnGroundTruth(**common, turns=tuple(tuple(turn) for turn in payload))

    if kind is GroundTruthKind.CALL_CONSTRAINTS:
        modeled = {"must_be_called_functions", "must_not_be_called_functions", "response_rubrics"}
        return CallConstraintGroundTruth(
            **common,
            must_be_called=tuple(
                tuple(group) for group in payload.get("must_be_called_functions", [])
            ),
            must_not_be_called=tuple(
                tuple(group) for group in payload.get("must_not_be_called_functions", [])
            ),
            rubrics=tuple(
                ResponseRubric.from_dict(r) for r in payload.get("response_rubrics", []) or []
            ),
            payload_extras={k: v for k, v in payload.items() if k not in modeled},
        )

    # TEXT_ANSWERS and COORDINATE share a wire shape.
    reasoning = known.get("reasoning")
    return cls(
        **common,
        answers=tuple(payload),
        source=known.get("source"),
        num_hops=known.get("num_hops"),
        ground_truth_source=known.get("ground_truth_source"),
        reasoning=tuple(reasoning) if reasoning is not None else None,
    )
