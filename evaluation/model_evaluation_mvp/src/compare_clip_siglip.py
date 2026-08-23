import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from tqdm import tqdm
from transformers import AutoModel, AutoProcessor


REPO_DIR = Path(__file__).resolve().parents[3]
PIPELINE_SRC_DIR = REPO_DIR / "pipeline" / "src"
if str(PIPELINE_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC_DIR))

from ukaht.tagging import vocabulary as vocab
from ukaht.tagging.calibration import (
    MULTI_LABEL_FACETS,
    SWEEP_START,
    SWEEP_STEP,
    SWEEP_STOP,
    evaluate_argmax,
    load_annotations,
    score_facet,
)
from ukaht.tagging.cross_validation import (
    SINGLE_LABEL_FACETS,
    cross_validate_facet,
)

from config import MODEL_NAMES, OUTPUT_DIR, SUPPORTED_IMAGE_TYPES


ARGMAX_FACETS = ("scene_type", "shot_type")
SIGLIP_SWEEP_START = -1.0
SIGLIP_SWEEP_STOP = 1.0
SIGLIP_SWEEP_STEP = 0.005
REFERENCE_FILE = REPO_DIR / "data" / "ground_truth" / "reference.csv"
THRESHOLD_FILE = REPO_DIR / "pipeline" / "config" / "vocabulary_thresholds.json"


def get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def move_to_device(values, device: str):
    return {name: value.to(device) for name, value in values.items()}


