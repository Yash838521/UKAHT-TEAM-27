"""Conversion of free-text coding notes into the structured coding sheet.

Notes are written as one block per image, introduced by a line naming the image
number and followed by field names each on their own line above their value.
This module parses that layout and merges the values into an existing coding
sheet, matching on image index.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

FIELDS = (
    "what_is_shown",
    "objects_present",
    "setting",
    "people_present",
    "condition_or_damage",
    "candidate_terms",
    "notes",
)

_HEADING = re.compile(r"^\s*(?:image|img)\s*[#:]?\s*(\d+)\s*$", re.IGNORECASE)
_FIELD = re.compile(r"^\s*(" + "|".join(FIELDS) + r")\s*:?\s*$", re.IGNORECASE)
_SEPARATOR = re.compile(r"^[\s\u2e3b\u2014\u2013_*=-]*$")
_PLACEHOLDER = {"", "-", "n/a", "na", "none given", "tbc"}

_GENERIC = {
    "object",
    "objects",
    "item",
    "items",
    "thing",
    "things",
    "artefact",
    "artifact",
    "display surface",
    "surface",
    "background",
    "equipment",
    "historic object",
    "heritage object",
}


def parse(text: str) -> dict[int, dict[str, str]]:
    """Return field values keyed by image index."""
    records: dict[int, dict[str, str]] = {}
    current_index: int | None = None
    current_field: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if current_index is not None and current_field is not None:
            value = " ".join(line.strip() for line in buffer if line.strip())
            if value:
                records.setdefault(current_index, {})[current_field] = value
        buffer = []

    for raw_line in text.splitlines():
        heading = _HEADING.match(raw_line)
        if heading:
            flush()
            current_index = int(heading.group(1))
            current_field = None
            records.setdefault(current_index, {})
            continue

        field = _FIELD.match(raw_line)
        if field:
            flush()
            current_field = field.group(1).lower()
            continue

        if _SEPARATOR.match(raw_line):
            continue

        if current_field is not None:
            buffer.append(raw_line)

    flush()
    return {index: values for index, values in records.items() if values}


def merge(sheet_path: Path, records: dict[int, dict[str, str]]) -> tuple[int, list[int]]:
    """Write parsed values into the coding sheet and report unmatched rows."""
    with open(sheet_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if "index" not in fieldnames:
        raise KeyError("coding sheet is missing an index column")

    filled = 0
    unmatched: list[int] = []

    for row in rows:
        index = int(row["index"])
        values = records.get(index)
        if not values:
            unmatched.append(index)
            continue
        for field in FIELDS:
            if field in fieldnames and values.get(field):
                row[field] = values[field]
        filled += 1

    with open(sheet_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return filled, unmatched


def report_thin_entries(sheet_path: Path, minimum_words: int = 4) -> list[int]:
    """Return indices whose description is too short to be usable."""
    thin: list[int] = []
    with open(sheet_path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            description = (row.get("what_is_shown") or "").strip()
            objects = (row.get("objects_present") or "").strip()
            named = [
                part.strip().lower().rstrip(".")
                for part in objects.split(",")
                if part.strip()
            ]
            specific = [part for part in named if part not in _GENERIC]

            if description.lower() in _PLACEHOLDER or len(description.split()) < minimum_words:
                thin.append(int(row["index"]))
            elif len(named) < 2 or not specific:
                thin.append(int(row["index"]))
    return thin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge free-text coding notes into the coding sheet"
    )
    parser.add_argument("notes", type=Path, nargs="+", help="one or more notes files")
    parser.add_argument(
        "--sheet",
        type=Path,
        default=Path("data/interim/viewing_sample/coding_notes.csv"),
        help="coding sheet to update",
    )
    args = parser.parse_args(argv)

    if not args.sheet.exists():
        print(f"Coding sheet not found: {args.sheet}", file=sys.stderr)
        return 1

    combined: dict[int, dict[str, str]] = {}
    for path in args.notes:
        if not path.exists():
            print(f"Notes file not found: {path}", file=sys.stderr)
            return 1
        parsed = parse(path.read_text(encoding="utf-8"))
        print(f"{path.name}: {len(parsed)} entries")
        for index, values in parsed.items():
            combined.setdefault(index, {}).update(values)

    filled, unmatched = merge(args.sheet, combined)
    print(f"\nRows updated: {filled}")

    if unmatched:
        print(f"Rows with no notes: {', '.join(str(i) for i in unmatched)}")

    thin = report_thin_entries(args.sheet)
    if thin:
        print(f"Rows needing more detail: {', '.join(str(i) for i in thin)}")

    print(f"\nUpdated {args.sheet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())