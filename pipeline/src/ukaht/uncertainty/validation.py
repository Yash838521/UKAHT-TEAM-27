"""Validation of the uncertainty score against measured labelling error.

An uncertainty score is only useful if it anticipates mistakes. A value that
carries no relationship to error is indistinguishable, at the point of use,
from one that does: both produce a plausible number and a plausible
distribution.

This module tests the relationship directly. For every annotated image the
error rate of the assigned terms is measured against human annotation, and that
rate is compared with the uncertainty score computed independently of it. Three
measures are reported.

Rank correlation
    Spearman's coefficient between uncertainty and error, with a permutation
    test giving the probability of a coefficient at least as large arising by
    chance.

Error by band
    Observed error within low, moderate and high bands. A useful score produces
    a rising sequence.

Review flag performance
    Precision and recall of the flag, alongside the rate that would be obtained
    by flagging images at random, which is the level any flag must exceed to be
    worth acting on.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ukaht.tagging import vocabulary as vocab
from ukaht.tagging.calibration import (
    _applicable,
    _values,
    encode_prompts,
    load_annotations,
    load_embeddings,
    score_facet,
)

EVALUATED_FACETS = ("scene_type", "shot_type", "room", "nature", "condition")
EXCLUSIVE = ("scene_type", "shot_type", "room")

BANDS = ((0.0, 0.35, "low"), (0.35, 0.55, "moderate"), (0.55, 1.01, "high"))

PERMUTATIONS = 10000
RANDOM_SEED = 27


@dataclass(frozen=True)
class ImageError:
    """Measured labelling error for one annotated image."""

    image_uid: str
    row_index: int
    correct: int
    total: int

    @property
    def error_rate(self) -> float:
        return 1.0 - self.correct / self.total if self.total else 0.0


def measure_errors(
    annotations: pd.DataFrame,
    embeddings: np.ndarray,
    prompts: dict[str, tuple[list[str], np.ndarray]],
    thresholds: dict[str, float],
) -> list[ImageError]:
    """Return per-image agreement between assigned terms and human annotation."""
    results: list[ImageError] = []

    for row in annotations.to_dict(orient="records"):
        position = int(row["row_index"])
        embedding = embeddings[position]
        correct = 0
        total = 0

        for facet_key in EVALUATED_FACETS:
            if facet_key not in prompts or not _applicable(row, facet_key):
                continue

            expected = _values(row.get(facet_key))
            if not expected:
                continue

            keys, scores = score_facet(embeddings, [position], facet_key, prompts)
            scores = scores[0]

            if facet_key in EXCLUSIVE:
                predicted = {keys[int(np.argmax(scores))]}
            else:
                threshold = thresholds.get(facet_key, 0.24)
                predicted = {
                    keys[i] for i, value in enumerate(scores) if value >= threshold
                }

            expected_set = set(expected)
            correct += len(predicted & expected_set)
            total += len(predicted | expected_set)

        if total:
            results.append(
                ImageError(
                    image_uid=str(row.get("image_uid", position)),
                    row_index=position,
                    correct=correct,
                    total=total,
                )
            )

    return results


def rank(values: np.ndarray) -> np.ndarray:
    """Return ranks with ties assigned their average position."""
    order = np.argsort(values)
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(1, len(values) + 1)

    for value in np.unique(values):
        mask = values == value
        if mask.sum() > 1:
            ranks[mask] = ranks[mask].mean()

    return ranks


def spearman(first: np.ndarray, second: np.ndarray) -> float:
    """Return Spearman's rank correlation coefficient."""
    first_ranks = rank(first)
    second_ranks = rank(second)

    first_centred = first_ranks - first_ranks.mean()
    second_centred = second_ranks - second_ranks.mean()

    denominator = np.sqrt((first_centred**2).sum() * (second_centred**2).sum())
    if denominator == 0:
        return 0.0

    return float((first_centred * second_centred).sum() / denominator)


