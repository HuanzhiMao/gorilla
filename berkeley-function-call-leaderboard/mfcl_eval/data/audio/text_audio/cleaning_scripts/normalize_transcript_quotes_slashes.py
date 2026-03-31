#!/usr/bin/env python3
"""
Normalize each role: user's transcript field:
  1) Fix starting and trailing quotation marks (strip or collapse so clean).
  2) Remove or fix weird slashes (examples to be added).

Same structure as remove_trailing_fillers: --file, --dry-run, --inplace.
Test on one or two files first, then run on the rest.

Usage:
  python normalize_transcript_quotes_slashes.py --file MFCL_v4_irrelevance.json   # report + write _cleaned.json
  python normalize_transcript_quotes_slashes.py --file MFCL_v4_irrelevance.json --dry-run   # report only
  python normalize_transcript_quotes_slashes.py --file MFCL_v4_irrelevance.json --inplace   # overwrite original
"""

import argparse
import json
import re
from pathlib import Path


def fix_starting_trailing_quotes(transcript: str) -> tuple[str, bool]:
    """
    Strip or normalize leading/trailing double-quotes so the transcript
    doesn't have stray \" when written to JSON. Safe rules:
    - exactly one quote at start or end: remove that one
    - exactly two quotes (start and end): remove both
    - 3+ quotes: leave unchanged (interior quoted phrases)
    """
    if not transcript or not isinstance(transcript, str):
        return transcript, False
    s = transcript.strip()
    orig = s
    n = s.count('"')
    if n == 1:
        if s.startswith('"'):
            s = s[1:].strip()
        elif s.endswith('"'):
            s = s[:-1].strip()
    elif n == 2 and s.startswith('"') and s.endswith('"'):
        s = s[1:-1].strip()
    if s != orig:
        return s, True
    return transcript, False


def fix_weird_slashes(transcript: str) -> tuple[str, bool]:
    """
    Remove escaped-quote style wrapping: ', "' -> ', ' and strip trailing ", or ".
    E.g. "Um, \"For that same third file...\"" -> "Um, For that same third file..."
    (In Python the transcript has literal ", not backslash; we remove the wrapping quotes.)
    """
    if not transcript or not isinstance(transcript, str):
        return transcript, False
    s = transcript
    orig = s
    # Remove comma-space-quote (start of quoted phrase) so we don't get \" in JSON
    s = s.replace(', "', ', ')
    # Remove trailing quote and optional trailing comma
    s = s.rstrip(' ",')
    if s != orig:
        return s.strip(), True
    return transcript, False


def load_json_objects(path: Path):
    """Yield one dict per test case (handles NDJSON and concatenated pretty JSON)."""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    lines = text.split("\n")
    if lines:
        first = lines[0].strip()
        if first.startswith("{") and first.endswith("}"):
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and ("id" in obj or "question" in obj):
                        yield obj
                except json.JSONDecodeError:
                    pass
            return
    try:
        data = json.loads(text)
        if isinstance(data, list):
            yield from data
            return
        if isinstance(data, dict) and ("id" in data or "question" in data):
            yield data
            return
    except json.JSONDecodeError:
        pass
    parts = re.split(r"\}\s*\n\s*\{", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if not part.startswith("{"):
            part = "{" + part
        if not part.endswith("}"):
            part = part + "}"
        try:
            yield json.loads(part)
        except json.JSONDecodeError:
            continue


def apply_to_object(obj, quote_changes: list, slash_changes: list) -> dict:
    """Walk each role: user transcript; fix quotes then weird slashes. Returns modified copy."""
    obj = json.loads(json.dumps(obj))  # deep copy
    questions = obj.get("question") or []
    for turn_list in questions:
        if not isinstance(turn_list, list):
            continue
        for msg in turn_list:
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            t = msg.get("transcript")
            if t is None:
                continue
            current = t
            # 1) Starting/trailing quotes
            new_t, changed = fix_starting_trailing_quotes(current)
            if changed:
                msg["transcript"] = new_t
                quote_changes.append((obj.get("id"), current, new_t))
                current = new_t
            # 2) Weird slashes
            new_t, changed = fix_weird_slashes(current)
            if changed:
                msg["transcript"] = new_t
                slash_changes.append((obj.get("id"), current, new_t))
    return obj


def main():
    ap = argparse.ArgumentParser(
        description="Normalize transcript quotes and weird slashes (starting/trailing \", slashes)."
    )
    ap.add_argument("--file", required=True, help="Path to one JSON file (e.g. MFCL_v4_irrelevance.json)")
    ap.add_argument("--dry-run", action="store_true", help="Print report only; do not write any file.")
    ap.add_argument("--inplace", action="store_true", help="Overwrite original file (use after verifying).")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    path = (root / args.file).resolve()
    if not path.is_file():
        path = Path(args.file).resolve()
    if not path.is_file():
        print(f"File not found: {args.file}")
        return 1
    if "_cleaned" in path.name:
        print("Error: Use the ORIGINAL file as input (not a _cleaned file).")
        return 1

    quote_changes: list[tuple[str, str, str]] = []
    slash_changes: list[tuple[str, str, str]] = []
    out_objects = []
    for obj in load_json_objects(path):
        modified = apply_to_object(obj, quote_changes, slash_changes)
        out_objects.append(modified)

    print(f"File: {path.name}")
    print(f"Total test cases: {len(out_objects)}")
    print(f"Transcripts modified (quotes): {len(quote_changes)}")
    print(f"Transcripts modified (weird slashes): {len(slash_changes)}\n")
    if quote_changes:
        print("--- Quote fixes (id | before -> after) ---\n")
        for i, (tid, before, after) in enumerate(quote_changes, 1):
            print(f"{i}. id={tid}")
            print(f"   BEFORE: {before!r}")
            print(f"   AFTER:  {after!r}\n")
    if slash_changes:
        print("--- Slash fixes (id | before -> after) ---\n")
        for i, (tid, before, after) in enumerate(slash_changes, 1):
            print(f"{i}. id={tid}")
            print(f"   BEFORE: {before!r}")
            print(f"   AFTER:  {after!r}\n")

    if args.dry_run:
        print("(Dry-run: no file written.)")
        return 0

    if not out_objects:
        print("No objects to write.")
        return 0

    if args.inplace:
        out_path = path
        print(f"Writing (inplace): {out_path}")
    else:
        out_path = path.parent / (path.stem + "_cleaned.json")
        print(f"Writing: {out_path}")

    raw = path.read_text(encoding="utf-8", errors="replace")
    first_line = raw.strip().split("\n")[0].strip() if raw.strip() else ""
    is_ndjson = first_line.startswith("{") and first_line.endswith("}") and len(first_line) > 100

    with open(out_path, "w", encoding="utf-8") as f:
        if is_ndjson:
            for obj in out_objects:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        else:
            for i, obj in enumerate(out_objects):
                if i > 0:
                    f.write("\n")
                f.write(json.dumps(obj, ensure_ascii=False, indent=4))

    print("Done.")
    return 0


if __name__ == "__main__":
    exit(main())
