from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from tqdm import tqdm

from ukaht.config import MODEL_CACHE_DIR, OUTPUT_DIR, PipelineConfig
from ukaht.io_utils import (
    ImageRecord,
    atomic_save_npy,
    atomic_write_csv,
    clear_error,
    get_file_state,
    load_errors,
    load_manifest,
    new_manifest_row,
    open_image,
    record_error,
    save_errors,
    save_manifest,
    update_file_state,
    utc_now,
)


EMBEDDING_FILE = OUTPUT_DIR / "clip_embeddings.npy"
INDEX_FILE = OUTPUT_DIR / "clip_index.csv"


def get_device() -> torch.device:
    return torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


def move_to_device(inputs, device: torch.device):
    return {name: value.to(device) for name, value in inputs.items()}


def load_saved_vectors() -> dict[str, np.ndarray]:
    if not EMBEDDING_FILE.exists() and not INDEX_FILE.exists():
        return {}
    if not EMBEDDING_FILE.exists() or not INDEX_FILE.exists():
        raise RuntimeError("The CLIP embedding file and index file exist together.")

    matrix = np.load(EMBEDDING_FILE)
    index = pd.read_csv(INDEX_FILE, dtype={"image_uid": str})
    if len(matrix) != len(index):
        raise RuntimeError("CLIP embedding and index row counts do not match.")

    vectors = {}
    for row in index.to_dict(orient="records"):
        row_index = int(row["row_index"])
        vectors[str(row["image_uid"])] = matrix[row_index].astype(np.float32)
    return vectors


def save_clip_checkpoint(
    records: list[ImageRecord],
    vectors: dict[str, np.ndarray],
    manifest: dict[str, dict],
    model_name: str,
) -> tuple[np.ndarray, pd.DataFrame]:
    rows = []
    ordered_vectors = []

    for record in records:
        vector = vectors.get(record.image_uid)
        if vector is None:
            continue
        manifest_row = manifest.get(record.image_uid, {})
        rows.append(
            {
                "row_index": len(rows),
                "image_uid": record.image_uid,
                "file_name": record.file_name,
                "relative_path": record.relative_path,
                "file_hash": manifest_row.get("file_hash", ""),
                "model": model_name,
            }
        )
        ordered_vectors.append(vector.astype(np.float32))

    if not ordered_vectors:
        for path in [EMBEDDING_FILE, INDEX_FILE]:
            if path.exists():
                path.unlink()
        return np.empty((0, 0), dtype=np.float32), pd.DataFrame()

    matrix = np.vstack(ordered_vectors).astype(np.float32)
    index = pd.DataFrame(rows)
    atomic_save_npy(matrix, EMBEDDING_FILE)
    atomic_write_csv(index, INDEX_FILE)
    return matrix, index


def run_clip(config: PipelineConfig, records: list[ImageRecord]) -> None:
    from transformers import CLIPModel, CLIPProcessor

    manifest = load_manifest()
    errors = load_errors()
    saved_vectors = load_saved_vectors()
    current_vectors = {}
    pending = []

    for record in records:
        previous = manifest.get(record.image_uid)
        previous_hash = str(previous.get("clip_file_hash", "")) if previous else ""
        row = new_manifest_row(record, previous)
        manifest[record.image_uid] = row

        try:
            state = get_file_state(record, previous)
            unchanged = (
                previous_hash == state.file_hash
                and row.get("clip_status") == "complete"
                and row.get("clip_model") == config.clip_model
                and record.image_uid in saved_vectors
            )
            update_file_state(row, state)
        except Exception as error:
            row["clip_status"] = "failed"
            row["clip_model"] = config.clip_model
            row["updated_at"] = utc_now()
            record_error(errors, record, "CLIP", error)
            continue

        if unchanged:
            current_vectors[record.image_uid] = saved_vectors[record.image_uid]
        else:
            row["clip_status"] = "pending"
            row["clip_model"] = config.clip_model
            pending.append(record)

    device = get_device()
    print(f"CLIP device: {device}")
    print(f"CLIP images already complete: {len(current_vectors)}")
    print(f"CLIP images to process: {len(pending)}")

    processor: Any = CLIPProcessor.from_pretrained(
        config.clip_model,
        cache_dir=MODEL_CACHE_DIR,
    )
    model: Any = CLIPModel.from_pretrained(
        config.clip_model,
        cache_dir=MODEL_CACHE_DIR,
    )
    model = model.to(device)
    model.eval()

    for start in tqdm(
        range(0, len(pending), config.clip_batch_size),
        desc="CLIP batches",
    ):
        batch_records = pending[start : start + config.clip_batch_size]
        opened_images = []
        ready_records = []

        for record in batch_records:
            try:
                opened_images.append(open_image(record.path))
                ready_records.append(record)
            except Exception as error:
                row = manifest[record.image_uid]
                row["clip_status"] = "failed"
                row["updated_at"] = utc_now()
                current_vectors.pop(record.image_uid, None)
                record_error(errors, record, "CLIP", error)

        if ready_records:
            try:
                inputs = move_to_device(
                    processor(images=opened_images, return_tensors="pt"),
                    device,
                )
                with torch.no_grad():
                    features = model.get_image_features(**inputs)
                    features = features / features.norm(dim=-1, keepdim=True)
                vectors = features.cpu().numpy().astype(np.float32)

                for record, vector in zip(ready_records, vectors):
                    current_vectors[record.image_uid] = vector
                    row = manifest[record.image_uid]
                    row["clip_status"] = "complete"
                    row["clip_model"] = config.clip_model
                    row["clip_file_hash"] = row["file_hash"]
                    row["updated_at"] = utc_now()
                    clear_error(errors, record.image_uid, "CLIP")
            except Exception as error:
                for record in ready_records:
                    row = manifest[record.image_uid]
                    row["clip_status"] = "failed"
                    row["updated_at"] = utc_now()
                    current_vectors.pop(record.image_uid, None)
                    record_error(errors, record, "CLIP", error)
            finally:
                for image in opened_images:
                    image.close()

        save_clip_checkpoint(records, current_vectors, manifest, config.clip_model)
        save_manifest(records, manifest)
        save_errors(errors)

    _, index = save_clip_checkpoint(
        records, current_vectors, manifest, config.clip_model
    )
    save_manifest(records, manifest)
    save_errors(errors)
    print(f"CLIP embeddings available: {len(index)}")
