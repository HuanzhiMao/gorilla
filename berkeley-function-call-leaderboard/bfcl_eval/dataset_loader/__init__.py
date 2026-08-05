"""Reading BFCL datasets and ground truth into the typed model.

This is the IO half of the split: ``bfcl_eval.schemas`` defines the shapes,
``bfcl_eval.dataset_loader`` reads them off disk and applies the per-category
post-processing.

Two public entry points::

    load_dataset_entries("text:multi_turn_base")     -> list[TestEntry]
    load_ground_truth_entries("text:multi_turn_base") -> list[GroundTruth]

``load_dataset_entries`` is a standalone implementation: it reads the file its
category's registry row names and runs that row's declared stages. The legacy dict
loader in ``bfcl_eval.utils`` is deliberately left in place as an independent
reference: the two were verified to agree for every category, entry for entry, and
keeping both means that comparison can be repeated after a change here.

``load_ground_truth_entries`` still parses the legacy loader's output; ground truth
needs no post-processing beyond reading the file, so there is nothing to move.
"""

from __future__ import annotations

from bfcl_eval.dataset_loader.jsonl import read_entries
from bfcl_eval.dataset_loader.pipeline import LoadContext, run_pipeline
from bfcl_eval.schemas.category import TestCategory
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.ground_truth import GroundTruth, GroundTruthKind, parse_ground_truth


def _as_category(category: TestCategory | str) -> TestCategory:
    return category if isinstance(category, TestCategory) else TestCategory.parse(category)


def load_dataset_entries(
    category: TestCategory | str,
    *,
    include_prereq: bool = True,
    include_language_specific_hint: bool = True,
) -> list[TestEntry]:
    """Load one category's test entries as typed objects.

    Reads the file the category's registry row names, then runs the stages that row
    declares. See ``bfcl_eval.dataset_loader.pipeline`` for the two-phase shape.
    """
    category = _as_category(category)
    if not category.is_loadable:
        raise ValueError(
            f"{category.value} is a derived category -- its entries are produced as a "
            f"side effect of loading its parent category, not requested directly"
        )

    raw_entries = read_entries(category.dataset_path())
    return run_pipeline(
        raw_entries,
        LoadContext(
            category=category,
            include_prereq=include_prereq,
            include_language_specific_hint=include_language_specific_hint,
        ),
    )


def load_ground_truth_entries(category: TestCategory | str) -> list[GroundTruth]:
    """Load one category's ground truth as typed objects.

    Returns an empty list for the relevance and irrelevance categories, which ship
    no ground-truth file; that matches what the evaluator does today rather than
    inventing a placeholder.
    """
    from bfcl_eval.utils import load_ground_truth_entry

    category = _as_category(category)
    if category.ground_truth_kind is GroundTruthKind.NONE:
        return []
    raw_entries = load_ground_truth_entry(category.value)
    return [parse_ground_truth(raw, category.ground_truth_kind) for raw in raw_entries]


__all__ = ["load_dataset_entries", "load_ground_truth_entries"]
