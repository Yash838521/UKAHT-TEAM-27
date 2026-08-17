"""Selection of a stratified viewing sample from the archive.

Images are grouped by the directory that contains them and a fixed number are
drawn from each group using a seeded random process, so that the selection
covers every part of the archive and can be reproduced exactly.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".webp"}

THUMBNAIL_SIZE = (320, 320)
SHEET_COLUMNS = 4
SHEET_ROWS = 4
PADDING = 10
LABEL_HEIGHT = 22

_UNSAFE = re.compile(r"[^A-Za-z0-9]+")


def find_images(root: Path) -> list[Path]:
    """Return every image file beneath a root directory."""
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def group_by_directory(root: Path, paths: list[Path]) -> dict[str, list[Path]]:
    """Group image paths by the directory that contains them."""
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in paths:
        relative_dir = path.parent.relative_to(root)
        groups[str(relative_dir)].append(path)
    return dict(groups)


def select(
    groups: dict[str, list[Path]], per_group: int, seed: int
) -> list[tuple[str, Path]]:
    """Draw a fixed number of images from each group."""
    rng = random.Random(seed)
    selection: list[tuple[str, Path]] = []

    for group in sorted(groups):
        members = sorted(groups[group])
        count = min(per_group, len(members))
        for path in rng.sample(members, count):
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
            origin_x = column * cell_width + PADDING
            origin_y = row * cell_height + PADDING

            draw.text(
                (origin_x, origin_y),
                f"{index:03d}  {short_label(group, 30)}",
                fill=(0, 0, 0),
            )

            try:
                with Image.open(path) as source:
                    thumbnail = source.convert("RGB")
                    thumbnail.thumbnail(THUMBNAIL_SIZE)
            except Exception:
                draw.text(
                    (origin_x, origin_y + LABEL_HEIGHT + 20),
                    "unreadable",
                    fill=(180, 0, 0),
                )
                continue

            sheet.paste(thumbnail, (origin_x, origin_y + LABEL_HEIGHT))

        number = start // per_sheet + 1
        target = destination / f"contact_sheet_{number:02d}.jpg"
        sheet.save(target, quality=88)
        sheets.append(target)

    return sheets


def export(
    selection: list[tuple[str, Path]],
    root: Path,
    destination: Path,
    copy_images: bool,
    contact_sheets: bool,
) -> None:
    """Write the manifest, the coding sheet and the visual aids."""
    destination.mkdir(parents=True, exist_ok=True)
    entries = [
        (index, group, path) for index, (group, path) in enumerate(selection, start=1)
    ]

    manifest = destination / "viewing_sample.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["index", "group", "relative_path", "filename"])
        for index, group, path in entries:
            writer.writerow([index, group, str(path.relative_to(root)), path.name])

    coding_sheet = destination / "coding_notes.csv"
    with open(coding_sheet, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "index",
                "group",
                "filename",
                "what_is_shown",
                "objects_present",
                "setting",
                "people_present",
                "condition_or_damage",
                "candidate_terms",
                "notes",
            ]
        )
        for index, group, path in entries:
            writer.writerow([index, group, path.name, "", "", "", "", "", "", ""])

    if copy_images:
        image_dir = destination / "images"
        image_dir.mkdir(exist_ok=True)
        for index, group, path in entries:
            target = image_dir / f"{index:03d}_{short_label(group)}{path.suffix.lower()}"
            shutil.copy2(path, target)

    if contact_sheets:
        sheets = build_contact_sheets(entries, destination)
        print(f"Contact sheets written: {len(sheets)}")

    counts: dict[str, int] = defaultdict(int)
    for _index, group, _path in entries:
        counts[group] += 1

    print(f"\nSelected {len(entries)} images from {len(counts)} groups\n")
    width = max(len(group) for group in counts)
    for group in sorted(counts):
        print(f"  {group:<{width}}  {counts[group]:>3}")

    print()
    print(f"Manifest:      {manifest}")
    print(f"Coding sheet:  {coding_sheet}")
    if copy_images:
        print(f"Images:        {destination / 'images'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Draw a stratified viewing sample from the archive"
    )
    parser.add_argument("--archive", type=Path, required=True, help="archive root")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/viewing_sample"),
        help="destination directory",
    )
    parser.add_argument(
        "--per-group", type=int, default=4, help="images drawn from each directory"
    )
    parser.add_argument("--seed", type=int, default=27, help="random seed")
    parser.add_argument("--no-copy", action="store_true", help="do not copy files")
    parser.add_argument("--no-sheets", action="store_true", help="skip contact sheets")
    args = parser.parse_args(argv)

    archive = args.archive.expanduser().resolve()
    if not archive.is_dir():
        print(f"Directory not found: {archive}", file=sys.stderr)
        return 1

    paths = find_images(archive)
    if not paths:
        print(f"No image files found under {archive}", file=sys.stderr)
        return 1

    groups = group_by_directory(archive, paths)
    print(f"Found {len(paths)} images across {len(groups)} directories")

    selection = select(groups, args.per_group, args.seed)
    export(
        selection,
        archive,
        args.output.expanduser().resolve(),
        copy_images=not args.no_copy,
        contact_sheets=not args.no_sheets,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())