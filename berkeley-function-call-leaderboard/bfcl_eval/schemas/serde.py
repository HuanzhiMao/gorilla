"""Shared serialization helpers for the BFCL data model.

Every dataclass in this package follows the same three rules, and this module holds
the pieces they share:

1. **Unknown keys survive.**  ``split_known`` partitions a raw JSON object into
   recognized fields, ``_``-prefixed authoring annotations, and genuinely unknown
   keys.  Nothing is ever dropped, so ``to_dict(from_dict(raw)) == raw`` holds for
   every line of every shipped dataset file.

2. **``to_dict`` emits presence, not ``None``.**  A field that was absent on disk
   must stay absent after a round trip; ``dataclasses.asdict`` would emit
   ``"image_content": null`` on every text message and break rule 1.

3. **Extras are written last**, so a modeled field never silently shadows a
   preserved one.
"""

from __future__ import annotations

import warnings
from typing import Any, Iterable

ANNOTATION_PREFIX = "_"

# Authoring/provenance keys that the dataset carries for human readers.  Listed here
# so `split_known` can route them without warning; the list is descriptive, not
# enforced -- any `_`-prefixed key is treated as an annotation.
KNOWN_ANNOTATION_KEYS = frozenset(
    {
        "_comment",
        "_source",
        "_original_id",
        "_expected_recovery",
        "_scenario_description",
        "_failure_source",
        "_failure_type",
        "_sheet_servers",
        "_sheet_initial_state",
        "_confirmation_added_for_non_noop",
        "_yash_index",
    }
)

# Non-underscore keys that exist on disk and have no reader anywhere in bfcl_eval.
# They must round-trip, but promoting them to real fields would imply a consumer
# that does not exist.  Listed so `split_known` does not warn about them.
KNOWN_UNMODELED_KEYS = frozenset(
    {
        "path",  # multi_turn: the intended tool trajectory, never read
        "excluded_function",  # multi_turn: never read
        # The pre-`missed_classes` spelling of holdout rules, and a different shape
        # entirely (turn index -> function names). Survives only in the audio
        # datasets, which do not currently load at all.
        "missed_function",
    }
)

# Parameter-schema keys that are part of BFCL's JSON-Schema dialect but have no
# named field on `ParameterSchema`. They round-trip through `extras`; the point of
# listing them is that they are *known*, so schema drift stays distinguishable from
# the long tail we already accept.
PARAMETER_DIALECT_KEYS = frozenset(
    {
        "optional",  # 194 occurrences; not JSON Schema
        "additionalProperties",  # 9
        "format",  # 16
        "maximum",  # 8
        "minItems",  # 2
        "maxItems",  # 2
    }
)

_WARNED: set[str] = set()


def warn_once(message: str) -> None:
    """Emit ``message`` at most once per process.

    Used for schema drift: the first time a dataset file grows a key the model does
    not know about, say so, but do not spam once per entry.
    """
    if message in _WARNED:
        return
    _WARNED.add(message)
    warnings.warn(message, stacklevel=3)


def split_known(
    raw: dict, known: Iterable[str], *, silent: Iterable[str] = ()
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Partition ``raw`` into ``(recognized, annotations, extras)``.

    * ``recognized`` -- keys the caller declared in ``known``.
    * ``annotations`` -- ``_``-prefixed keys (dataset authoring metadata).
    * ``extras`` -- everything else, preserved verbatim.

    Unknown keys warn once so schema drift surfaces instead of vanishing quietly.
    ``silent`` names additional keys the caller already knows about and chose not to
    model; they land in ``extras`` without a warning.
    """
    known = frozenset(known)
    accepted = KNOWN_UNMODELED_KEYS | frozenset(silent)
    recognized: dict[str, Any] = {}
    annotations: dict[str, Any] = {}
    extras: dict[str, Any] = {}

    for key, value in raw.items():
        if key in known:
            recognized[key] = value
        elif key.startswith(ANNOTATION_PREFIX):
            annotations[key] = value
        else:
            extras[key] = value
            if key not in accepted:
                warn_once(f"unmodeled dataset key {key!r}")

    return recognized, annotations, extras


def dump_extras(out: dict, *buckets: dict) -> dict:
    """Merge preserved buckets into ``out`` and return it, for use as a tail call."""
    for bucket in buckets:
        out.update(bucket)
    return out
