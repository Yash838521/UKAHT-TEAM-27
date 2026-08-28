"""Uncertainty scoring for automatically assigned vocabulary terms.

Vision-language models assign terms without indicating how far those terms can
be trusted. A description generated for a blurred, unidentifiable subject is
expressed with the same fluency as one generated for a clearly lit scene, so an
incorrect label is indistinguishable from a correct one at the point of use.

This module combines four independent signals into a single score per image,
together with a stated reason and a flag marking images that warrant human
checking.

Model confidence
    The margin between the highest and second highest scoring term, and the
    distance of the accepted term above its threshold. A narrow margin
    indicates the model is separating two terms poorly even where the absolute
    score appears healthy.

Image quality
    Sharpness and exposure measured from the image itself. Degraded images
    offer less evidence, so terms assigned to them carry less weight.

Model agreement
    Whether a generated description corroborates the terms assigned by
    similarity matching. Two models examining the same image provide
    independent evidence; disagreement between them is informative in itself.

Novelty
    Distance from the annotated reference set in embedding space. Terms and
    thresholds were established on that set, so an image unlike it lies outside
    the conditions under which they were validated.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ukaht.tagging import vocabulary as vocab
from ukaht.tagging.calibration import (
    encode_prompts,
    load_annotations,
    load_embeddings,
)

DEFAULT_WEIGHTS = {
    "confidence": 0.50,
    "quality": 0.35,
    "agreement": 0.15,
    "novelty": 0.00,
}

MEASURED_WEIGHTS = dict(DEFAULT_WEIGHTS)

UNIFORM_WEIGHTS = {
    "confidence": 0.25,
    "quality": 0.25,
    "agreement": 0.25,
    "novelty": 0.25,
}

WEIGHT_SETS = {
    "measured": MEASURED_WEIGHTS,
    "uniform": UNIFORM_WEIGHTS,
    "confidence_quality": {
        "confidence": 0.60,
        "quality": 0.40,
        "agreement": 0.00,
        "novelty": 0.00,
    },
}

REVIEW_THRESHOLD = 0.55

SCORED_FACETS = ("scene_type", "shot_type", "room", "nature", "condition")

TERM_LEXICON: dict[str, tuple[str, ...]] = {
    "exterior": (
        "building", "exterior", "outside", "hut", "cabin", "shed", "structure",
        "roof", "chimney", "facade", "wall of", "house", "lodge",
    ),
    "interior": (
        "interior", "inside", "room", "wall", "floor", "ceiling", "indoor",
        "shelf", "shelves", "furniture", "doorway",
    ),
    "landscape": (
        "landscape", "mountain", "snow-covered", "horizon", "scenery", "terrain",
        "expanse", "coastline", "shore", "vast", "glacier", "wilderness",
    ),
    "object_study": (
        "close-up", "closeup", "background is blurred", "plain", "white surface",
        "focal point", "against a", "resting on", "lying on", "sitting on",
        "photograph of a", "the object", "appears to be made of", "blurred, but",
        "wooden surface", "beige", "cardboard", "white background", "the item",
    ),
    "wide": (
        "landscape", "wide", "background", "in the distance", "overall scene",
        "vast", "expanse", "panoramic", "surrounding",
    ),
    "medium": (
        "shelf", "wall", "section", "part of", "row of", "collection of",
        "arranged", "stacked", "several",
    ),
    "detail": (
        "close-up", "closeup", "focal point", "blurred", "detail", "tightly",
        "the surface", "texture", "engraved", "label reads", "written on",
    ),
    "living_room": (
        "living room", "armchair", "sofa", "fireplace", "lounge", "couch",
        "coffee table", "bookshelf",
    ),
    "kitchen": (
        "kitchen", "stove", "oven", "kettle", "countertop", "pantry",
        "cooking", "saucepan", "frying pan", "utensil", "food tin",
    ),
    "workshop": (
        "workshop", "workbench", "tools", "garage", "machinery", "wrench",
        "hammer", "toolbox", "equipment scattered",
    ),
    "bunkroom": (
        "bunk", "bed", "bedroom", "mattress", "pillow", "dormitory",
        "blanket", "linens", "sleeping",
    ),
    "radio_room": (
        "radio", "control panel", "knobs", "dials", "switches", "antenna",
        "receiver", "transmitter", "wires", "electronic",
    ),
    "storage": (
        "shelf", "shelves", "stacked", "crates", "storage", "containers",
        "boxes", "supplies", "arranged neatly",
    ),
    "museum_display": (
        "museum", "display", "plaque", "information", "exhibit", "label",
        "survey", "collection", "catalogue", "poster", "signboard",
        "condition survey", "list of items", "documentation",
    ),
    "penguin": ("penguin",),
    "dog": ("dog", "husky", "sled dog"),
    "seal": ("seal",),
    "bird": ("bird", "puffin"),
    "whale": ("whale",),
    "snow": ("snow", "snowy", "snow-covered", "snow-capped"),
    "sea_ice": ("sea ice", "frozen", "ice floe", "ice-covered"),
    "iceberg": ("iceberg",),
    "glacier": ("glacier", "ice cliff", "ice shelf"),
    "exposed_rock": ("rock", "rocky", "boulder", "pebble", "stone"),
    "mountains": ("mountain", "peak", "range", "snow-capped"),
    "open_water": ("water", "sea", "ocean", "bay", "lake"),
    "coastline": ("shore", "coast", "shoreline", "beach"),
    "sunset": ("sunset", "sunrise", "orange sky", "pink sky", "warm glow"),
    "overcast": ("overcast", "cloudy", "grey sky", "gloomy", "bleak"),
    "clear_sky": ("clear", "blue sky", "sunny", "clear and blue"),
    "weathered_timber": (
        "weathered", "peeling", "worn", "aged", "dilapidated", "chipped",
        "cracks", "faded",
    ),
    "paint_loss": (
        "peeling paint", "chipped", "flaking", "faded", "paint peeling",
        "discoloured", "discolored",
    ),
    "rust": ("rust", "rusted", "rusty", "corroded", "corrosion", "oxidised"),
    "structural_damage": (
        "broken", "collapsed", "crumbling", "damaged", "rubble", "debris",
    ),
    "object_wear": (
        "worn", "aged", "weathered", "old", "wear and tear", "signs of wear",
        "frayed", "scratches", "grime",
    ),
    "sound": (),
}

DOCUMENT_MARKERS = (
    "survey",
    "list of items",
    "written on",
    "text reads",
    "label reads",
    "titled",
    "poster",
    "signboard",
    "printed",
    "document",
)


PEOPLE_MARKERS = (
    "person",
    "people",
    "man ",
    "men ",
    "woman",
    "women",
    "hand",
    "someone",
    "worker",
    "figure",
)

_WORD = re.compile(r"[a-z][a-z\-']+")


@dataclass(frozen=True)
class Signals:
    """Component values contributing to one image's score."""

    image_uid: str
    confidence: float
    quality: float
    agreement: float
    novelty: float

    def combine(self, weights: dict[str, float]) -> float:
        total = sum(weights.values())
        weighted = (
            self.confidence * weights["confidence"]
            + self.quality * weights["quality"]
            + self.agreement * weights["agreement"]
            + self.novelty * weights["novelty"]
        )
        return round(weighted / total, 4)

    def dominant(self) -> str:
        values = {
            "confidence": self.confidence,
            "quality": self.quality,
            "agreement": self.agreement,
            "novelty": self.novelty,
        }
        return max(values, key=lambda key: values[key])


