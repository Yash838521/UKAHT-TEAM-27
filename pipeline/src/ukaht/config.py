import json
import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_DIR / "config" / "settings.json"
OUTPUT_DIR = PROJECT_DIR / "outputs"
MODEL_CACHE_DIR = PROJECT_DIR / ".model_cache"

os.environ.setdefault("HF_HOME", str(MODEL_CACHE_DIR))


@dataclass
class PipelineConfig:
    image_directory: Path
    inventory_file: Path
    clip_model: str
    florence_model: str
    clip_batch_size: int
    florence_checkpoint_interval: int
    florence_max_new_tokens: int
    florence_num_beams: int
    inventory_columns: dict[str, str]


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_DIR / path


def load_config() -> PipelineConfig:
    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    return PipelineConfig(
        image_directory=resolve_project_path(settings["image_directory"]),
        inventory_file=resolve_project_path(settings["inventory_file"]),
        clip_model=settings["clip_model"],
        florence_model=settings["florence_model"],
        clip_batch_size=max(1, int(settings["clip_batch_size"])),
        florence_checkpoint_interval=max(
            1, int(settings["florence_checkpoint_interval"])
        ),
        florence_max_new_tokens=max(1, int(settings["florence_max_new_tokens"])),
        florence_num_beams=max(1, int(settings["florence_num_beams"])),
        inventory_columns=settings["inventory_columns"],
    )
