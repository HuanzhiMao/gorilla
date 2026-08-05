"""Reading the JSONL files the dataset ships as.

Every ``.json`` file under ``bfcl_eval/data/`` is really JSONL -- one JSON object per
line -- so ``json.load`` on one of them fails. This module is the single place that
knows that.
"""

from __future__ import annotations

from pathlib import Path


def read_entries(path: Path) -> list[dict]:
    """Read one JSONL dataset file into a list of raw objects.

    Delegates to ``utils.load_file`` so the cross-process file locking stays in one
    place rather than being duplicated here.
    """
    from bfcl_eval.utils import load_file

    return load_file(path)
