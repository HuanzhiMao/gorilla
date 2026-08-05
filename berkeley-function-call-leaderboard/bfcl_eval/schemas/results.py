"""Generated artifacts: model result files and score files.

Two families of JSONL file are produced by a run and read back by later stages:

``result/<model>/<modality>/<category>_result.json``
    One :class:`ModelResultEntry` per line. Written by the handler, read back by the
    resume path (to skip already-generated ids) and by the evaluator.

``score/<model>/<modality>/<category>_score.json``
    Line 0 is a :class:`ScoreHeader`; lines 1..n are :class:`ScoreRecord` rows for
    *failing* entries only. The header is the sole input to the leaderboard CSV.

Both are modeled here for the same reason as the dataset: the shapes are implicit,
differ per category, and are indexed by string key at a dozen call sites. Note the
per-entry score rows are genuinely heterogeneous today -- each of the six runners
builds a slightly different dict -- so :class:`ScoreRecord` keeps a permissive
``details`` bucket rather than pretending a single shape exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bfcl_eval.schemas.serde import dump_extras, split_known

# Token counts and latency are a scalar for single-turn categories and a
# list-of-lists (turn -> step) for multi-step ones. Both shapes are flattened by
# the cost/latency aggregator.
TokenCount = "int | float | list[list[int | float]] | None"


@dataclass(slots=True)
class ModelResultEntry:
    """One line of a ``*_result.json`` file.

    ``result`` is whatever the handler produced: a string or list of decoded calls
    for single-turn categories, a list-of-lists for multi-step ones. It is passed
    straight to the checker, so it stays untyped here on purpose.
    """

    id: str
    result: Any = None
    input_token_count: Any = None
    output_token_count: Any = None
    latency: Any = None
    # Present for multi-step categories, or whenever ``--include-input-log`` is set.
    inference_log: Any = None
    # Present only when the model emitted a non-empty reasoning trace.
    reasoning_content: Any = None
    # Present instead of real metadata when inference raised.
    traceback: str | None = None
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    _WIRE_KEYS = frozenset(
        {
            "id",
            "result",
            "input_token_count",
            "output_token_count",
            "latency",
            "inference_log",
            "reasoning_content",
            "traceback",
        }
    )

    @property
    def failed(self) -> bool:
        return self.traceback is not None

    @classmethod
    def from_dict(cls, raw: dict) -> "ModelResultEntry":
        known, annotations, extras = split_known(raw, cls._WIRE_KEYS)
        return cls(
            id=known["id"],
            result=known.get("result"),
            input_token_count=known.get("input_token_count"),
            output_token_count=known.get("output_token_count"),
            latency=known.get("latency"),
            inference_log=known.get("inference_log"),
            reasoning_content=known.get("reasoning_content"),
            traceback=known.get("traceback"),
            extras=dump_extras({}, annotations, extras),
        )

    @classmethod
    def from_inference(cls, entry_id: str, result: Any, metadata: dict) -> "ModelResultEntry":
        """Build from a handler's ``(result, metadata)`` return value."""
        return cls.from_dict({"id": entry_id, "result": result, **metadata})

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"id": self.id, "result": self.result}
        for name in (
            "input_token_count",
            "output_token_count",
            "latency",
            "inference_log",
            "reasoning_content",
            "traceback",
        ):
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        return dump_extras(out, self.extras)


@dataclass(slots=True)
class ScoreHeader:
    """Line 0 of a ``*_score.json`` file, and the only line the leaderboard reads."""

    accuracy: float
    correct_count: int
    total_count: int
    # geoguessr type1 reports distribution stats alongside the mean score.
    score_variance: float | None = None
    score_std: float | None = None
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    _WIRE_KEYS = frozenset(
        {"accuracy", "correct_count", "total_count", "score_variance", "score_std"}
    )

    @classmethod
    def from_dict(cls, raw: dict) -> "ScoreHeader":
        known, annotations, extras = split_known(raw, cls._WIRE_KEYS)
        return cls(
            accuracy=known["accuracy"],
            correct_count=known["correct_count"],
            total_count=known["total_count"],
            score_variance=known.get("score_variance"),
            score_std=known.get("score_std"),
            extras=dump_extras({}, annotations, extras),
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "accuracy": self.accuracy,
            "correct_count": self.correct_count,
            "total_count": self.total_count,
        }
        if self.score_variance is not None:
            out["score_variance"] = self.score_variance
        if self.score_std is not None:
            out["score_std"] = self.score_std
        return dump_extras(out, self.extras)


@dataclass(slots=True)
class ScoreRecord:
    """One failing-entry row of a ``*_score.json`` file.

    The six runners each emit a different key set today (``error`` vs
    ``error_message``, nested checker dict vs flat fields, and so on). Rather than
    force a false uniformity, this models the keys they agree on and preserves the
    rest in ``details``. Unifying the row shape is a scoring-visible change and is
    deliberately out of scope.
    """

    id: str
    model_name: str | None = None
    test_category: str | None = None
    valid: bool | None = None
    score: float | None = None
    details: dict[str, Any] = field(default_factory=dict, repr=False)

    _WIRE_KEYS = frozenset({"id", "model_name", "test_category", "valid", "score"})

    @classmethod
    def from_dict(cls, raw: dict) -> "ScoreRecord":
        known, annotations, extras = split_known(raw, cls._WIRE_KEYS)
        return cls(
            id=known["id"],
            model_name=known.get("model_name"),
            test_category=known.get("test_category"),
            valid=known.get("valid"),
            score=known.get("score"),
            details=dump_extras({}, annotations, extras),
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"id": self.id}
        for name in ("model_name", "test_category", "valid", "score"):
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        return dump_extras(out, self.details)
