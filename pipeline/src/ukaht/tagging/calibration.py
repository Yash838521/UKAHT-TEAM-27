"""Calibration of similarity thresholds for vocabulary term assignment.

Term assignment compares an image embedding against a text embedding of each
vocabulary prompt and accepts terms whose similarity exceeds a threshold. A
single threshold applied across all facets is unlikely to be optimal, because
similarity values are not comparable between prompt sets of different length and
specificity.

This module measures assignment quality against human annotation, sweeps the
threshold range for each facet independently, and reports the value that
maximises the balance of precision and recall.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ukaht.tagging import vocabulary as vocab

EXCLUSIVE_FACETS = ("scene_type", "shot_type", "people")
MULTI_LABEL_FACETS = ("structure", "orientation", "activity", "nature", "condition")
SINGLE_OPTIONAL_FACETS = ("room",)

CONDITIONAL_ON_SCENE = {"room": "interior", "structure": "exterior"}
CONDITIONAL_ON_PEOPLE = ("orientation", "activity")

SWEEP_START = 0.15
SWEEP_STOP = 0.40
SWEEP_STEP = 0.002


@dataclass(frozen=True)
class FacetResult:
    """Measured performance of one facet at its best threshold."""

    facet: str
    kind: str
    support: int
    threshold: float | None
    precision: float
    recall: float
    f1: float
    baseline_precision: float
    baseline_recall: float
    baseline_f1: float

    @property
    def improvement(self) -> float:
        return self.f1 - self.baseline_f1


def _encode_with_projection_model(model_name: str, prompts_by_facet: dict) -> dict:
    """Encode prompts using the text model that exposes projected embeddings."""
    import torch
    from transformers import AutoTokenizer, CLIPTextModelWithProjection

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = CLIPTextModelWithProjection.from_pretrained(model_name).to(device)
    model.eval()

    encoded = {}
    for facet_key, prompts in prompts_by_facet.items():
        keys = list(prompts)
        inputs = tokenizer(
            [prompts[key] for key in keys],
            padding=True,
            truncation=True,
            return_tensors="pt",
        )
        inputs = {name: value.to(device) for name, value in inputs.items()}
        with torch.no_grad():
            features = model(**inputs).text_embeds
            features = features / features.norm(dim=-1, keepdim=True)
        encoded[facet_key] = (keys, features.cpu().numpy().astype("float32"))

    return encoded


def _encode_with_full_model(model_name: str, prompts_by_facet: dict) -> dict:
    """Encode prompts using the combined image and text model."""
    import torch
    from transformers import CLIPModel, CLIPProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name).to(device)
    model.eval()

    encoded = {}
    for facet_key, prompts in prompts_by_facet.items():
        keys = list(prompts)
        inputs = processor(
            text=[prompts[key] for key in keys],
            padding=True,
            truncation=True,
            return_tensors="pt",
        )
        inputs = {name: value.to(device) for name, value in inputs.items()}
        with torch.no_grad():
            output = model.get_text_features(**inputs)
            features = output if isinstance(output, torch.Tensor) else output.text_embeds
            features = features / features.norm(dim=-1, keepdim=True)
        encoded[facet_key] = (keys, features.cpu().numpy().astype("float32"))

    return encoded


def check_score_range(
    embeddings: np.ndarray,
    prompts: dict[str, tuple[list[str], np.ndarray]],
    expected_low: float = 0.10,
    expected_high: float = 0.45,
) -> None:
    """Confirm that similarity values fall within a plausible range.

    Text and image embeddings must occupy a shared space for their inner
    product to carry meaning. Values far outside the expected band indicate
    that the two sets were produced differently and cannot be compared.
    """
    sample = embeddings[: min(200, len(embeddings))]
    highest = float("-inf")
    lowest = float("inf")

    for _keys, vectors in prompts.values():
        scores = sample @ vectors.T
        highest = max(highest, float(scores.max()))
        lowest = min(lowest, float(scores.min()))

    print(f"Similarity range across sampled images: {lowest:.4f} to {highest:.4f}")

    if highest < expected_low or lowest > expected_high:
        raise ValueError(
            f"Similarity values ({lowest:.4f} to {highest:.4f}) fall outside the "
            f"expected range ({expected_low} to {expected_high}). Text and image "
            "embeddings are not comparable; confirm both come from the same model."
        )


def encode_prompts(model_name: str, cache: Path | None = None) -> dict[str, tuple[list[str], np.ndarray]]:
    """Return normalised text embeddings for every prompt in the vocabulary."""
    if cache is not None and cache.exists():
        print(f"Reading stored prompt vectors: {cache.resolve()}")
        stored = np.load(cache, allow_pickle=True)
        return {
            key: (list(stored[f"{key}__keys"]), stored[f"{key}__vectors"])
            for key in stored["facets"]
        }

    print(f"Encoding prompts with {model_name}")
    prompts_by_facet = vocab.all_prompts()

    try:
        encoded = _encode_with_projection_model(model_name, prompts_by_facet)
    except Exception as error:
        print(f"Falling back to the combined model: {error}")
        encoded = _encode_with_full_model(model_name, prompts_by_facet)

    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, np.ndarray] = {"facets": np.array(list(encoded))}
        for facet_key, (keys, vectors) in encoded.items():
            payload[f"{facet_key}__keys"] = np.array(keys)
            payload[f"{facet_key}__vectors"] = vectors
        np.savez(cache, **payload)
        print(f"Stored prompt vectors: {cache.resolve()}")

    return encoded


def load_embeddings(index_path: Path, embedding_path: Path) -> tuple[pd.DataFrame, np.ndarray]:
    """Load the image index and its embedding matrix."""
    index = pd.read_csv(index_path, dtype=str).fillna("")
    embeddings = np.load(embedding_path).astype("float32")
    if len(index) != len(embeddings):
        raise ValueError("index and embedding row counts do not match")
    return index, embeddings


def load_annotations(sheet_path: Path, manifest_path: Path, index: pd.DataFrame) -> pd.DataFrame:
    """Join human annotation to the image index through the sample manifest."""
    with open(sheet_path, newline="", encoding="utf-8-sig") as handle:
        annotations = [row for row in csv.DictReader(handle) if any(row.values())]

    with open(manifest_path, newline="", encoding="utf-8-sig") as handle:
        manifest = {}
        for row in csv.DictReader(handle):
            key = str(row.get("index", "")).strip()
            if key:
                manifest[int(key)] = row["relative_path"].strip()

    lookup = {}
    for row in index.to_dict(orient="records"):
        lookup[row["relative_path"].strip().lower()] = row["row_index"]

    records = []
    unmatched = []
    for row in annotations:
        key = str(row.get("index", "")).strip()
        if not key:
            continue
        number = int(key)
        relative_path = manifest.get(number)
        if relative_path is None:
            unmatched.append(number)
            continue
        row_index = lookup.get(relative_path.lower())
        if row_index is None:
            unmatched.append(number)
            continue
        record = dict(row)
        record["row_index"] = int(row_index)
        record["relative_path"] = relative_path
        records.append(record)

    if unmatched:
        print(f"Annotations without a matching embedding: {sorted(unmatched)}")

    return pd.DataFrame(records)


def _values(cell: object) -> list[str]:
    return [part.strip() for part in str(cell or "").split("|") if part.strip()]


def _applicable(row: dict, facet_key: str) -> bool:
    scene = str(row.get("scene_type", "")).strip()
    if facet_key in CONDITIONAL_ON_SCENE:
        return scene == CONDITIONAL_ON_SCENE[facet_key]
    if facet_key in CONDITIONAL_ON_PEOPLE:
        return str(row.get("people", "")).strip() not in ("", "no_people")
    return True


def score_facet(
    embeddings: np.ndarray,
    rows: list[int],
    facet_key: str,
    prompts: dict[str, tuple[list[str], np.ndarray]],
) -> tuple[list[str], np.ndarray]:
    """Return term keys and the similarity of each annotated image to each term."""
    keys, vectors = prompts[facet_key]
    return keys, embeddings[rows] @ vectors.T


def evaluate_multi_label(
    truth: list[set[str]], keys: list[str], scores: np.ndarray, threshold: float
) -> tuple[float, float, float]:
    """Return micro precision, recall and F1 at a given threshold."""
    true_positive = false_positive = false_negative = 0

    for expected, row_scores in zip(truth, scores, strict=False):
        predicted = {keys[i] for i, value in enumerate(row_scores) if value >= threshold}
        true_positive += len(predicted & expected)
        false_positive += len(predicted - expected)
        false_negative += len(expected - predicted)

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def evaluate_single_label(
    truth: list[str], keys: list[str], scores: np.ndarray, threshold: float, fallback: str
) -> tuple[float, float, float]:
    """Return accuracy expressed as precision, recall and F1 for a one-value facet.

    The highest scoring term is taken unless it falls below the threshold, in
    which case the fallback term is recorded.
    """
    true_positive = false_positive = false_negative = 0

    for expected, row_scores in zip(truth, scores, strict=False):
        best = int(np.argmax(row_scores))
        predicted = keys[best] if row_scores[best] >= threshold else fallback
        if predicted == expected:
            true_positive += 1
        else:
            false_positive += 1
            false_negative += 1

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def evaluate_argmax(truth: list[str], keys: list[str], scores: np.ndarray) -> tuple[float, float, float]:
    """Return accuracy for a facet where the highest scoring term is always taken."""
    correct = sum(
        1 for expected, row in zip(truth, scores, strict=False) if keys[int(np.argmax(row))] == expected
    )
    accuracy = correct / len(truth) if truth else 0.0
    return accuracy, accuracy, accuracy


def sweep_facet(
    annotations: pd.DataFrame,
    embeddings: np.ndarray,
    facet_key: str,
    prompts: dict[str, tuple[list[str], np.ndarray]],
    baseline: float,
) -> FacetResult | None:
    """Measure a facet across the threshold range and return its best setting."""
    applicable = [row for row in annotations.to_dict(orient="records") if _applicable(row, facet_key)]
    if not applicable:
        return None

    rows = [row["row_index"] for row in applicable]
    keys, scores = score_facet(embeddings, rows, facet_key, prompts)

    if facet_key in ("scene_type", "shot_type"):
        truth = [str(row.get(facet_key, "")).strip() for row in applicable]
        usable = [(t, s) for t, s in zip(truth, scores, strict=False) if t]
        if not usable:
            return None
        truth = [t for t, _ in usable]
        matrix = np.vstack([s for _, s in usable])
        precision, recall, f1 = evaluate_argmax(truth, keys, matrix)
        return FacetResult(
            facet=facet_key,
            kind="argmax",
            support=len(truth),
            threshold=None,
            precision=precision,
            recall=recall,
            f1=f1,
            baseline_precision=precision,
            baseline_recall=recall,
            baseline_f1=f1,
        )

    if facet_key in ("people",) + SINGLE_OPTIONAL_FACETS:
        fallback = "no_people" if facet_key == "people" else "room_unknown"
        truth = [str(row.get(facet_key, "")).strip() for row in applicable]
        usable = [(t, s) for t, s in zip(truth, scores, strict=False) if t]
        if not usable:
            return None
        truth = [t for t, _ in usable]
        matrix = np.vstack([s for _, s in usable])
        evaluator = lambda value: evaluate_single_label(truth, keys, matrix, value, fallback)
        support = len(truth)
    else:
        truth_sets = [set(_values(row.get(facet_key))) for row in applicable]
        matrix = scores
        evaluator = lambda value: evaluate_multi_label(truth_sets, keys, matrix, value)
        support = sum(len(item) for item in truth_sets)
        if support == 0:
            return None

    grid = np.arange(SWEEP_START, SWEEP_STOP + SWEEP_STEP, SWEEP_STEP)
    best = max(((value, *evaluator(float(value))) for value in grid), key=lambda item: item[3])
    base_precision, base_recall, base_f1 = evaluator(baseline)

    return FacetResult(
        facet=facet_key,
        kind="threshold",
        support=support,
        threshold=round(float(best[0]), 3),
        precision=best[1],
        recall=best[2],
        f1=best[3],
        baseline_precision=base_precision,
        baseline_recall=base_recall,
        baseline_f1=base_f1,
    )


def sweep_curve(
    annotations: pd.DataFrame,
    embeddings: np.ndarray,
    facet_key: str,
    prompts: dict[str, tuple[list[str], np.ndarray]],
) -> pd.DataFrame:
    """Return precision, recall and F1 across the full threshold range."""
    applicable = [row for row in annotations.to_dict(orient="records") if _applicable(row, facet_key)]
    if not applicable:
        return pd.DataFrame()

    rows = [row["row_index"] for row in applicable]
    keys, scores = score_facet(embeddings, rows, facet_key, prompts)
    truth_sets = [set(_values(row.get(facet_key))) for row in applicable]

    records = []
    for value in np.arange(SWEEP_START, SWEEP_STOP + SWEEP_STEP, SWEEP_STEP):
        precision, recall, f1 = evaluate_multi_label(truth_sets, keys, scores, float(value))
        records.append(
            {
                "facet": facet_key,
                "threshold": round(float(value), 3),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
            }
        )
    return pd.DataFrame(records)


def format_results(results: list[FacetResult], baseline: float) -> str:
    """Return a readable comparison of calibrated and uniform thresholds."""
    lines = [
        f"Uniform threshold in use: {baseline}",
        "",
        f"{'facet':<14}{'support':>8}{'threshold':>11}{'precision':>11}"
        f"{'recall':>9}{'F1':>8}{'uniform F1':>12}{'change':>9}",
        "-" * 82,
    ]

    for result in results:
        threshold = "argmax" if result.threshold is None else f"{result.threshold:.3f}"
        change = "" if result.kind == "argmax" else f"{result.improvement:+.3f}"
        lines.append(
            f"{result.facet:<14}{result.support:>8}{threshold:>11}"
            f"{result.precision:>11.3f}{result.recall:>9.3f}{result.f1:>8.3f}"
            f"{result.baseline_f1:>12.3f}{change:>9}"
        )

    tuned = [item for item in results if item.kind == "threshold"]
    if tuned:
        mean_before = sum(item.baseline_f1 for item in tuned) / len(tuned)
        mean_after = sum(item.f1 for item in tuned) / len(tuned)
        lines.append("-" * 82)
        lines.append(
            f"{'mean':<14}{'':>8}{'':>11}{'':>11}{'':>9}"
            f"{mean_after:>8.3f}{mean_before:>12.3f}{mean_after - mean_before:>+9.3f}"
        )

    return "\n".join(lines)


def verify_alignment(
    index: pd.DataFrame,
    embeddings: np.ndarray,
    prompts: dict[str, tuple[list[str], np.ndarray]],
    reference_path: Path,
) -> None:
    """Compare recomputed assignments against a previously generated tag file.

    Text and image embeddings must occupy the same space for similarity values
    to be meaningful. Reproducing the assignments in an existing tag file
    confirms that they do.
    """
    reference = pd.read_csv(reference_path, dtype=str).fillna("")
    row_lookup = {row["image_uid"]: int(row["row_index"]) for row in index.to_dict(orient="records")}

    for facet_key in ("scene_type", "shot_type"):
        if facet_key not in prompts:
            continue
        expected = reference[reference["facet"] == facet_key]
        if expected.empty:
            continue

        keys, vectors = prompts[facet_key]
        matched = agreed = 0
        for row in expected.to_dict(orient="records"):
            position = row_lookup.get(row["image_uid"])
            if position is None:
                continue
            matched += 1
            scores = vectors @ embeddings[position]
            if keys[int(np.argmax(scores))] == row["term_key"]:
                agreed += 1

        if matched:
            share = agreed / matched
            status = "consistent" if share > 0.98 else "INCONSISTENT"
            print(f"  {facet_key:<12} {agreed}/{matched} ({share:.1%}) {status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate vocabulary assignment thresholds")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results"))
    parser.add_argument("--baseline", type=float, default=0.24)
    parser.add_argument("--model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--prompt-cache", type=Path, default=Path("data/interim/prompt_vectors.npz"))
    parser.add_argument(
        "--refresh-prompts",
        action="store_true",
        help="encode prompts again, replacing any stored vectors",
    )
    parser.add_argument(
        "--verify-against",
        type=Path,
        default=None,
        help="existing tag file used to confirm embedding alignment",
    )
    args = parser.parse_args(argv)

    problems = vocab.validate()
    if problems:
        raise ValueError("vocabulary validation failed: " + "; ".join(problems))

    index, embeddings = load_embeddings(args.index, args.embeddings)
    annotations = load_annotations(args.annotations, args.manifest, index)
    if annotations.empty:
        print("No annotations could be matched to the embedding index")
        return 1

    print(f"Vocabulary version {vocab.VERSION}")
    print(f"Images with embeddings: {len(index)}")
    print(f"Annotated images matched: {len(annotations)}")
    print()

    if args.refresh_prompts and args.prompt_cache.exists():
        args.prompt_cache.unlink()

    prompts = encode_prompts(args.model, args.prompt_cache)
    check_score_range(embeddings, prompts)
    print()

    if args.verify_against is not None and args.verify_against.exists():
        print("Embedding alignment")
        verify_alignment(index, embeddings, prompts, args.verify_against)
        print()

    order = EXCLUSIVE_FACETS + SINGLE_OPTIONAL_FACETS + MULTI_LABEL_FACETS
    results = []
    for facet_key in order:
        if facet_key not in prompts:
            continue
        result = sweep_facet(annotations, embeddings, facet_key, prompts, args.baseline)
        if result is not None:
            results.append(result)

    print(format_results(results, args.baseline))

    args.output.mkdir(parents=True, exist_ok=True)

    summary = pd.DataFrame(
        {
            "facet": result.facet,
            "kind": result.kind,
            "support": result.support,
            "threshold": result.threshold,
            "precision": round(result.precision, 4),
            "recall": round(result.recall, 4),
            "f1": round(result.f1, 4),
            "uniform_precision": round(result.baseline_precision, 4),
            "uniform_recall": round(result.baseline_recall, 4),
            "uniform_f1": round(result.baseline_f1, 4),
            "vocabulary_version": vocab.VERSION,
        }
        for result in results
    )
    summary.to_csv(args.output / "threshold_calibration.csv", index=False)

    curves = [
        sweep_curve(annotations, embeddings, facet_key, prompts)
        for facet_key in MULTI_LABEL_FACETS
        if facet_key in prompts
    ]
    curves = [curve for curve in curves if not curve.empty]
    if curves:
        pd.concat(curves, ignore_index=True).to_csv(
            args.output / "threshold_sweep.csv", index=False
        )

    calibrated = {
        result.facet: result.threshold
        for result in results
        if result.kind == "threshold" and result.threshold is not None
    }
    thresholds_path = args.output / "vocabulary_thresholds.json"
    thresholds_path.write_text(json.dumps(calibrated, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"Summary:    {args.output / 'threshold_calibration.csv'}")
    print(f"Sweep:      {args.output / 'threshold_sweep.csv'}")
    print(f"Thresholds: {thresholds_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())