def permutation_probability(
    first: np.ndarray, second: np.ndarray, observed: float, permutations: int
) -> float:
    """Return the proportion of shuffles reaching the observed coefficient.

    With a sample of this size a permutation test is preferable to an
    approximation that assumes a particular distribution.
    """
    generator = np.random.default_rng(RANDOM_SEED)
    shuffled = second.copy()
    reached = 0

    for _ in range(permutations):
        generator.shuffle(shuffled)
        if abs(spearman(first, shuffled)) >= abs(observed):
            reached += 1

    return (reached + 1) / (permutations + 1)


def band_table(scores: np.ndarray, errors: np.ndarray) -> pd.DataFrame:
    """Return observed error within each uncertainty band."""
    records = []

    for lower, upper, label in BANDS:
        mask = (scores >= lower) & (scores < upper)
        count = int(mask.sum())
        records.append(
            {
                "band": label,
                "range": f"{lower:.2f} to {min(upper, 1.0):.2f}",
                "images": count,
                "mean_error": round(float(errors[mask].mean()), 4) if count else None,
                "mean_uncertainty": round(float(scores[mask].mean()), 4) if count else None,
            }
        )

    return pd.DataFrame(records)


def flag_performance(
    scores: np.ndarray, errors: np.ndarray, threshold: float, error_cut: float
) -> dict[str, float]:
    """Return precision and recall of the review flag against a random baseline."""
    flagged = scores >= threshold
    poor = errors >= error_cut

    true_positive = int((flagged & poor).sum())
    false_positive = int((flagged & ~poor).sum())
    false_negative = int((~flagged & poor).sum())

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    baseline = float(poor.mean())

    return {
        "flagged": int(flagged.sum()),
        "poorly_labelled": int(poor.sum()),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "random_baseline": round(baseline, 4),
        "lift": round(precision / baseline, 3) if baseline else 0.0,
    }


def component_correlations(
    merged: pd.DataFrame, errors: np.ndarray
) -> pd.DataFrame:
    """Return the correlation of each component with observed error."""
    records = []

    for column, label in (
        ("confidence_component", "confidence"),
        ("quality_component", "quality"),
        ("agreement_component", "agreement"),
        ("novelty_component", "novelty"),
        ("uncertainty_score", "combined"),
    ):
        if column not in merged.columns:
            continue
        coefficient = spearman(merged[column].to_numpy(dtype=float), errors)
        records.append({"component": label, "spearman": round(coefficient, 4)})

    return pd.DataFrame(records)


