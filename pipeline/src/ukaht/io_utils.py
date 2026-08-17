import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from ukaht.config import OUTPUT_DIR, PipelineConfig


MANIFEST_FILE = OUTPUT_DIR / "processing_manifest.csv"
ERROR_FILE = OUTPUT_DIR / "processing_errors.csv"

MANIFEST_COLUMNS = [
    "image_uid",
    "file_name",
    "relative_path",
    "file_size_bytes",
    "modified_ns",
    "file_hash",
    "clip_status",
    "clip_model",
    "clip_file_hash",
    "florence_status",
    "florence_model",
    "florence_file_hash",
    "updated_at",
]

ERROR_COLUMNS = [
    "image_uid",
    "file_name",
    "model",
    "error_message",
    "attempted_at",
]


@dataclass
class ImageRecord:
    image_uid: str
    file_name: str
    relative_path: str
    path: Path


@dataclass
class FileState:
    file_size_bytes: int
    modified_ns: int
    file_hash: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_inventory(config: PipelineConfig) -> list[ImageRecord]:
    path = config.inventory_file
    if not path.exists():
        raise FileNotFoundError(f"Inventory file not found: {path}")

    if path.suffix.lower() == ".parquet":
        inventory = pd.read_parquet(path)
    else:
        inventory = pd.read_csv(path, dtype=str)

    columns = config.inventory_columns
    uid_column = columns["image_uid"]
    path_column = columns["relative_path"]
    file_name_column = columns.get("file_name", "file_name")

    missing = [name for name in [uid_column, path_column] if name not in inventory.columns]
    if missing:
        raise ValueError(f"Inventory is missing columns: {', '.join(missing)}")

    if inventory[uid_column].isna().any() or inventory[path_column].isna().any():
        raise ValueError("The inventory contains empty image_uid or relative_path values.")

    inventory[uid_column] = inventory[uid_column].astype(str).str.strip()
    inventory[path_column] = inventory[path_column].astype(str).str.strip()
    if inventory[uid_column].duplicated().any():
        raise ValueError("The inventory contains duplicate image_uid values.")

    records = []
    for row in inventory.to_dict(orient="records"):
        relative_path = str(row[path_column]).replace("\\", "/")
        if not relative_path or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
            raise ValueError(f"Invalid relative_path in inventory: {relative_path}")

        file_name_value = row.get(file_name_column)
        file_name = (
            str(file_name_value)
            if file_name_value is not None and not pd.isna(file_name_value)
            else Path(relative_path).name
        )
        records.append(
            ImageRecord(
                image_uid=str(row[uid_column]),
                file_name=file_name,
                relative_path=relative_path,
                path=config.image_directory / Path(relative_path),
            )
        )
    return records


def load_manifest() -> dict[str, dict]:
    if not MANIFEST_FILE.exists():
        return {}
    frame = pd.read_csv(MANIFEST_FILE, dtype=str).fillna("")
    return {str(row["image_uid"]): row for row in frame.to_dict(orient="records")}


def new_manifest_row(record: ImageRecord, previous: dict | None = None) -> dict:
    row = {column: "" for column in MANIFEST_COLUMNS}
    if previous:
        row.update(previous)
    row.update(
        {
            "image_uid": record.image_uid,
            "file_name": record.file_name,
            "relative_path": record.relative_path,
        }
    )
    return row


def save_manifest(records: list[ImageRecord], manifest: dict[str, dict]) -> None:
    rows = []
    for record in records:
        if record.image_uid in manifest:
            rows.append({column: manifest[record.image_uid].get(column, "") for column in MANIFEST_COLUMNS})
    atomic_write_csv(pd.DataFrame(rows, columns=MANIFEST_COLUMNS), MANIFEST_FILE)


def safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def calculate_hash(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def get_file_state(record: ImageRecord, previous: dict | None) -> FileState:
    stat = record.path.stat()
    old_size = safe_int(previous.get("file_size_bytes")) if previous else None
    old_modified = safe_int(previous.get("modified_ns")) if previous else None
    old_hash = str(previous.get("file_hash", "")) if previous else ""

    if old_hash and old_size == stat.st_size and old_modified == stat.st_mtime_ns:
        file_hash = old_hash
    else:
        file_hash = calculate_hash(record.path)

    return FileState(
        file_size_bytes=stat.st_size,
        modified_ns=stat.st_mtime_ns,
        file_hash=file_hash,
    )


def update_file_state(row: dict, state: FileState) -> None:
    row["file_size_bytes"] = state.file_size_bytes
    row["modified_ns"] = state.modified_ns
    row["file_hash"] = state.file_hash
    row["updated_at"] = utc_now()


def open_image(path: Path) -> Image.Image:
    image = Image.open(path)
    return image.convert("RGB")


def atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def atomic_save_npy(array: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".tmp.npy")
    np.save(temporary, array)
    os.replace(temporary, path)


def load_errors() -> list[dict]:
    if not ERROR_FILE.exists():
        return []
    return pd.read_csv(ERROR_FILE, dtype=str).fillna("").to_dict(orient="records")


def record_error(errors: list[dict], record: ImageRecord, model: str, error: Exception) -> None:
    clear_error(errors, record.image_uid, model)
    errors.append(
        {
            "image_uid": record.image_uid,
            "file_name": record.file_name,
            "model": model,
            "error_message": str(error),
            "attempted_at": utc_now(),
        }
    )


def clear_error(errors: list[dict], image_uid: str, model: str) -> None:
    errors[:] = [
        row
        for row in errors
        if not (row.get("image_uid") == image_uid and row.get("model") == model)
    ]


def save_errors(errors: list[dict]) -> None:
    if errors:
        atomic_write_csv(pd.DataFrame(errors, columns=ERROR_COLUMNS), ERROR_FILE)
    elif ERROR_FILE.exists():
        ERROR_FILE.unlink()
