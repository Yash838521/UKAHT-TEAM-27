import csv
from pathlib import Path
import hashlib

from ukaht.config import load_config


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
}


def load_existing_inventory(path: Path) -> list[dict[str, str]]:
    columns = ["image_uid", "relative_path", "file_name"]
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        field_names = reader.fieldnames or []
        missing = set(columns) - set(field_names)
        rows = list(reader)

    if missing:
        raise ValueError(
            f"Existing inventory is missing: {', '.join(sorted(missing))}"
        )
    if len({row["image_uid"] for row in rows}) != len(rows):
        raise ValueError("Existing inventory contains duplicate image_uid values")
    if len({row["relative_path"] for row in rows}) != len(rows):
        raise ValueError("Existing inventory contains duplicate relative_path values")
    return [{column: row[column] for column in columns} for row in rows]


def find_images(image_directory: Path) -> list[Path]:
    if not image_directory.exists():
        raise FileNotFoundError(f"Image folder not found: {image_directory}")

    return sorted(
        path
        for path in image_directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def main() -> int:
    config = load_config()
    inventory_path = config.inventory_file
    existing = load_existing_inventory(inventory_path)
    known_paths = {row["relative_path"] for row in existing}
    images = find_images(config.image_directory)
    new_rows = []

    for image_path in images:
        relative_path = image_path.relative_to(config.image_directory).as_posix()
        if relative_path in known_paths:
            continue

        new_rows.append(
            {
                "image_uid": hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:32],
                "relative_path": relative_path,
                "file_name": image_path.name,
            }
        )

    inventory = existing + new_rows

    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    with inventory_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["image_uid", "relative_path", "file_name"],
        )
        writer.writeheader()
        writer.writerows(inventory)

    print(f"Images found: {len(images)}")
    print(f"New inventory rows: {len(new_rows)}")
    print(f"Total inventory rows: {len(inventory)}")
    print(f"Saved: {inventory_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
