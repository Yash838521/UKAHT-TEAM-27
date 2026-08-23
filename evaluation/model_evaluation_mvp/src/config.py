import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
IMAGE_DIR = PROJECT_DIR / "data" / "sample_images"
OUTPUT_DIR = PROJECT_DIR / "outputs"
CATEGORY_FILE = PROJECT_DIR / "config" / "categories.txt"
QUERY_FILE = PROJECT_DIR / "config" / "search_queries.txt"
MODEL_CACHE_DIR = PROJECT_DIR / ".model_cache"

os.environ.setdefault("HF_HOME", str(MODEL_CACHE_DIR))

MODEL_NAMES = {
    "clip": "openai/clip-vit-base-patch32",
    "blip": "Salesforce/blip-image-captioning-base",
    "florence": "microsoft/Florence-2-base",
    "siglip": "google/siglip-base-patch16-224",
}

SUPPORTED_IMAGE_TYPES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
}


def read_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
