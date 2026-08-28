"""Validation of the controlled vocabulary against unseen images.

A second sample is drawn using a different seed and excluding the images used
during vocabulary development. Terms are assigned by hand, and coverage is then
measured per facet to identify gaps, unused terms and ambiguous cases.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

from ukaht.tagging import vocabulary as vocab

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".webp"}

THUMBNAIL_SIZE = (320, 320)
SHEET_COLUMNS = 4
SHEET_ROWS = 4
PADDING = 10
LABEL_HEIGHT = 22

REQUIRED_FACETS = ("scene_type", "people", "shot_type")
CONDITIONAL_FACETS = {"room": "interior", "structure": "exterior"}
OPEN_FACETS = ("orientation", "activity", "nature", "condition")

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

_UNSAFE = re.compile(r"[^A-Za-z0-9]+")


def find_images(root: Path) -> list[Path]:
    """Return every image file beneath a root directory."""
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def load_excluded(manifest: Path | None) -> set[str]:
    """Return relative paths already used during vocabulary development."""
    if manifest is None or not manifest.exists():
        return set()
    with open(manifest, newline="", encoding="utf-8") as handle:
        return {row["relative_path"] for row in csv.DictReader(handle)}


def select(
    root: Path, paths: list[Path], excluded: set[str], per_group: int, seed: int
) -> list[tuple[str, Path]]:
    """Draw images from each directory, skipping any already used."""
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in paths:
        if str(path.relative_to(root)) in excluded:
            continue
        groups[str(path.parent.relative_to(root))].append(path)

    rng = random.Random(seed)
    selection: list[tuple[str, Path]] = []
    for group in sorted(groups):
        members = sorted(groups[group])
        for path in rng.sample(members, min(per_group, len(members))):
            selection.append((group, path))
    return selection


def short_label(group: str, limit: int = 24) -> str:
    """Return a filename-safe abbreviation of a group name."""
    tail = group.split("/")[-1] if group != "." else "root"
    return _UNSAFE.sub("_", tail).strip("_")[:limit] or "group"


def build_contact_sheets(
    entries: list[tuple[int, str, Path]], destination: Path
) -> list[Path]:
    """Render the selection as grids of numbered thumbnails."""
    per_sheet = SHEET_COLUMNS * SHEET_ROWS
    cell_width = THUMBNAIL_SIZE[0] + PADDING * 2
    cell_height = THUMBNAIL_SIZE[1] + PADDING * 2 + LABEL_HEIGHT
    sheets: list[Path] = []

    for start in range(0, len(entries), per_sheet):
        block = entries[start : start + per_sheet]
        sheet = Image.new(
            "RGB",
            (cell_width * SHEET_COLUMNS, cell_height * SHEET_ROWS),
            (255, 255, 255),
        )
        draw = ImageDraw.Draw(sheet)

        for position, (index, group, path) in enumerate(block):
            column = position % SHEET_COLUMNS
            row = position // SHEET_COLUMNS
            x = column * cell_width + PADDING
            y = row * cell_height + PADDING

            draw.text((x, y), f"{index:03d}  {short_label(group, 30)}", fill=(0, 0, 0))
            try:
                with Image.open(path) as source:
                    thumbnail = source.convert("RGB")
                    thumbnail.thumbnail(THUMBNAIL_SIZE)
            except Exception:
                draw.text((x, y + LABEL_HEIGHT + 20), "unreadable", fill=(180, 0, 0))
                continue
            sheet.paste(thumbnail, (x, y + LABEL_HEIGHT))

        target = destination / f"validation_sheet_{start // per_sheet + 1:02d}.jpg"
        sheet.save(target, quality=88)
        sheets.append(target)

    return sheets


def write_reference(destination: Path) -> Path:
    """Write a list of permitted terms for each facet."""
    path = destination / "term_reference.txt"
    lines: list[str] = []

    for facet in vocab.FACETS:
        if facet.key == "site":
            continue
        scope = f"  (applies to {', '.join(facet.applies_to)})" if facet.applies_to else ""
        rule = "choose one" if facet.exclusive else "choose any number, separate with |"
        lines.append(f"{facet.label}{scope} — {rule}")
        for term in facet.terms:
            note = f"   [{term.note}]" if term.note else ""
            lines.append(f"    {term.key:<20} {term.label}{note}")
        lines.append("")

    lines.append("Object tags — choose any number, separate with |")
    for group, tags in vocab.OBJECT_GROUPS.items():
        lines.append(f"    {group}")
        lines.append(f"      {', '.join(tags)}")
    lines.append("")
    lines.append("Where no term fits, leave the column empty and record what was")
    lines.append("needed in missing_terms. Where two terms both seem to apply,")
    lines.append("choose one and record the difficulty in hesitation.")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export(
    selection: list[tuple[str, Path]],
    root: Path,
    destination: Path,
    copy_images: bool,
) -> None:
    """Write the annotation sheet, term reference and visual aids."""
    destination.mkdir(parents=True, exist_ok=True)
    entries = [(i, g, p) for i, (g, p) in enumerate(selection, start=1)]

    manifest = destination / "validation_sample.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["index", "group", "relative_path", "filename"])
        for index, group, path in entries:
            writer.writerow([index, group, str(path.relative_to(root)), path.name])

    sheet = destination / "validation_annotations.csv"
    with open(sheet, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(SHEET_FIELDS)
        for index, group, path in entries:
            row = [index, group, path.name] + [""] * (len(SHEET_FIELDS) - 3)
            writer.writerow(row)

    if copy_images:
        image_dir = destination / "images"
        image_dir.mkdir(exist_ok=True)
        for index, group, path in entries:
            target = image_dir / f"{index:03d}_{short_label(group)}{path.suffix.lower()}"
            shutil.copy2(path, target)

    sheets = build_contact_sheets(entries, destination)
    reference = write_reference(destination)

    counts = Counter(group for _index, group, _path in entries)
    print(f"\nSelected {len(entries)} images from {len(counts)} groups\n")
    width = max(len(group) for group in counts)
    for group in sorted(counts):
        print(f"  {group:<{width}}  {counts[group]:>3}")

    print()
    print(f"Annotation sheet: {sheet}")
    print(f"Term reference:   {reference}")
    print(f"Contact sheets:   {len(sheets)}")


def _values(cell: str) -> list[str]:
    return [part.strip() for part in cell.split("|") if part.strip()]


def analyse(sheet_path: Path) -> str:
    """Measure coverage, unused terms and problem cases across the sheet."""
    with open(sheet_path, newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if any(row.values())]

    annotated = [row for row in rows if row.get("scene_type", "").strip()]
    if not annotated:
        return "No annotated rows found."

    total = len(annotated)
    lines = [f"Annotated images: {total} of {len(rows)}", ""]

    lines.append("Coverage by facet")
    for facet in vocab.FACETS:
        if facet.key == "site":
            continue
        applicable = annotated
        if facet.key in CONDITIONAL_FACETS:
            scene = CONDITIONAL_FACETS[facet.key]
            applicable = [r for r in annotated if r.get("scene_type", "").strip() == scene]
        if not applicable:
            lines.append(f"  {facet.label:<22} no applicable images")
            continue
        filled = sum(1 for r in applicable if _values(r.get(facet.key, "")))
        share = filled / len(applicable)
        flag = "" if share == 1.0 or facet.key in OPEN_FACETS else "   <-- incomplete"
        lines.append(
            f"  {facet.label:<22} {filled:>3}/{len(applicable):<3} ({share:5.1%}){flag}"
        )

    lines.append("")
    lines.append("Term usage")
    for facet in vocab.FACETS:
        if facet.key == "site":
            continue
        used = Counter()
        for row in annotated:
            used.update(_values(row.get(facet.key, "")))
        unknown = [term for term in used if term not in facet.keys]
        unused = [term for term in facet.keys if term not in used]
        lines.append(f"  {facet.label}")
        for term, count in used.most_common():
            marker = "  (not in vocabulary)" if term in unknown else ""
            lines.append(f"    {term:<22} {count:>3}{marker}")
        if unused:
            lines.append(f"    unused: {', '.join(unused)}")

    tags = Counter()
    for row in annotated:
        tags.update(_values(row.get("object_tags", "")))
    known = set(vocab.object_tags())
    lines.append("")
    lines.append("Object tags")
    lines.append(f"  distinct tags applied: {len(tags)} of {len(known)} available")
    outside = [tag for tag in tags if tag not in known]
    if outside:
        lines.append(f"  outside the vocabulary: {', '.join(sorted(outside))}")
    if tags:
        lines.append("  most frequent: " + ", ".join(t for t, _ in tags.most_common(10)))

    missing = [(r["index"], r["missing_terms"]) for r in annotated if r.get("missing_terms", "").strip()]
    lines.append("")
    lines.append(f"Images needing a term that does not exist: {len(missing)}")
    for index, text in missing:
        lines.append(f"  {index:>3}  {text}")

    hesitation = [(r["index"], r["hesitation"]) for r in annotated if r.get("hesitation", "").strip()]
    lines.append("")
    lines.append(f"Images with an ambiguous choice: {len(hesitation)}")
    for index, text in hesitation:
        lines.append(f"  {index:>3}  {text}")

    per_image = [
        sum(len(_values(row.get(f.key, ""))) for f in vocab.FACETS if f.key != "site")
        + len(_values(row.get("object_tags", "")))
        for row in annotated
    ]
    lines.append("")
    lines.append(
        f"Terms per image: min {min(per_image)}, "
        f"mean {sum(per_image) / len(per_image):.1f}, max {max(per_image)}"
    )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the vocabulary on unseen images")
    subparsers = parser.add_subparsers(dest="command", required=True)

    draw = subparsers.add_parser("draw", help="select images and build the annotation sheet")
    draw.add_argument("--archive", type=Path, required=True)
    draw.add_argument("--output", type=Path, default=Path("data/interim/validation_sample"))
    draw.add_argument("--exclude", type=Path, default=None, help="earlier sample manifest")
    draw.add_argument("--per-group", type=int, default=3)
    draw.add_argument("--seed", type=int, default=91)
    draw.add_argument("--no-copy", action="store_true")

    report = subparsers.add_parser("report", help="measure coverage from a completed sheet")
    report.add_argument(
        "--sheet",
        type=Path,
        default=Path("data/interim/validation_sample/validation_annotations.csv"),
    )

    args = parser.parse_args(argv)

    if args.command == "draw":
        archive = args.archive.expanduser().resolve()
        if not archive.is_dir():
            print(f"Directory not found: {archive}", file=sys.stderr)
            return 1
        paths = find_images(archive)
        excluded = load_excluded(args.exclude)
        print(f"Found {len(paths)} images; excluding {len(excluded)} already used")
        selection = select(archive, paths, excluded, args.per_group, args.seed)
        export(selection, archive, args.output.expanduser().resolve(), not args.no_copy)
        return 0

    sheet = args.sheet.expanduser().resolve()
    if not sheet.exists():
        print(f"Sheet not found: {sheet}", file=sys.stderr)
        return 1
    print(analyse(sheet))
    return 0


if __name__ == "__main__":
    sys.exit(main())