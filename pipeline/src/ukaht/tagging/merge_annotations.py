"""Consolidation of annotation files into a single sheet.

Annotations are recorded in several files covering different ranges of
images. This module combines them, aligns column names with the generated
sheet, normalises term formatting and reports values that fall outside the
controlled vocabulary.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from ukaht.tagging import vocabulary as vocab

SHEET_FIELDS = (
    "index",
    "group",
    "filename",
    "scene_type",
    "room",
    "structure",
    "people",
    "orientation",
    "activity",
    "nature",
    "condition",
    "shot_type",
    "object_tags",
    "missing_terms",
    "hesitation",
    "notes",
)

FACET_COLUMNS = (
    "scene_type",
    "room",
    "structure",
    "people",
    "orientation",
    "activity",
    "nature",
    "condition",
    "shot_type",
)

INDEX_ALIASES = ("index", "image", "image_index", "id", "no")


def _read(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _index_of(row: dict[str, str]) -> int | None:
    for alias in INDEX_ALIASES:
        if alias in row and str(row[alias]).strip():
            try:
                return int(str(row[alias]).strip())
            except ValueError:
                continue
    return None


def _values(cell: str) -> list[str]:
    return [part.strip() for part in (cell or "").split("|") if part.strip()]


def normalise_tag(tag: str, known: set[str]) -> str:
    """Match a tag against the vocabulary, allowing for separator differences."""
    candidate = tag.strip().lower()
    if candidate in known:
        return candidate
    spaced = candidate.replace("_", " ")
    if spaced in known:
        return spaced
    underscored = candidate.replace(" ", "_")
    if underscored in known:
        return underscored
    return tag.strip()


def merge(sources: list[Path], manifest: Path | None) -> tuple[list[dict[str, str]], Counter]:
    """Combine annotation files and align them with the sheet schema."""
    context: dict[int, dict[str, str]] = {}
    if manifest and manifest.exists():
        for row in _read(manifest):
            index = _index_of(row)
            if index is not None:
                context[index] = {
                    "group": row.get("group", ""),
                    "filename": row.get("filename", ""),
                }

    known_tags = set(vocab.object_tags())
    corrections: Counter = Counter()
    merged: dict[int, dict[str, str]] = {}

    for source in sources:
        for row in _read(source):
            index = _index_of(row)
            if index is None:
                continue

            record = {field: "" for field in SHEET_FIELDS}
            record["index"] = str(index)
            record.update(context.get(index, {}))

            for column in FACET_COLUMNS:
                record[column] = (row.get(column) or "").strip()

            tags = []
            for tag in _values(row.get("object_tags", "")):
                fixed = normalise_tag(tag, known_tags)
                if fixed != tag.strip():
                    corrections[f"{tag.strip()} -> {fixed}"] += 1
                tags.append(fixed)
            record["object_tags"] = "|".join(tags)

            for column in ("missing_terms", "hesitation", "notes"):
                record[column] = (row.get(column) or "").strip()

            merged[index] = record

    return [merged[key] for key in sorted(merged)], corrections


def check(rows: list[dict[str, str]]) -> list[str]:
    """Return values that do not appear in the controlled vocabulary."""
    problems: list[str] = []
    known_tags = set(vocab.object_tags())

    for row in rows:
        index = row["index"]
        for column in FACET_COLUMNS:
            facet = vocab.facet(column)
            for value in _values(row.get(column, "")):
                if value not in facet.keys:
                    problems.append(f"{index}: {column} = {value}")
            if facet.exclusive and len(_values(row.get(column, ""))) > 1:
                problems.append(f"{index}: {column} holds more than one value")
        for tag in _values(row.get("object_tags", "")):
            if tag not in known_tags:
                problems.append(f"{index}: object tag = {tag}")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Combine annotation files into one sheet")
    parser.add_argument("sources", type=Path, nargs="+", help="annotation files")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/interim/validation_sample/validation_sample.csv"),
        help="sample manifest supplying group and filename",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/validation_sample/validation_annotations.csv"),
        help="destination sheet",
    )
    args = parser.parse_args(argv)

    for source in args.sources:
        if not source.exists():
            print(f"File not found: {source}", file=sys.stderr)
            return 1

    rows, corrections = merge(args.sources, args.manifest)
    if not rows:
        print("No annotation rows were found", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Combined {len(rows)} rows from {len(args.sources)} files")

    if corrections:
        print("\nFormatting aligned with the vocabulary")
        for change, count in corrections.most_common():
            print(f"  {change}  ({count})")

    problems = check(rows)
    if problems:
        print(f"\nValues outside the vocabulary: {len(problems)}")
        for problem in problems:
            print(f"  {problem}")
    else:
        print("\nAll values match the vocabulary")

    print(f"\nWritten to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())