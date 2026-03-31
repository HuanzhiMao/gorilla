#!/usr/bin/env python3
"""
Two separate tasks:
  1) Remove only trailing filler (um, uh). Never touch or remove any quotation mark.
  2) Normalize speech quotes: ensure each transcript starts and ends with a single ".
     Only collapse 2+ quotes at the very start and very end; never edit the interior.

Always use the ORIGINAL file as input (not a _cleaned file). Output is written to _cleaned.json.

Usage:
  python remove_trailing_fillers.py --file MFCL_v4_irrelevance.json   # report + write _cleaned.json
  python remove_trailing_fillers.py --file MFCL_v4_irrelevance.json --dry-run   # report only, no write
  python remove_trailing_fillers.py --file MFCL_v4_irrelevance.json --inplace   # overwrite original (use after verification)
"""

import argparse
import json
import re
from pathlib import Path

# Match ONLY trailing filler (uh|um) as whole words—not "um" inside "Belgium"/"aluminum".
# No leading [\s,]* so we never consume a " (e.g. ..." "Uh, uh. -> we remove only "Uh, uh.", leave ..." ").
TRAILING_FILLER_RE = re.compile(
    r"(?<![a-zA-Z])(?:uh|um)(?:\s*,\s*(?:uh|um))*\s*\.?\s*$",
    re.IGNORECASE
)


def strip_trailing_filler(transcript: str) -> tuple[str, bool]:
    """
    Remove only trailing filler words (um, uh). Return (cleaned_string, True) if changed.
    Never touches or removes any quotation mark; that is a separate task.
    """
    if not transcript or not isinstance(transcript, str):
        return transcript, False
    stripped = transcript.strip()
    if not stripped:
        return transcript, False
    match = TRAILING_FILLER_RE.search(stripped)
    if not match:
        return transcript, False
    # Match is only filler (uh/um); we never consume a quote
    new_text = stripped[: match.start()].rstrip()
    new_text = new_text.rstrip(" \t\u2014\u2013-")  # no quote in this set
    if not new_text or not new_text.rstrip(".,;:!?").strip():
        return transcript, False
    return new_text, True


def normalize_speech_quotes(transcript: str) -> tuple[str, bool]:
    """
    Remove the outer speech quotes so when written to JSON there is no \" inside
    (only the JSON string delimiters). Only strip when safe:
    - exactly one quote at start or end: remove that one
    - exactly two quotes (start and end): remove both (whole string was quoted)
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


def apply_to_object(obj, changes_list: list, quote_changes_list: list) -> dict:
    """Walk object: strip trailing filler, then normalize speech quotes (one " at start, one at end). Returns modified copy."""
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
            # 1) Remove trailing filler
            new_t, changed = strip_trailing_filler(t)
            if changed:
                msg["transcript"] = new_t
                changes_list.append((obj.get("id"), t, new_t))
                t = new_t
            # 2) Normalize quotes: one " at start, one " at end (collapse double-ups)
            current = msg["transcript"]
            normalized, quote_changed = normalize_speech_quotes(current)
            if quote_changed:
                msg["transcript"] = normalized
                quote_changes_list.append((obj.get("id"), current, normalized))
    return obj


def main():
    ap = argparse.ArgumentParser(description="Remove trailing um/uh and normalize speech quotes (one \" at start, one at end).")
    ap.add_argument("--file", required=True, help="Path to one JSON file (e.g. MFCL_v4_irrelevance.json)")
    ap.add_argument("--dry-run", action="store_true", help="Print report only; do not write any file.")
    ap.add_argument("--inplace", action="store_true", help="Overwrite original file (use only after verifying _cleaned.json).")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    path = (root / args.file).resolve()
    if not path.is_file():
        path = Path(args.file).resolve()
    if not path.is_file():
        print(f"File not found: {args.file}")
        return 1
    if "_cleaned" in path.name:
        print("Error: Use the ORIGINAL file as input (not a _cleaned file). Running cleaned on cleaned is not allowed.")
        return 1

    changes: list[tuple[str, str, str]] = []
    quote_changes: list[tuple[str, str, str]] = []
    out_objects = []
    for obj in load_json_objects(path):
        modified = apply_to_object(obj, changes, quote_changes)
        out_objects.append(modified)

    # Report
    print(f"File: {path.name}")
    print(f"Total test cases: {len(out_objects)}")
    print(f"Transcripts modified (trailing filler removed): {len(changes)}")
    print(f"Transcripts modified (quote normalization): {len(quote_changes)}\n")
    if changes:
        print("--- Trailing filler removed (id | before -> after) ---\n")
        for i, (tid, before, after) in enumerate(changes, 1):
            print(f"{i}. id={tid}")
            print(f"   BEFORE: {before!r}")
            print(f"   AFTER:  {after!r}\n")
    if quote_changes:
        print("--- Quote normalization: one \" at start, one at end (id | before -> after) ---\n")
        for i, (tid, before, after) in enumerate(quote_changes, 1):
            print(f"{i}. id={tid}")
            print(f"   BEFORE: {before!r}")
            print(f"   AFTER:  {after!r}\n")

    if args.dry_run:
        print("(Dry-run: no file written.)")
        return 0

    if not out_objects:
        print("No objects to write.")
        return 0

    # Write output
    if args.inplace:
        out_path = path
        print(f"Writing (inplace): {out_path}")
    else:
        out_path = path.parent / (path.stem + "_cleaned.json")
        print(f"Writing: {out_path}")

    # Preserve format: if original was NDJSON (one line per object), write NDJSON; else pretty-print blocks
    raw = path.read_text(encoding="utf-8", errors="replace")
    is_ndjson = raw.strip().count("\n") > 10 and all(
        line.strip().startswith("{") and line.strip().endswith("}") for line in raw.strip().split("\n") if line.strip()
    ) if raw.strip() else False
    # Simpler: if first line is a full JSON object, treat as NDJSON for output
    first_line = raw.strip().split("\n")[0].strip()
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
