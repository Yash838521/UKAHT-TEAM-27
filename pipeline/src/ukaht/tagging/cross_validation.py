

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ukaht.tagging import vocabulary as vocab
from ukaht.tagging.calibration import (
    MULTI_LABEL_FACETS,
    SWEEP_START,
    SWEEP_STEP,
    SWEEP_STOP,
    _applicable,
    _values,
    encode_prompts,
    load_annotations,
    load_embeddings,
    score_facet,
)

SINGLE_LABEL_FACETS = ("people", "room")
FALLBACK_TERMS = {"people": "no_people", "room": "room_unknown"}


@dataclass(frozen=True)
class Counts:
    """Assignment outcomes accumulated over held-out images."""

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    def __add__(self, other: Counts) -> Counts:
        return Counts(
            self.true_positive + other.true_positive,
            self.false_positive + other.false_positive,
            self.false_negative + other.false_negative,
        )

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        precision, recall = self.precision, self.recall
        return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


@dataclass(frozen=True)
class CrossValidationResult:
    """Resampled performance of one facet."""

    facet: str
    folds: int
    support: int
    mean_threshold: float
    threshold_spread: float
    precision: float
    recall: float
    f1: float
    resubstitution_f1: float
    uniform_f1: float

    @property
    def optimism(self) -> float:
        return self.resubstitution_f1 - self.f1

    @property
    def honest_gain(self) -> float:
        return self.f1 - self.uniform_f1


def threshold_grid() -> np.ndarray:
    return np.arange(SWEEP_START, SWEEP_STOP + SWEEP_STEP, SWEEP_STEP)


def count_multi_label(expected: set[str], keys: list[str], scores: np.ndarray, threshold: float) -> Counts:
    """Return outcomes for one image where several terms may apply."""
    predicted = {keys[i] for i, value in enumerate(scores) if value >= threshold}
    return Counts(
        true_positive=len(predicted & expected),
        false_positive=len(predicted - expected),
        false_negative=len(expected - predicted),
    )


def count_single_label(
    expected: str, keys: list[str], scores: np.ndarray, threshold: float, fallback: str
) -> Counts:
    """Return outcomes for one image where exactly one term applies."""
    best = int(np.argmax(scores))
    predicted = keys[best] if scores[best] >= threshold else fallback
    if predicted == expected:
        return Counts(true_positive=1)
    return Counts(false_positive=1, false_negative=1)


def best_threshold(
    truth: list,
    keys: list[str],
    scores: np.ndarray,
    positions: list[int],
    counter,
    candidates: np.ndarray | None = None,
) -> float:
    """Return the threshold maximising F1 over the given rows."""
    values = threshold_grid() if candidates is None else candidates
    if len(values) == 0:
        raise ValueError("Threshold candidate list is empty")

    best_value = float(values[0])
    best_score = -1.0

    for value in values:
        total = Counts()
        for position in positions:
            total = total + counter(truth[position], keys, scores[position], float(value))
        if total.f1 > best_score:
            best_score = total.f1
            best_value = float(value)

    return best_value


def evaluate_at(
    truth: list, keys: list[str], scores: np.ndarray, positions: list[int], counter, threshold: float
) -> Counts:
    """Return accumulated outcomes at a fixed threshold."""
    total = Counts()
    for position in positions:
        total = total + counter(truth[position], keys, scores[position], threshold)
    return total


def cross_validate_facet(
    annotations: pd.DataFrame,
    embeddings: np.ndarray,
    facet_key: str,
    prompts: dict[str, tuple[list[str], np.ndarray]],
    uniform: float,
    candidates: np.ndarray | None = None,
) -> CrossValidationResult | None:
    """Estimate facet performance with each image held out in turn."""
    applicable = [row for row in annotations.to_dict(orient="records") if _applicable(row, facet_key)]
    if len(applicable) < 3:
        return None

    rows = [row["row_index"] for row in applicable]
    keys, scores = score_facet(embeddings, rows, facet_key, prompts)

    if facet_key in SINGLE_LABEL_FACETS:
        fallback = FALLBACK_TERMS[facet_key]
        truth = [str(row.get(facet_key, "")).strip() for row in applicable]
        keep = [i for i, value in enumerate(truth) if value]
        counter = lambda expected, k, s, t: count_single_label(expected, k, s, t, fallback)
        support = len(keep)
    else:
        truth = [set(_values(row.get(facet_key))) for row in applicable]
        keep = list(range(len(truth)))
        counter = count_multi_label
        support = sum(len(item) for item in truth)

    if support == 0 or len(keep) < 3:
        return None

    held_out_total = Counts()
    chosen: list[float] = []

    for index in keep:
        training = [position for position in keep if position != index]
        threshold = best_threshold(
            truth, keys, scores, training, counter, candidates
        )
        chosen.append(threshold)
        held_out_total = held_out_total + counter(
            truth[index], keys, scores[index], threshold
        )

    resubstitution = best_threshold(
        truth, keys, scores, keep, counter, candidates
    )
    resubstitution_f1 = evaluate_at(truth, keys, scores, keep, counter, resubstitution).f1
    uniform_f1 = evaluate_at(truth, keys, scores, keep, counter, uniform).f1

    return CrossValidationResult(
        facet=facet_key,
        folds=len(keep),
        support=support,
        mean_threshold=float(np.mean(chosen)),
        threshold_spread=float(np.std(chosen)),
        precision=held_out_total.precision,
        recall=held_out_total.recall,
        f1=held_out_total.f1,
        resubstitution_f1=resubstitution_f1,
        uniform_f1=uniform_f1,
    )


