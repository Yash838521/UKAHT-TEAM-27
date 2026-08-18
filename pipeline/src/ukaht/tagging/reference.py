"""Consolidation of annotation sets into a single reference.

Annotation was carried out in stages, and the sheets differ in layout: earlier
sheets identify images by position within a sample manifest, later sheets carry
the image identifier directly. This module resolves both to a common identifier
and combines them.

Where the same image was labelled by more than one annotator, one set of labels
is retained rather than averaged. Combining disagreeing labels would produce a
reference that neither annotator endorsed, so the first annotator encountered is
treated as authoritative and the duplication is reported.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ukaht.tagging import vocabulary as vocab

OUTPUT_FIELDS = (
    "image_uid",
    "file_name",
    "relative_path",
    "source",
    "annotator",
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

EXCLUSIVE_FACETS = ("scene_type", "room", "people", "shot_type")


@dataclass
class SheetResult:
    """Rows read from one sheet, with any that could not be resolved."""

    rows: list[dict]
    unresolved: list[str]
    source: str


def _read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle) if any(row.values())]


def _values(cell: object) -> list[str]:
    return [part.strip() for part in str(cell or "").split("|") if part.strip()]


def build_path_lookup(index: pd.DataFrame) -> dict[str, str]:
    """Return image identifiers keyed by lower-cased relative path."""
    return {
        row["relative_path"].strip().lower(): row["image_uid"]
        for row in index.to_dict(orient="records")
    }


def read_sheet(
    path: Path,
    source: str,
    index: pd.DataFrame,
    manifest: Path | None = None,
    annotator: str | None = None,
) -> SheetResult:
    """Read one annotation sheet and resolve every row to an image identifier.

    Sheets carrying an identifier are used directly. Sheets identifying images
    by position are resolved through the manifest that produced them.
    """
    rows = _read(path)
    if not rows:
        return SheetResult([], [], source)

    path_lookup = build_path_lookup(index)
    uid_by_position: dict[int, str] = {}
    path_by_uid = {
        row["image_uid"]: row["relative_path"] for row in index.to_dict(orient="records")
    }

    if manifest is not None and manifest.exists():
        for entry in _read(manifest):
            key = str(entry.get("index", "")).strip()
            relative = (entry.get("relative_path") or "").strip().lower()
            if key and relative in path_lookup:
                uid_by_position[int(key)] = path_lookup[relative]

    resolved: list[dict] = []
    unresolved: list[str] = []

    for row in rows:
        if not str(row.get("scene_type", "")).strip():
            continue

        image_uid = str(row.get("image_uid", "")).strip()
        if not image_uid:
            key = str(row.get("index", "")).strip()
            image_uid = uid_by_position.get(int(key), "") if key.isdigit() else ""

        if not image_uid:
            unresolved.append(str(row.get("index", "?")))
            continue

        record = {field: "" for field in OUTPUT_FIELDS}
        record["image_uid"] = image_uid
        record["file_name"] = (
            str(row.get("file_name") or row.get("filename") or "").strip()
        )
        record["relative_path"] = path_by_uid.get(image_uid, "")
        record["source"] = source
        record["annotator"] = annotator or str(row.get("annotator", "")).strip()

        for column in FACET_COLUMNS + ("object_tags", "missing_terms", "hesitation", "notes"):
            record[column] = str(row.get(column) or "").strip()

        resolved.append(record)

    return SheetResult(resolved, unresolved, source)


def combine(results: list[SheetResult]) -> tuple[list[dict], list[dict]]:
    """Combine sheets, retaining one set of labels per image."""
    combined: dict[str, dict] = {}
    duplicates: list[dict] = []

    for result in results:
        for row in result.rows:
            image_uid = row["image_uid"]
            if image_uid in combined:
                duplicates.append(
                    {
                        "image_uid": image_uid,
                        "file_name": row["file_name"],
                        "retained_from": combined[image_uid]["annotator"]
                        or combined[image_uid]["source"],
                        "also_labelled_by": row["annotator"] or row["source"],
                    }
                )
                continue
            combined[image_uid] = row

    return list(combined.values()), duplicates


def check_terms(rows: list[dict]) -> list[str]:
    """Return values that do not appear in the controlled vocabulary."""
    problems: list[str] = []
    known_tags = set(vocab.object_tags())

    for row in rows:
        for column in FACET_COLUMNS:
            facet = vocab.facet(column)
            values = _values(row.get(column))
            for value in values:
                if value not in facet.keys:
                    problems.append(f"{row['image_uid'][:8]}: {column} = {value}")
            if column in EXCLUSIVE_FACETS and len(values) > 1:
                problems.append(f"{row['image_uid'][:8]}: {column} holds several values")

        for tag in _values(row.get("object_tags")):
            if tag not in known_tags:
                problems.append(f"{row['image_uid'][:8]}: object tag = {tag}")

    return problems


def summarise(rows: list[dict]) -> str:
    """Return a readable account of the combined reference set."""
    lines = [f"Reference images: {len(rows)}", ""]

    sources = Counter(row["source"] for row in rows)
    lines.append("By source")
    width = max(len(name) for name in sources)
    for name in sorted(sources):
        lines.append(f"  {name:<{width}}  {sources[name]:>4}")

    annotators = Counter(row["annotator"] or "unrecorded" for row in rows)
    lines.append("")
    lines.append("By annotator")
    width = max(len(name) for name in annotators)
    for name in sorted(annotators):
        lines.append(f"  {name:<{width}}  {annotators[name]:>4}")

    lines.append("")
    lines.append("Annotation support per facet")
    for column in FACET_COLUMNS:
        instances = sum(len(_values(row.get(column))) for row in rows)
        images = sum(1 for row in rows if _values(row.get(column)))
        lines.append(f"  {column:<14} {images:>4} images, {instances:>4} term instances")

    tags = sum(len(_values(row.get("object_tags"))) for row in rows)
    distinct = len({tag for row in rows for tag in _values(row.get("object_tags"))})
    lines.append("")
    lines.append(f"  object_tags    {distinct:>4} distinct, {tags:>4} instances")

    scenes = Counter(row["scene_type"] for row in rows if row["scene_type"])
    lines.append("")
    lines.append("Scene type distribution")
    for name, count in scenes.most_common():
        lines.append(f"  {name:<14} {count:>4} ({count / len(rows):.1%})")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Combine annotation sets into a single reference"
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument(
        "--legacy",
        type=Path,
        default=None,
        help="earlier sheet identifying images by position",
    )
    parser.add_argument(
        "--legacy-manifest",
        type=Path,
        default=None,
        help="manifest that produced the earlier sheet",
    )
    parser.add_argument(
        "--sheets",
        type=Path,
        nargs="*",
        default=[],
        help="sheets carrying an image identifier",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/ground_truth/reference.csv"),
    )
    args = parser.parse_args(argv)

    problems = vocab.validate()
    if problems:
        raise ValueError("vocabulary validation failed: " + "; ".join(problems))

    index = pd.read_csv(args.index, dtype=str).fillna("")
    print(f"Vocabulary version {vocab.VERSION}")
    print(f"Images in index: {len(index)}")
    print()

    results: list[SheetResult] = []

    if args.legacy is not None and args.legacy.exists():
        result = read_sheet(
            args.legacy,
            source="validation",
            index=index,
            manifest=args.legacy_manifest,
            annotator="saisha",
        )
        print(f"{args.legacy.name}: {len(result.rows)} rows")
        if result.unresolved:
            print(f"  unresolved: {', '.join(result.unresolved)}")
        results.append(result)

    for path in args.sheets:
        if not path.exists():
            print(f"Sheet not found: {path}")
            return 1
        result = read_sheet(path, source="ground_truth", index=index)
        print(f"{path.name}: {len(result.rows)} rows")
        if result.unresolved:
            print(f"  unresolved: {', '.join(result.unresolved)}")
        results.append(result)

    if not results:
        print("No sheets were supplied")
        return 1

    rows, duplicates = combine(results)
    print()

    if duplicates:
        print(f"Images labelled by more than one annotator: {len(duplicates)}")
        print("  one set of labels retained per image; the rest are reported below")
        print()

    issues = check_terms(rows)
    if issues:
        print(f"Values outside the vocabulary: {len(issues)}")
        for issue in issues[:20]:
            print(f"  {issue}")
        if len(issues) > 20:
            print(f"  and {len(issues) - 20} more")
        print()

    print(summarise(rows))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    if duplicates:
        duplicate_path = args.output.with_name("reference_duplicates.csv")
        pd.DataFrame(duplicates).to_csv(duplicate_path, index=False)
        print()
        print(f"Duplicates: {duplicate_path}")

    print()
    print(f"Reference: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
