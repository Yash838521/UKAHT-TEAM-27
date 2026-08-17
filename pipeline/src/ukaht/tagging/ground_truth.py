"""Selection and allocation of the ground-truth annotation set.

Measurement requires a reference set of images labelled by hand. Where more than
one person labels, a block annotated by everyone allows the consistency of those
labels to be quantified, which is otherwise unavailable.

Images are drawn from the archive excluding every image used during vocabulary
development or validation, so that the reference set is independent of the terms
being tested. Selection is stratified across collection and quality band and
uses a fixed seed, making it reproducible.

The selection is divided into a block seen by all annotators and further blocks
allocated to one annotator each. Agreement is computed on the shared block; the
exclusive blocks extend coverage without duplicating effort.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

SHEET_FIELDS = (
    "index",
    "block",
    "annotator",
    "image_uid",
    "file_name",
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

MANIFEST_FIELDS = (
    "index",
    "block",
    "annotator",
    "image_uid",
    "file_name",
    "relative_path",
    "collection",
    "quality_band",
)

_UNSAFE = re.compile(r"[^A-Za-z0-9]+")

QUALITY_BANDS = ((0.0, 0.45, "low"), (0.45, 0.65, "medium"), (0.65, 1.01, "high"))


def load_index(path: Path) -> pd.DataFrame:
    """Load the image index and derive the collection from each path."""
    index = pd.read_csv(path, dtype=str).fillna("")
    index["collection"] = index["relative_path"].str.split("/").str[0]
    return index


def load_quality(path: Path | None, index: pd.DataFrame) -> dict[str, str]:
    """Return a quality band per image, where measurements are available."""
    if path is None or not path.exists():
        return {}

    quality = pd.read_csv(path)
    quality["join_key"] = quality["image_name"].str.strip().str.lower()

    lookup = {}
    for row in index.to_dict(orient="records"):
        parts = row["relative_path"].split("/")
        lookup["/".join(parts[-2:]).lower()] = row["image_uid"]

    bands: dict[str, str] = {}
    for row in quality.to_dict(orient="records"):
        image_uid = lookup.get(row["join_key"])
        if image_uid is None:
            continue
        score = float(row.get("overall_score", 0.0))
        for lower, upper, label in QUALITY_BANDS:
            if lower <= score < upper:
                bands[image_uid] = label
                break

    return bands


def load_excluded(paths: list[Path], index: pd.DataFrame) -> set[str]:
    """Return identifiers of images already used in earlier samples."""
    by_path = {
        row["relative_path"].strip().lower(): row["image_uid"]
        for row in index.to_dict(orient="records")
    }

    excluded: set[str] = set()
    for path in paths:
        if not path.exists():
            print(f"  manifest not found, skipping: {path}")
            continue
        with open(path, newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        found = 0
        for row in rows:
            relative = (row.get("relative_path") or "").strip().lower()
            image_uid = by_path.get(relative)
            if image_uid:
                excluded.add(image_uid)
                found += 1
        print(f"  {path.name}: {found} of {len(rows)} matched")

    return excluded


def stratified_draw(
    candidates: pd.DataFrame,
    quality_bands: dict[str, str],
    total: int,
    seed: int,
) -> list[dict]:
    """Draw images spread across collection and quality band."""
    rng = random.Random(seed)

    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in candidates.to_dict(orient="records"):
        band = quality_bands.get(row["image_uid"], "unknown")
        strata[(row["collection"], band)].append(row)

    for members in strata.values():
        rng.shuffle(members)

    keys = sorted(strata)
    selection: list[dict] = []
    position = 0

    # Draw in rotation so that every stratum contributes before any is exhausted.
    while len(selection) < total and any(strata[key] for key in keys):
        key = keys[position % len(keys)]
        if strata[key]:
            row = strata[key].pop()
            row["quality_band"] = quality_bands.get(row["image_uid"], "unknown")
            selection.append(row)
        position += 1

    rng.shuffle(selection)
    return selection


def allocate(
    selection: list[dict], annotators: list[str], shared: int
) -> list[dict]:
    """Assign each image to the shared block or to a single annotator."""
    allocated: list[dict] = []

    for index, row in enumerate(selection, start=1):
        record = dict(row)
        record["index"] = index
        if index <= shared:
            record["block"] = "shared"
            record["annotator"] = "all"
        else:
            position = (index - shared - 1) % len(annotators)
            record["block"] = "exclusive"
            record["annotator"] = annotators[position]
        allocated.append(record)

    return allocated


def short_label(value: str, limit: int = 20) -> str:
    """Return a filename-safe abbreviation."""
    return _UNSAFE.sub("_", value).strip("_")[:limit] or "image"


def write_outputs(
    allocated: list[dict],
    archive: Path,
    destination: Path,
    annotators: list[str],
    copy_images: bool,
) -> None:
    """Write the manifest, per-annotator sheets and image folders."""
    destination.mkdir(parents=True, exist_ok=True)

    manifest = destination / "ground_truth_manifest.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in allocated:
            writer.writerow({field: row.get(field, "") for field in MANIFEST_FIELDS})

    for annotator in annotators:
        assigned = [
            row
            for row in allocated
            if row["block"] == "shared" or row["annotator"] == annotator
        ]
        folder = destination / annotator
        folder.mkdir(exist_ok=True)

        sheet = folder / f"annotations_{annotator}.csv"
        with open(sheet, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=SHEET_FIELDS)
            writer.writeheader()
            for row in assigned:
                record = {field: "" for field in SHEET_FIELDS}
                record.update(
                    {
                        "index": row["index"],
                        "block": row["block"],
                        "annotator": annotator,
                        "image_uid": row["image_uid"],
                        "file_name": row["file_name"],
                    }
                )
                writer.writerow(record)

        if copy_images:
            image_folder = folder / "images"
            image_folder.mkdir(exist_ok=True)
            for row in assigned:
                source = archive / row["relative_path"]
                if not source.exists():
                    continue
                suffix = Path(row["file_name"]).suffix.lower()
                target = image_folder / f"{row['index']:03d}_{short_label(row['block'])}{suffix}"
                shutil.copy2(source, target)

        print(f"  {annotator}: {len(assigned)} images -> {sheet}")

    blocks = Counter(row["block"] for row in allocated)
    collections = Counter(row["collection"] for row in allocated)
    bands = Counter(row.get("quality_band", "unknown") for row in allocated)

    print()
    print(f"Total selected: {len(allocated)}")
    print(f"  shared block: {blocks['shared']}")
    print(f"  exclusive   : {blocks['exclusive']}")
    print()
    print("By collection")
    width = max(len(name) for name in collections)
    for name in sorted(collections):
        print(f"  {name:<{width}}  {collections[name]:>3}")
    print()
    print("By quality band")
    for name in sorted(bands):
        print(f"  {name:<8}  {bands[name]:>3}")
    print()
    print(f"Manifest: {manifest}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Select and allocate the ground-truth annotation set"
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--quality", type=Path, default=None)
    parser.add_argument(
        "--exclude",
        type=Path,
        nargs="*",
        default=[],
        help="manifests of images already used",
    )
    parser.add_argument(
        "--annotators", nargs="+", required=True, help="annotator names"
    )
    parser.add_argument("--total", type=int, default=80)
    parser.add_argument("--shared", type=int, default=30)
    parser.add_argument("--seed", type=int, default=113)
    parser.add_argument("--output", type=Path, default=Path("data/ground_truth"))
    parser.add_argument("--no-copy", action="store_true")
    args = parser.parse_args(argv)

    archive = args.archive.expanduser().resolve()
    if not archive.is_dir():
        print(f"Archive directory not found: {archive}")
        return 1

    if args.shared >= args.total:
        print("The shared block must be smaller than the total")
        return 1

    index = load_index(args.index)
    print(f"Images in index: {len(index)}")

    print("Excluding images already used:")
    excluded = load_excluded(list(args.exclude), index)
    print(f"  total excluded: {len(excluded)}")

    quality_bands = load_quality(args.quality, index)
    print(f"Quality bands available: {len(quality_bands)}")

    candidates = index[~index["image_uid"].isin(excluded)]
    print(f"Candidates: {len(candidates)}")
    print()

    if len(candidates) < args.total:
        print(f"Only {len(candidates)} candidates remain; reduce --total")
        return 1

    selection = stratified_draw(candidates, quality_bands, args.total, args.seed)
    allocated = allocate(selection, args.annotators, args.shared)

    write_outputs(
        allocated,
        archive,
        args.output.expanduser().resolve(),
        args.annotators,
        copy_images=not args.no_copy,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())