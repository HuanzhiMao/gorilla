"""Running a category's declared loading pipeline.

The transforms a category needs used to live in an if/elif chain inside
``load_dataset_entry``, so answering "what happens to my category on the way in?"
meant reading the whole function. Now each category declares an ordered list of
:class:`~bfcl_eval.schemas.category.StageId` and this module runs it.

The pipeline has two halves, separated by ``StageId.PARSE``:

* before it, stages take and return ``list[dict]`` -- they change an entry's identity
  or rebuild it outright, so the typed object cannot exist yet;
* after it, stages take and return ``list[TestEntry]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bfcl_eval.schemas.category import StageId, TestCategory


@dataclass(frozen=True)
class LoadContext:
    """Everything a stage needs to know beyond the entries themselves."""

    category: TestCategory
    include_prereq: bool = True
    include_language_specific_hint: bool = True


# Stage implementations, populated lazily to keep the import graph acyclic: the
# stages import LoadContext from this module.
_RAW_STAGES: dict[StageId, Callable] = {}
_TYPED_STAGES: dict[StageId, Callable] = {}


def _register() -> None:
    if _RAW_STAGES:
        return
    from bfcl_eval.dataset_loader.stages import raw, typed

    _RAW_STAGES.update(
        {
            StageId.ASSIGN_IDS: raw.assign_ids,
            StageId.MEMORY_PREREQ_LINK: raw.memory_prereq_link,
            StageId.VISION_ATTACH_IMAGE: raw.vision_attach_image,
            StageId.AUDIO_MATERIALIZE: raw.audio_materialize,
        }
    )
    _TYPED_STAGES.update(
        {
            StageId.RESOLVE_INITIAL_CONFIG: typed.resolve_initial_config,
            StageId.MARK_LONG_CONTEXT: typed.mark_long_context,
            StageId.STRUCTURED_ANSWER_PROMPT: typed.structured_answer_prompt,
            StageId.RESOLVE_TOOLS: typed.resolve_tools,
            StageId.RESOLVE_HOLDOUT_DOCS: typed.resolve_holdout_docs,
            StageId.LANGUAGE_HINT: typed.language_hint,
        }
    )


def describe(category: TestCategory) -> list[str]:
    """The stage names a category runs, in order. Useful for explaining a category."""
    return [stage.value for stage in category.load_stages]


def run_pipeline(raw_entries: list[dict], ctx: LoadContext) -> list:
    """Run ``ctx.category``'s declared stages over freshly-read raw entries."""
    _register()

    stages = ctx.category.load_stages
    if StageId.PARSE not in stages:
        raise ValueError(
            f"{ctx.category.value} declares no PARSE stage, so its entries would never "
            f"become typed objects"
        )

    from bfcl_eval.schemas.entries import parse_test_entry

    entries = raw_entries
    parsed = False
    for stage in stages:
        if stage is StageId.PARSE:
            entries = [parse_test_entry(raw, ctx.category) for raw in entries]
            parsed = True
            continue

        table = _TYPED_STAGES if parsed else _RAW_STAGES
        try:
            implementation = table[stage]
        except KeyError:
            side = "after" if parsed else "before"
            raise ValueError(
                f"{ctx.category.value} declares stage {stage.value!r} {side} PARSE, "
                f"but no {'typed' if parsed else 'raw'} implementation is registered "
                f"for it"
            ) from None
        entries = implementation(entries, ctx)

    return entries