def format_results(results: list[CrossValidationResult], uniform: float) -> str:
    """Return a comparison of resampled, fitted and uniform performance."""
    lines = [
        f"Leave-one-out estimation against a uniform threshold of {uniform}",
        "",
        f"{'facet':<14}{'folds':>7}{'support':>9}{'threshold':>11}{'spread':>9}"
        f"{'precision':>11}{'recall':>9}{'F1':>8}{'fitted F1':>11}{'optimism':>10}{'gain':>8}",
        "-" * 107,
    ]

    for result in results:
        lines.append(
            f"{result.facet:<14}{result.folds:>7}{result.support:>9}"
            f"{result.mean_threshold:>11.3f}{result.threshold_spread:>9.3f}"
            f"{result.precision:>11.3f}{result.recall:>9.3f}{result.f1:>8.3f}"
            f"{result.resubstitution_f1:>11.3f}{result.optimism:>10.3f}"
            f"{result.honest_gain:>+8.3f}"
        )

    if results:
        mean_cv = sum(item.f1 for item in results) / len(results)
        mean_fit = sum(item.resubstitution_f1 for item in results) / len(results)
        mean_uniform = sum(item.uniform_f1 for item in results) / len(results)
        lines.append("-" * 107)
        lines.append(
            f"{'mean':<14}{'':>7}{'':>9}{'':>11}{'':>9}{'':>11}{'':>9}"
            f"{mean_cv:>8.3f}{mean_fit:>11.3f}{mean_fit - mean_cv:>10.3f}"
            f"{mean_cv - mean_uniform:>+8.3f}"
        )
        lines.append("")
        lines.append(f"Uniform threshold mean F1: {mean_uniform:.3f}")

    return "\n".join(lines)


def stability_table(results: list[CrossValidationResult]) -> str:
    """Return a table showing how consistently each threshold are selected."""
    lines = ["Threshold stability across folds", ""]

    for result in results:
        if result.mean_threshold == 0:
            continue
        variation = result.threshold_spread / result.mean_threshold
        if variation < 0.02:
            reading = "stable"
        elif variation < 0.08:
            reading = "moderate variation"
        else:
            reading = "unstable"
        lines.append(
            f"  {result.facet:<14} {result.mean_threshold:.3f} "
            f"(sd {result.threshold_spread:.3f}, {variation:.1%})  {reading}"
        )

    lines.append("")
    lines.append(
        "A threshold selected consistently across folds is likely to transfer to "
        "unseen images. Wide variation indicates that the value is being driven by "
        "individual images rather than by a stable property of the facet."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Estimate assignment thresholds with cross-validation"
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results"))
    parser.add_argument("--uniform", type=float, default=0.24)
    parser.add_argument("--model", default="openai/clip-vit-base-patch32")
    parser.add_argument(
        "--prompt-cache", type=Path, default=Path("data/interim/prompt_vectors.npz")
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
    print(f"Annotated images: {len(annotations)}")
    print()

    prompts = encode_prompts(args.model, args.prompt_cache)

    order = SINGLE_LABEL_FACETS + MULTI_LABEL_FACETS
    results = []
    for facet_key in order:
        if facet_key not in prompts:
            continue
        result = cross_validate_facet(annotations, embeddings, facet_key, prompts, args.uniform)
        if result is not None:
            results.append(result)

    if not results:
        print("No facet had enough annotation to support cross-validation")
        return 1

    print(format_results(results, args.uniform))
    print()
    print(stability_table(results))

    args.output.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(
        {
            "facet": result.facet,
            "folds": result.folds,
            "support": result.support,
            "mean_threshold": round(result.mean_threshold, 4),
            "threshold_sd": round(result.threshold_spread, 4),
            "cv_precision": round(result.precision, 4),
            "cv_recall": round(result.recall, 4),
            "cv_f1": round(result.f1, 4),
            "fitted_f1": round(result.resubstitution_f1, 4),
            "uniform_f1": round(result.uniform_f1, 4),
            "optimism": round(result.optimism, 4),
            "honest_gain": round(result.honest_gain, 4),
            "vocabulary_version": vocab.VERSION,
        }
        for result in results
    )
    output_path = args.output / "threshold_cross_validation.csv"
    summary.to_csv(output_path, index=False)

    print()
    print(f"Summary: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
