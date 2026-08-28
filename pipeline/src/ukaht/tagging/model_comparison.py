"""Comparison of generative description models against human annotation.

Two captioning models produce free text for the same images. Free text cannot be
compared with human annotation directly, since a description and a set of terms
are different kinds of object. The comparison is therefore made through
corroboration: for each term a human assigned to an image, the description is
examined for expressions that a description of that subject would be expected to
contain, and the proportion of terms so corroborated is recorded.

This measures how far a description supports the terms a person considered
applicable, which is the property that matters when descriptions are used as
evidence for retrieval.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import pandas as pd

from ukaht.tagging import vocabulary as vocab
from ukaht.uncertainty.score import TERM_LEXICON

MEASURED_FACETS = ("scene_type", "room", "nature", "condition", "shot_type")

CAPTION_COLUMNS = (
    "image_uid",
    "file_name",
    "model",
    "caption",
    "word_count",
    "runtime_seconds",
)


def load_reference(path: Path) -> list[dict]:
    """Load the annotated reference set."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle) if any(row.values())]


def resolve_paths(reference: list[dict], archive: Path) -> list[tuple[dict, Path]]:
    """Attach a filesystem path to each reference record."""
    resolved = []
    for row in reference:
        relative = (row.get("relative_path") or "").strip()
        if not relative:
            continue
        path = archive / relative
        if path.exists():
            resolved.append((row, path))
    return resolved


