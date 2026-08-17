from pathlib import Path
from typing import Any

import pandas as pd
import torch
from tqdm import tqdm

from ukaht.config import MODEL_CACHE_DIR, OUTPUT_DIR, PipelineConfig
from ukaht.io_utils import (
    ImageRecord,
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


DESCRIPTION_COLUMNS = ["image_uid", "file_name", "description"]


def load_descriptions(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    table = pd.read_csv(path, dtype=str).fillna("")
    missing = set(DESCRIPTION_COLUMNS) - set(table.columns)
    if missing:
        raise ValueError(
            f"{path.name} is missing columns: {', '.join(sorted(missing))}"
        )

    def _to_str(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    return {
        _to_str(row.image_uid).strip(): _to_str(row.description).strip()
        for row in table.itertuples(index=False)
        if row.image_uid is not None
        and _to_str(row.image_uid).strip()
        and _to_str(row.description).strip()
    }


def save_descriptions(
    path: Path,
    records: list[ImageRecord],
    descriptions: dict[str, str],
) -> None:
    rows = []
    for record in records:
        description = descriptions.get(record.image_uid, "").strip()
        if description:
            rows.append(
                {
                    "image_uid": record.image_uid,
                    "file_name": record.file_name,
                    "description": description,
                }
            )

    atomic_write_csv(pd.DataFrame(rows, columns=DESCRIPTION_COLUMNS), path)


def extract_description(result, task: str) -> str:
    if isinstance(result, dict):
        text = result.get(task, "")
        if not text and result:
            text = next(iter(result.values()))
    else:
        text = result

    return " ".join(str(text).strip().split())


def run_florence(config: PipelineConfig, records: list[ImageRecord]) -> None:
    from transformers import AutoModelForCausalLM, AutoProcessor

    output_path = OUTPUT_DIR / "florence_descriptions.csv"
    model_name = config.florence_model
    descriptions = load_descriptions(output_path)
    manifest = load_manifest()
    errors = load_errors()
    pending = []

    current_ids = {record.image_uid for record in records}
    descriptions = {
        uid: text for uid, text in descriptions.items() if uid in current_ids
    }

    for record in records:
        previous = manifest.get(record.image_uid)
        previous_hash = (
            str(previous.get("florence_file_hash", "")) if previous else ""
        )
        row = new_manifest_row(record, previous)
        manifest[record.image_uid] = row

        try:
            state = get_file_state(record, previous)
            unchanged = (
                previous_hash == state.file_hash
                and row.get("florence_status") == "complete"
                and row.get("florence_model") == model_name
                and bool(descriptions.get(record.image_uid, "").strip())
            )
            update_file_state(row, state)
        except Exception as error:
            descriptions.pop(record.image_uid, None)
            row["florence_status"] = "failed"
            row["florence_model"] = model_name
            row["updated_at"] = utc_now()
            record_error(errors, record, "Florence-2", error)
            continue

        if unchanged:
            continue

        descriptions.pop(record.image_uid, None)
        row["florence_status"] = "pending"
        row["florence_model"] = model_name
        pending.append((record, state))

    print(f"Florence-2 images already complete: {len(records) - len(pending)}")
    print(f"Florence-2 images to process: {len(pending)}")

    if not pending:
        save_descriptions(output_path, records, descriptions)
        save_manifest(records, manifest)
        save_errors(errors)
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    data_type = torch.float16 if device == "cuda" else torch.float32
    print(f"Florence-2 device: {device}")

    processor: Any = AutoProcessor.from_pretrained(
        model_name,
        trust_remote_code=True,
        cache_dir=MODEL_CACHE_DIR,
    )
    model: Any = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=data_type,
        cache_dir=MODEL_CACHE_DIR,
    ).to(device)
    model.eval()

    task = "<MORE_DETAILED_CAPTION>"
    completed_since_save = 0

    try:
        for record, state in tqdm(pending, desc="Florence-2 descriptions"):
            try:
                image = open_image(record.path)
                try:
                    inputs = processor(text=task, images=image, return_tensors="pt")
                    inputs = {
                        name: value.to(device, dtype=data_type)
                        if name == "pixel_values"
                        else value.to(device)
                        for name, value in inputs.items()
                    }

                    with torch.no_grad():
                        generated_ids = model.generate(
                            input_ids=inputs["input_ids"],
                            pixel_values=inputs["pixel_values"],
                            max_new_tokens=config.florence_max_new_tokens,
                            num_beams=config.florence_num_beams,
                            do_sample=False,
                        )

                    generated_text = processor.batch_decode(
                        generated_ids,
                        skip_special_tokens=False,
                    )[0]
                    parsed = processor.post_process_generation(
                        generated_text,
                        task=task,
                        image_size=(image.width, image.height),
                    )
                finally:
                    image.close()

                description = extract_description(parsed, task)
                if not description:
                    raise ValueError("Florence-2 returned an empty description")

                descriptions[record.image_uid] = description
                row = manifest[record.image_uid]
                row["florence_status"] = "complete"
                row["florence_model"] = model_name
                row["florence_file_hash"] = state.file_hash
                row["updated_at"] = utc_now()
                clear_error(errors, record.image_uid, "Florence-2")
            except Exception as error:
                descriptions.pop(record.image_uid, None)
                row = manifest[record.image_uid]
                row["florence_status"] = "failed"
                row["florence_model"] = model_name
                row["updated_at"] = utc_now()
                record_error(errors, record, "Florence-2", error)

            completed_since_save += 1
            if completed_since_save >= config.florence_checkpoint_interval:
                save_descriptions(output_path, records, descriptions)
                save_manifest(records, manifest)
                save_errors(errors)
                completed_since_save = 0
    finally:
        save_descriptions(output_path, records, descriptions)
        save_manifest(records, manifest)
        save_errors(errors)

    print(f"Florence-2 processed: {len(pending)} image(s).")
