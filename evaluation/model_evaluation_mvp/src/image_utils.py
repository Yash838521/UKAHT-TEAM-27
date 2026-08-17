import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image  

from config import IMAGE_DIR, SUPPORTED_IMAGE_TYPES


@dataclass
class ImageRecord:
    image_uid: str
    path: Path
    relative_path: str

    @property
    def file_name(self) -> str:
        return self.path.name


def find_images() -> list[ImageRecord]:
    records = []
    paths = sorted(
        (
            path
            for path in IMAGE_DIR.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_TYPES
        ),
        key=lambda path: str(path).lower(),
    )

    for path in paths:
        relative_path = path.relative_to(IMAGE_DIR).as_posix()
        image_uid = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]
        records.append(ImageRecord(image_uid, path, relative_path))
    return records


def open_image(path: Path) -> Image.Image:
    image = Image.open(path)
    return image.convert("RGB")