REASONS = {
    "confidence": "the matching scores separated the leading terms only narrowly",
    "quality": "the image is soft or poorly exposed, limiting what can be assigned",
    "agreement": "the generated description does not corroborate the assigned terms",
    "novelty": "the image differs markedly from those used to establish the terms",
}


def load_quality(path: Path, index: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Return quality measurements keyed by image identifier.

    Quality measurements are keyed by the containing directory and file name
    rather than by identifier, so the index supplies the correspondence.
    """
    quality = pd.read_csv(path)
    quality["join_key"] = (quality["relative_path"].str.split("/").str[-2:].str.join("/")).str.strip().str.lower()

    lookup = {}
    for row in index.to_dict(orient="records"):
        parts = row["relative_path"].split("/")
        key = "/".join(parts[-2:]).lower()
        lookup[key] = row["image_uid"]

    measurements: dict[str, dict[str, float]] = {}
    for row in quality.to_dict(orient="records"):
        image_uid = lookup.get(row["join_key"])
        if image_uid is None:
            continue
        measurements[image_uid] = {
            "sharpness": float(row.get("sharpness_score", 0.0)),
            "exposure": float(row.get("exposure_score", 0.0)),
            "overall": float(row.get("overall_score", 0.0)),
        }

    return measurements


def load_descriptions(path: Path) -> dict[str, str]:
    """Return generated descriptions keyed by image identifier."""
    frame = pd.read_csv(path, dtype=str).fillna("")
    return {
        str(row["image_uid"]).strip(): str(row["description"]).strip().lower()
        for row in frame.to_dict(orient="records")
        if str(row.get("image_uid", "")).strip()
    }


def confidence_signal(
    embedding: np.ndarray,
    prompts: dict[str, tuple[list[str], np.ndarray]],
    thresholds: dict[str, float],
) -> tuple[float, dict[str, str]]:
    """Return an uncertainty contribution from score margins and threshold distance."""
    margins = []
    assigned: dict[str, str] = {}

    for facet_key in SCORED_FACETS:
        if facet_key not in prompts:
            continue
        keys, vectors = prompts[facet_key]
        scores = vectors @ embedding
        order = np.argsort(scores)[::-1]

        best = keys[int(order[0])]
        best_score = float(scores[order[0]])
        second_score = float(scores[order[1]]) if len(order) > 1 else 0.0

        threshold = thresholds.get(facet_key)
        if threshold is not None and best_score < threshold:
            continue

        assigned[facet_key] = best
        separation = best_score - second_score
        margins.append(min(separation / 0.05, 1.0))

    if not margins:
        return 1.0, assigned

    return round(1.0 - float(np.mean(margins)), 4), assigned


def quality_signal(measurement: dict[str, float] | None) -> float:
    """Return an uncertainty contribution from measured image quality."""
    if measurement is None:
        return 0.5

    sharpness = measurement.get("sharpness", 0.0)
    exposure = measurement.get("exposure", 0.0)
    combined = 0.6 * sharpness + 0.4 * exposure
    return round(1.0 - min(max(combined, 0.0), 1.0), 4)


def agreement_signal(description: str, assigned: dict[str, str]) -> tuple[float, int, int]:
    """Return an uncertainty contribution from description corroboration.

    Each assigned term carries a set of expressions that a description of the
    same subject would be expected to contain. The proportion of terms so
    corroborated measures how far two independently produced accounts of the
    image coincide.
    """
    if not description or not assigned:
        return 0.5, 0, 0

    checked = 0
    corroborated = 0

    for facet_key, term_key in assigned.items():
        expressions = TERM_LEXICON.get(term_key)
        if not expressions:
            continue
        checked += 1
        if any(expression in description for expression in expressions):
            corroborated += 1

    if checked == 0:
        return 0.5, 0, 0

    # A description dominated by transcribed text describes what the image
    # depicts only indirectly, so absence of the expected expressions is not
    # evidence that the assigned terms are wrong.
    if corroborated == 0 and any(marker in description for marker in DOCUMENT_MARKERS):
        return 0.5, corroborated, checked

    return round(1.0 - corroborated / checked, 4), corroborated, checked


def people_conflict(description: str, people_term: str) -> bool:
    """Return whether a description contradicts the recorded people value."""
    mentions = any(marker in description for marker in PEOPLE_MARKERS)
    if people_term == "no_people":
        return mentions
    return not mentions


def novelty_signal(embedding: np.ndarray, reference: np.ndarray) -> float:
    """Return an uncertainty contribution from distance to the reference set."""
    if reference.size == 0:
        return 0.5

    similarities = reference @ embedding
    closest = float(np.max(similarities))
    distance = (1.0 - closest) / 0.6
    return round(min(max(distance, 0.0), 1.0), 4)


def describe(signals: Signals, score: float, weights: dict[str, float]) -> str:
    """Return a readable explanation of an image's score."""
    if score < 0.35:
        return "The assigned terms are well supported across all measures."

    driver = signals.dominant()
    reason = REASONS[driver]

    secondary = sorted(
        (
            ("confidence", signals.confidence),
            ("quality", signals.quality),
            ("agreement", signals.agreement),
            ("novelty", signals.novelty),
        ),
        key=lambda item: item[1],
        reverse=True,
    )[1]

    if secondary[1] > 0.6:
        return f"Chiefly because {reason}, and {REASONS[secondary[0]]}."
    return f"Chiefly because {reason}."


def score_archive(
    index: pd.DataFrame,
    embeddings: np.ndarray,
    prompts: dict[str, tuple[list[str], np.ndarray]],
    thresholds: dict[str, float],
    quality: dict[str, dict[str, float]],
    descriptions: dict[str, str],
    reference: np.ndarray,
    weights: dict[str, float],
    review_threshold: float,
) -> pd.DataFrame:
    """Return per-image uncertainty scores with their components and reasons."""
    records = []

    for row, embedding in zip(index.to_dict(orient="records"), embeddings, strict=False):
        image_uid = row["image_uid"]
        description = descriptions.get(image_uid, "")

        confidence, assigned = confidence_signal(embedding, prompts, thresholds)
        measurement = quality.get(image_uid)
        agreement, corroborated, checked = agreement_signal(description, assigned)

        signals = Signals(
            image_uid=image_uid,
            confidence=confidence,
            quality=quality_signal(measurement),
            agreement=agreement,
            novelty=novelty_signal(embedding, reference),
        )

        score = signals.combine(weights)

        records.append(
            {
                "image_uid": image_uid,
                "file_name": row.get("file_name", ""),
                "uncertainty_score": score,
                "confidence_component": signals.confidence,
                "quality_component": signals.quality,
                "agreement_component": signals.agreement,
                "novelty_component": signals.novelty,
                "terms_corroborated": corroborated,
                "terms_checked": checked,
                "has_description": bool(description),
                "has_quality": measurement is not None,
                "review_recommended": score >= review_threshold,
                "reason": describe(signals, score, weights),
                "vocabulary_version": vocab.VERSION,
            }
        )

    return pd.DataFrame(records)


def summarise(scores: pd.DataFrame, review_threshold: float) -> str:
    """Return a readable summary of the score distribution."""
    lines = [f"Images scored: {len(scores)}", ""]

    lines.append("Component means")
    for column, label in (
        ("confidence_component", "confidence"),
        ("quality_component", "quality"),
        ("agreement_component", "agreement"),
        ("novelty_component", "novelty"),
        ("uncertainty_score", "combined"),
    ):
        lines.append(f"  {label:<12} {scores[column].mean():.3f}")

    lines.append("")
    lines.append("Distribution of the combined score")
    bands = [(0.0, 0.35, "low"), (0.35, 0.55, "moderate"), (0.55, 1.01, "high")]
    for lower, upper, label in bands:
        count = int(((scores.uncertainty_score >= lower) & (scores.uncertainty_score < upper)).sum())
        lines.append(f"  {label:<10} {count:>5} ({count / len(scores):.1%})")

    flagged = int(scores.review_recommended.sum())
    lines.append("")
    lines.append(f"Flagged for review at {review_threshold}: {flagged} ({flagged / len(scores):.1%})")

    coverage = int(scores.has_quality.sum())
    described = int(scores.has_description.sum())
    lines.append(f"Quality measurements available: {coverage} ({coverage / len(scores):.1%})")
    lines.append(f"Descriptions available: {described} ({described / len(scores):.1%})")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score assignment uncertainty per image")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--quality", type=Path, required=True)
    parser.add_argument("--descriptions", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results"))
    parser.add_argument("--model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--prompt-cache", type=Path, default=Path("data/interim/prompt_vectors.npz"))
    parser.add_argument("--review-threshold", type=float, default=REVIEW_THRESHOLD)
    parser.add_argument(
        "--weights",
        choices=sorted(WEIGHT_SETS),
        default="measured",
        help="component weighting to apply",
    )
    args = parser.parse_args(argv)

    problems = vocab.validate()
    if problems:
        raise ValueError("vocabulary validation failed: " + "; ".join(problems))

    index, embeddings = load_embeddings(args.index, args.embeddings)
    prompts = encode_prompts(args.model, args.prompt_cache)

    thresholds = {}
    if args.thresholds is not None and args.thresholds.exists():
        thresholds = {
            key: float(value)
            for key, value in json.loads(args.thresholds.read_text(encoding="utf-8")).items()
        }
        print(f"Thresholds: {args.thresholds}")
    else:
        print("Thresholds: none supplied; all leading terms retained")

    quality = load_quality(args.quality, index)
    descriptions = load_descriptions(args.descriptions)

    annotations = load_annotations(args.annotations, args.manifest, index)
    reference = embeddings[[int(row) for row in annotations["row_index"]]] if not annotations.empty else np.empty((0, embeddings.shape[1]), dtype="float32")

    print(f"Images: {len(index)}")
    print(f"Quality measurements: {len(quality)}")
    print(f"Descriptions: {len(descriptions)}")
    print(f"Reference images: {len(reference)}")
    weights = WEIGHT_SETS[args.weights]
    print(f"Weights ({args.weights}): " + ", ".join(f"{k} {v:.2f}" for k, v in weights.items()))
    print()

    scores = score_archive(
        index,
        embeddings,
        prompts,
        thresholds,
        quality,
        descriptions,
        reference,
        WEIGHT_SETS[args.weights],
        args.review_threshold,
    )

    print(summarise(scores, args.review_threshold))

    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "uncertainty_scores.csv"
    scores.to_csv(destination, index=False)

    print()
    print(f"Scores: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())