def generate_blip(
    records: list[tuple[dict, Path]], model_name: str, destination: Path
) -> None:
    """Generate captions for the reference images and write them out."""
    import torch
    from PIL import Image
    from transformers import BlipForConditionalGeneration, BlipProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading {model_name} on {device}")

    processor = BlipProcessor.from_pretrained(model_name)
    model = BlipForConditionalGeneration.from_pretrained(model_name).to(device)
    model.eval()

    rows = []
    for position, (row, path) in enumerate(records, start=1):
        started = time.perf_counter()
        try:
            with Image.open(path) as source:
                image = source.convert("RGB")
                inputs = processor(images=image, return_tensors="pt").to(device)
                with torch.no_grad():
                    output = model.generate(**inputs, max_new_tokens=40, num_beams=3)
                caption = processor.decode(output[0], skip_special_tokens=True).strip()
        except Exception as error:
            print(f"  {path.name}: {error}")
            caption = ""

        elapsed = time.perf_counter() - started
        rows.append(
            {
                "image_uid": row["image_uid"],
                "file_name": row.get("file_name", path.name),
                "model": "BLIP",
                "caption": caption,
                "word_count": len(caption.split()),
                "runtime_seconds": round(elapsed, 3),
            }
        )

        if position % 20 == 0:
            print(f"  {position} of {len(records)}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=list(CAPTION_COLUMNS)).to_csv(destination, index=False)
    print(f"Captions written: {destination}")


def load_florence(path: Path, wanted: set[str]) -> dict[str, str]:
    """Load existing descriptions for the reference images."""
    frame = pd.read_csv(path, dtype=str).fillna("")
    return {
        str(row["image_uid"]).strip(): str(row["description"]).strip()
        for row in frame.to_dict(orient="records")
        if str(row["image_uid"]).strip() in wanted
    }


def _values(cell: object) -> list[str]:
    return [part.strip() for part in str(cell or "").split("|") if part.strip()]


def corroboration(description: str, row: dict) -> tuple[int, int]:
    """Return terms corroborated and terms checked for one image."""
    if not description:
        return 0, 0

    text = description.lower()
    checked = corroborated = 0

    for facet_key in MEASURED_FACETS:
        for term_key in _values(row.get(facet_key)):
            expressions = TERM_LEXICON.get(term_key)
            if not expressions:
                continue
            checked += 1
            if any(expression in text for expression in expressions):
                corroborated += 1

    return corroborated, checked


def evaluate(
    reference: list[dict], captions: dict[str, str], label: str
) -> dict[str, float]:
    """Return corroboration and length statistics for one model."""
    by_uid = {row["image_uid"]: row for row in reference}

    total_corroborated = total_checked = 0
    per_image = []
    lengths = []
    empty = 0

    for image_uid, description in captions.items():
        row = by_uid.get(image_uid)
        if row is None:
            continue
        if not description:
            empty += 1
            continue

        lengths.append(len(description.split()))
        corroborated, checked = corroboration(description, row)
        total_corroborated += corroborated
        total_checked += checked
        if checked:
            per_image.append(corroborated / checked)

    return {
        "model": label,
        "images": len(per_image),
        "empty_captions": empty,
        "terms_checked": total_checked,
        "terms_corroborated": total_corroborated,
        "corroboration_rate": round(total_corroborated / total_checked, 4)
        if total_checked
        else 0.0,
        "mean_per_image": round(sum(per_image) / len(per_image), 4) if per_image else 0.0,
        "mean_words": round(sum(lengths) / len(lengths), 1) if lengths else 0.0,
        "min_words": min(lengths) if lengths else 0,
        "max_words": max(lengths) if lengths else 0,
    }


def paired_comparison(
    reference: list[dict], first: dict[str, str], second: dict[str, str]
) -> dict[str, int]:
    """Return per-image wins on images described by both models."""
    by_uid = {row["image_uid"]: row for row in reference}
    shared = set(first) & set(second) & set(by_uid)

    first_better = second_better = tied = 0

    for image_uid in shared:
        row = by_uid[image_uid]
        a_corr, a_checked = corroboration(first[image_uid], row)
        b_corr, b_checked = corroboration(second[image_uid], row)
        if not a_checked or not b_checked:
            continue
        a_rate, b_rate = a_corr / a_checked, b_corr / b_checked
        if a_rate > b_rate:
            first_better += 1
        elif b_rate > a_rate:
            second_better += 1
        else:
            tied += 1

    return {
        "compared": first_better + second_better + tied,
        "first_better": first_better,
        "second_better": second_better,
        "tied": tied,
    }


def format_report(results: list[dict], paired: dict[str, int]) -> str:
    """Return a readable comparison of the two models."""
    lines = [
        f"{'model':<14}{'images':>8}{'checked':>9}{'corrob.':>9}"
        f"{'rate':>8}{'per image':>11}{'words':>8}",
        "-" * 67,
    ]

    for item in results:
        lines.append(
            f"{item['model']:<14}{item['images']:>8}{item['terms_checked']:>9}"
            f"{item['terms_corroborated']:>9}{item['corroboration_rate']:>8.3f}"
            f"{item['mean_per_image']:>11.3f}{item['mean_words']:>8.1f}"
        )

    lines.append("")
    lines.append("Per-image comparison on images described by both")
    lines.append(f"  images compared     : {paired['compared']}")
    lines.append(f"  Florence-2 stronger : {paired['second_better']}")
    lines.append(f"  BLIP stronger       : {paired['first_better']}")
    lines.append(f"  equal               : {paired['tied']}")

    lines.append("")
    lines.append(
        "Corroboration measures the proportion of human-assigned terms for which"
    )
    lines.append(
        "the description contains a corresponding expression. It is bounded above"
    )
    lines.append("by the coverage of the expression lists and is comparable between")
    lines.append("models only because both are measured against the same lists.")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare generative description models against human annotation"
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--reference", type=Path, default=Path("data/ground_truth/reference.csv")
    )
    parser.add_argument(
        "--florence", type=Path, default=Path("data/interim/florence_descriptions.csv")
    )
    parser.add_argument(
        "--blip-output",
        type=Path,
        default=Path("evaluation/results/blip_reference_captions.csv"),
    )
    parser.add_argument("--blip-model", default="Salesforce/blip-image-captioning-base")
    parser.add_argument(
        "--output", type=Path, default=Path("evaluation/results")
    )
    parser.add_argument(
        "--skip-generation",
        action="store_true",
        help="use an existing caption file rather than generating",
    )
    args = parser.parse_args(argv)

    problems = vocab.validate()
    if problems:
        raise ValueError("vocabulary validation failed: " + "; ".join(problems))

    reference = load_reference(args.reference)
    print(f"Reference images: {len(reference)}")

    if not args.skip_generation:
        archive = args.archive.expanduser().resolve()
        records = resolve_paths(reference, archive)
        print(f"Images resolved on disk: {len(records)}")
        if not records:
            print("No reference images could be located; check --archive")
            return 1
        generate_blip(records, args.blip_model, args.blip_output)

    if not args.blip_output.exists():
        print(f"Caption file not found: {args.blip_output}")
        return 1

    blip_frame = pd.read_csv(args.blip_output, dtype=str).fillna("")
    blip = {
        str(row["image_uid"]).strip(): str(row["caption"]).strip()
        for row in blip_frame.to_dict(orient="records")
    }

    wanted = {row["image_uid"] for row in reference}
    florence = load_florence(args.florence, wanted)

    print(f"BLIP captions: {len(blip)}")
    print(f"Florence-2 descriptions: {len(florence)}")
    print()

    results = [
        evaluate(reference, blip, "BLIP"),
        evaluate(reference, florence, "Florence-2"),
    ]
    paired = paired_comparison(reference, blip, florence)

    print(format_report(results, paired))

    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "model_comparison.csv"
    pd.DataFrame(results).to_csv(destination, index=False)

    print()
    print(f"Summary: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