def format_report(
    sample_size: int,
    coefficient: float,
    probability: float,
    bands: pd.DataFrame,
    components: pd.DataFrame,
    flag: dict[str, float],
    error_cut: float,
    threshold: float,
) -> str:
    """Return a readable account of the validation result."""
    lines = [f"Annotated images with measurable error: {sample_size}", ""]

    lines.append("Rank correlation between uncertainty and observed error")
    lines.append(f"  Spearman coefficient : {coefficient:+.4f}")
    lines.append(f"  Permutation p-value  : {probability:.4f}")

    if probability < 0.05 and coefficient > 0:
        verdict = "The score anticipates error at conventional significance."
    elif coefficient > 0:
        verdict = "The relationship runs in the expected direction but is not significant at this sample size."
    else:
        verdict = "No positive relationship between the score and observed error is present."
    lines.append(f"  {verdict}")

    lines.append("")
    lines.append("Observed error by uncertainty band")
    lines.append(f"  {'band':<10}{'range':<16}{'images':>8}{'mean error':>13}{'mean score':>13}")
    for row in bands.to_dict(orient="records"):
        error = "-" if row["mean_error"] is None else f"{row['mean_error']:.3f}"
        score = "-" if row["mean_uncertainty"] is None else f"{row['mean_uncertainty']:.3f}"
        lines.append(
            f"  {row['band']:<10}{row['range']:<16}{row['images']:>8}{error:>13}{score:>13}"
        )

    populated = bands.dropna(subset=["mean_error"])
    if len(populated) > 1:
        rising = populated["mean_error"].is_monotonic_increasing
        lines.append("")
        lines.append(
            "  Error rises across the bands." if rising
            else "  Error does not rise consistently across the bands."
        )

    lines.append("")
    lines.append("Correlation of each component with observed error")
    for row in components.to_dict(orient="records"):
        lines.append(f"  {row['component']:<12} {row['spearman']:+.4f}")

    lines.append("")
    lines.append(f"Review flag at {threshold}, treating error at or above {error_cut} as poorly labelled")
    lines.append(f"  images flagged        : {flag['flagged']}")
    lines.append(f"  poorly labelled       : {flag['poorly_labelled']}")
    lines.append(f"  precision             : {flag['precision']:.3f}")
    lines.append(f"  recall                : {flag['recall']:.3f}")
    lines.append(f"  random baseline       : {flag['random_baseline']:.3f}")
    lines.append(f"  improvement on chance : {flag['lift']:.2f} times")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Test whether the uncertainty score anticipates labelling error"
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results"))
    parser.add_argument("--model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--prompt-cache", type=Path, default=Path("data/interim/prompt_vectors.npz"))
    parser.add_argument("--review-threshold", type=float, default=0.55)
    parser.add_argument("--error-cut", type=float, default=0.5)
    parser.add_argument("--permutations", type=int, default=PERMUTATIONS)
    args = parser.parse_args(argv)

    problems = vocab.validate()
    if problems:
        raise ValueError("vocabulary validation failed: " + "; ".join(problems))

    index, embeddings = load_embeddings(args.index, args.embeddings)
    annotations = load_annotations(args.annotations, args.manifest, index)
    if annotations.empty:
        print("No annotations could be matched to the embedding index")
        return 1

    prompts = encode_prompts(args.model, args.prompt_cache)

    thresholds = {}
    if args.thresholds is not None and args.thresholds.exists():
        import json

        thresholds = {
            key: float(value)
            for key, value in json.loads(args.thresholds.read_text(encoding="utf-8")).items()
        }

    scores = pd.read_csv(args.scores)
    uid_by_row = {int(row["row_index"]): row["image_uid"] for row in index.to_dict(orient="records")}

    measured = measure_errors(annotations, embeddings, prompts, thresholds)
    if len(measured) < 5:
        print("Too few annotated images carry measurable error for a meaningful test")
        return 1

    frame = pd.DataFrame(
        {
            "image_uid": [uid_by_row.get(item.row_index, item.image_uid) for item in measured],
            "row_index": [item.row_index for item in measured],
            "correct": [item.correct for item in measured],
            "total": [item.total for item in measured],
            "error_rate": [item.error_rate for item in measured],
        }
    )

    merged = frame.merge(scores, on="image_uid", how="inner")
    if len(merged) < 5:
        print("Uncertainty scores could not be matched to the annotated images")
        return 1

    uncertainty = merged["uncertainty_score"].to_numpy(dtype=float)
    error = merged["error_rate"].to_numpy(dtype=float)

    coefficient = spearman(uncertainty, error)
    probability = permutation_probability(uncertainty, error, coefficient, args.permutations)

    bands = band_table(uncertainty, error)
    components = component_correlations(merged, error)
    flag = flag_performance(uncertainty, error, args.review_threshold, args.error_cut)

    print(
        format_report(
            len(merged),
            coefficient,
            probability,
            bands,
            components,
            flag,
            args.error_cut,
            args.review_threshold,
        )
    )

    args.output.mkdir(parents=True, exist_ok=True)

    merged.to_csv(args.output / "uncertainty_validation_detail.csv", index=False)
    bands.to_csv(args.output / "uncertainty_bands.csv", index=False)
    components.to_csv(args.output / "uncertainty_components.csv", index=False)

    summary = pd.DataFrame(
        [
            {
                "sample_size": len(merged),
                "spearman": round(coefficient, 4),
                "p_value": round(probability, 4),
                "permutations": args.permutations,
                "review_threshold": args.review_threshold,
                "error_cut": args.error_cut,
                "flag_precision": flag["precision"],
                "flag_recall": flag["recall"],
                "random_baseline": flag["random_baseline"],
                "lift": flag["lift"],
                "vocabulary_version": vocab.VERSION,
            }
        ]
    )
    summary.to_csv(args.output / "uncertainty_validation.csv", index=False)

    print()
    print(f"Summary: {args.output / 'uncertainty_validation.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())