def split_values(value: object) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def load_reference(path: Path, archive: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not path.exists():
        raise FileNotFoundError(f"Reference file not found: {path}")

    reference = pd.read_csv(path, dtype=str).fillna("")
    required = {"image_uid", "file_name", "relative_path", *vocab.all_prompts()}
    missing_columns = sorted(required - set(reference.columns))
    if missing_columns:
        raise ValueError(
            "Reference file is missing columns: " + ", ".join(missing_columns)
        )

    if reference["image_uid"].duplicated().any():
        raise ValueError("Reference file contains duplicate image identifiers.")

    records = []
    missing_images = []
    for row_index, row in enumerate(reference.to_dict(orient="records")):
        image_path = archive / row["relative_path"]
        if not image_path.exists() or image_path.suffix.lower() not in SUPPORTED_IMAGE_TYPES:
            missing_images.append(row["relative_path"])
            continue
        records.append(
            {
                "image_uid": row["image_uid"],
                "file_name": row["file_name"],
                "relative_path": row["relative_path"],
                "image_path": image_path,
                "row_index": row_index,
            }
        )

    if missing_images:
        preview = ", ".join(missing_images[:5])
        raise FileNotFoundError(
            f"{len(missing_images)} reference image(s) could not be found. "
            f"First missing path(s): {preview}"
        )

    return reference, pd.DataFrame(records)


def validate_reference_terms(reference: pd.DataFrame) -> None:
    problems = []
    for facet_key in vocab.all_prompts():
        allowed = set(vocab.facet(facet_key).keys)
        for row in reference.to_dict(orient="records"):
            for term in split_values(row.get(facet_key)):
                if term not in allowed:
                    problems.append(
                        f"{str(row['image_uid'])[:8]}: {facet_key} = {term}"
                    )

    if problems:
        raise ValueError(
            "Reference file contains terms outside vocabulary "
            f"v{vocab.VERSION}: " + "; ".join(problems[:10])
        )


def load_thresholds(path: Path) -> dict[str, float]:
    if not path.exists():
        raise FileNotFoundError(f"Threshold file not found: {path}")
    with path.open(encoding="utf-8") as file:
        return {key: float(value) for key, value in json.load(file).items()}


def load_model(model_key: str, device: str):
    model_name = MODEL_NAMES[model_key]
    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(device)
    model.eval()
    return model, processor


def normalise(features: torch.Tensor) -> torch.Tensor:
    return features / features.norm(dim=-1, keepdim=True)


def encode_images(model, processor, index: pd.DataFrame, device: str, label: str):
    rows = []
    for record in tqdm(
        index.to_dict(orient="records"),
        desc=f"{label} image embeddings",
    ):
        with Image.open(record["image_path"]) as source:
            image = source.convert("RGB")
            inputs = processor(images=image, return_tensors="pt")
        inputs = move_to_device(inputs, device)
        with torch.no_grad():
            features = model.get_image_features(**inputs)
        rows.append(normalise(features).cpu().numpy()[0])
    return np.asarray(rows, dtype="float32")


def encode_prompts(model, processor, device: str, model_key: str):
    encoded = {}
    for facet_key, prompt_map in vocab.all_prompts().items():
        keys = list(prompt_map)
        padding = "max_length" if model_key == "siglip" else True
        inputs = processor(
            text=[prompt_map[key] for key in keys],
            padding=padding,
            truncation=True,
            return_tensors="pt",
        )
        inputs = move_to_device(inputs, device)
        with torch.no_grad():
            features = model.get_text_features(**inputs)
        vectors = normalise(features).cpu().numpy().astype("float32")
        encoded[facet_key] = (keys, vectors)
    return encoded


def evaluate_argmax_facets(
    model_name: str,
    annotations: pd.DataFrame,
    embeddings: np.ndarray,
    prompts,
) -> tuple[list[dict], list[dict]]:
    metric_rows = []
    prediction_rows = []

    for facet_key in ARGMAX_FACETS:
        rows = [
            row
            for row in annotations.to_dict(orient="records")
            if str(row.get(facet_key, "")).strip()
        ]
        positions = [int(row["row_index"]) for row in rows]
        keys, scores = score_facet(embeddings, positions, facet_key, prompts)
        truth = [str(row[facet_key]).strip() for row in rows]
        accuracy, _, _ = evaluate_argmax(truth, keys, scores)

        metric_rows.append(
            {
                "model": model_name,
                "facet": facet_key,
                "method": "argmax",
                "images_evaluated": len(rows),
                "support": len(rows),
                "threshold": "",
                "threshold_sd": "",
                "project_threshold": "",
                "precision": "",
                "recall": "",
                "f1": "",
                "accuracy": round(accuracy, 4),
                "uniform_f1": "",
                "vocabulary_version": vocab.VERSION,
            }
        )

        for row, expected, row_scores in zip(rows, truth, scores, strict=False):
            predicted = keys[int(np.argmax(row_scores))]
            prediction_rows.append(
                {
                    "image_uid": row["image_uid"],
                    "file_name": row["file_name"],
                    "model": model_name,
                    "facet": facet_key,
                    "expected": expected,
                    "predicted": predicted,
                    "correct": predicted == expected,
                }
            )

    return metric_rows, prediction_rows


def evaluate_threshold_facets(
    model_name: str,
    annotations: pd.DataFrame,
    embeddings: np.ndarray,
    prompts,
    thresholds: dict[str, float],
) -> list[dict]:
    metric_rows = []
    facets = SINGLE_LABEL_FACETS + MULTI_LABEL_FACETS

    if model_name == "SIGLIP":
        sweep_start = SIGLIP_SWEEP_START
        sweep_stop = SIGLIP_SWEEP_STOP
        sweep_step = SIGLIP_SWEEP_STEP
        candidates = np.arange(
            sweep_start,
            sweep_stop + sweep_step,
            sweep_step,
        )
    else:
        sweep_start = SWEEP_START
        sweep_stop = SWEEP_STOP
        sweep_step = SWEEP_STEP
        candidates = None

    for facet_key in facets:
        if facet_key not in prompts:
            continue
        project_threshold = thresholds.get(facet_key, 0.24)
        result = cross_validate_facet(
            annotations,
            embeddings,
            facet_key,
            prompts,
            project_threshold,
            candidates,
        )
        if result is None:
            continue
        metric_rows.append(
            {
                "model": model_name,
                "facet": facet_key,
                "method": "leave_one_out_threshold",
                "images_evaluated": result.folds,
                "support": result.support,
                "threshold": round(result.mean_threshold, 4),
                "threshold_sd": round(result.threshold_spread, 4),
                "sweep_start": sweep_start,
                "sweep_stop": sweep_stop,
                "sweep_step": sweep_step,
                "project_threshold": project_threshold,
                "precision": round(result.precision, 4),
                "recall": round(result.recall, 4),
                "f1": round(result.f1, 4),
                "accuracy": "",
                "uniform_f1": round(result.uniform_f1, 4),
                "vocabulary_version": vocab.VERSION,
            }
        )

    return metric_rows


def paired_argmax_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    clip = predictions[predictions["model"] == "CLIP"][
        ["image_uid", "facet", "correct"]
    ].rename(columns={"correct": "clip_correct"})
    siglip = predictions[predictions["model"] == "SIGLIP"][
        ["image_uid", "facet", "correct"]
    ].rename(columns={"correct": "siglip_correct"})
    paired = clip.merge(siglip, on=["image_uid", "facet"], how="inner")

    rows = []
    for facet_key, group in paired.groupby("facet", sort=False):
        rows.append(
            {
                "facet": facet_key,
                "images_compared": len(group),
                "both_correct": int(
                    (group["clip_correct"] & group["siglip_correct"]).sum()
                ),
                "clip_only_correct": int(
                    (group["clip_correct"] & ~group["siglip_correct"]).sum()
                ),
                "siglip_only_correct": int(
                    (~group["clip_correct"] & group["siglip_correct"]).sum()
                ),
                "both_incorrect": int(
                    (~group["clip_correct"] & ~group["siglip_correct"]).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare CLIP and SigLIP on the shared UKAHT reference set"
    )
    parser.add_argument(
        "--archive",
        type=Path,
        required=True,
        help="folder containing the full image archive",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=REFERENCE_FILE,
        help="shared annotated reference CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help="folder for the comparison CSV files",
    )
    args = parser.parse_args()

    problems = vocab.validate()
    if problems:
        raise ValueError("Vocabulary validation failed: " + "; ".join(problems))

    archive = args.archive.expanduser().resolve()
    if not archive.exists():
        print(f"Image archive not found: {archive}")
        return 1

    try:
        reference, index = load_reference(args.reference, archive)
        validate_reference_terms(reference)
        thresholds = load_thresholds(THRESHOLD_FILE)
        annotations = load_annotations(args.reference, Path(), index)
    except (FileNotFoundError, ValueError) as error:
        print(error)
        return 1

    if annotations.empty or len(annotations) != len(reference):
        print(
            f"Only {len(annotations)} of {len(reference)} reference rows were matched."
        )
        return 1

    device = get_device()
    print(f"Vocabulary version: {vocab.VERSION}")
    print(f"Reference images: {len(reference)}")
    print(f"Device: {device}")

    metric_rows = []
    prediction_rows = []

    for model_key in ("clip", "siglip"):
        model_name = model_key.upper()
        model, processor = load_model(model_key, device)
        embeddings = encode_images(model, processor, index, device, model_name)
        prompts = encode_prompts(model, processor, device, model_key)

        argmax_metrics, argmax_predictions = evaluate_argmax_facets(
            model_name,
            annotations,
            embeddings,
            prompts,
        )
        metric_rows.extend(argmax_metrics)
        prediction_rows.extend(argmax_predictions)
        metric_rows.extend(
            evaluate_threshold_facets(
                model_name,
                annotations,
                embeddings,
                prompts,
                thresholds,
            )
        )

        del model
        if device == "cuda":
            torch.cuda.empty_cache()

    metrics = pd.DataFrame(metric_rows)
    predictions = pd.DataFrame(prediction_rows)
    paired = paired_argmax_summary(predictions)

    args.output.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.output / "model_comparison_metrics.csv", index=False)
    predictions.to_csv(
        args.output / "clip_siglip_argmax_predictions.csv",
        index=False,
    )
    paired.to_csv(
        args.output / "clip_siglip_paired_comparison.csv",
        index=False,
    )

    print("Evaluation completed")
    print(f"Metrics: {args.output / 'model_comparison_metrics.csv'}")
    print(f"Paired comparison: {args.output / 'clip_siglip_paired_comparison.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
