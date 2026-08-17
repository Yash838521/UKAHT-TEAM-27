import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from ukaht.config import MODEL_CACHE_DIR, OUTPUT_DIR, PROJECT_DIR, load_config
from ukaht.io_utils import atomic_write_csv
from ukaht.tagging import vocabulary as vocab


OUTPUT_COLUMNS = [
    "image_uid",
    "file_name",
    "facet",
    "term_key",
    "label",
    "similarity_score",
    "source",
    "vocabulary_version",
]

SITE_MARKERS = {
    "_A_": "base_a",
    "_W_": "base_w",
    "_E_": "base_e",
    "_F_": "base_f",
    "_Y_": "base_y",
}

STRUCTURE_TERMS = {"main_hut", "outbuilding"}


def load_thresholds(path: Path) -> dict[str, float]:
    values = json.loads(path.read_text(encoding="utf-8"))
    return {key: float(value) for key, value in values.items()}


def load_clip_files() -> tuple[pd.DataFrame, np.ndarray]:
    index_path = OUTPUT_DIR / "clip_index.csv"
    embedding_path = OUTPUT_DIR / "clip_embeddings.npy"

    if not index_path.exists() or not embedding_path.exists():
        raise FileNotFoundError(
            "CLIP index files were not found. Run the CLIP pipeline first."
        )

    index = pd.read_csv(index_path, dtype=str).fillna("")
    embeddings = np.load(embedding_path).astype("float32")
    if len(index) != len(embeddings):
        raise ValueError("CLIP index and embedding row counts do not match")
    return index, embeddings


def text_vectors(
    prompts: list[str],
    processor: Any,
    model: Any,
    device: str,
) -> np.ndarray:
    inputs = processor(
        text=prompts,
        padding=True,
        truncation=True,
        return_tensors="pt",
    )
    inputs = {name: value.to(device) for name, value in inputs.items()}

    with torch.no_grad():
        features = model.get_text_features(**inputs)
        features = features / features.norm(dim=-1, keepdim=True)

    return features.cpu().numpy().astype("float32")


def site_from_path(relative_path: str) -> str:
    upper_path = relative_path.upper()
    for marker, term_key in SITE_MARKERS.items():
        if marker in upper_path:
            return term_key
    return "site_unknown"


def result_row(
    image: dict,
    facet_key: str,
    term_key: str,
    score: float | None,
    source: str,
) -> dict:
    term = vocab.facet(facet_key).get(term_key)
    if term is None:
        raise KeyError(f"Unknown vocabulary term: {facet_key}.{term_key}")

    return {
        "image_uid": image["image_uid"],
        "file_name": image["file_name"],
        "facet": facet_key,
        "term_key": term_key,
        "label": term.label,
        "similarity_score": "" if score is None else round(float(score), 6),
        "source": source,
        "vocabulary_version": vocab.VERSION,
    }


def best_term(scores: dict[str, float]) -> tuple[str, float]:
    return max(scores.items(), key=lambda item: item[1])


def scores_for_facet(
    image_vector: np.ndarray,
    facet_key: str,
    prompt_vectors: dict[str, tuple[list[str], np.ndarray]],
) -> dict[str, float]:
    keys, vectors = prompt_vectors[facet_key]
    scores = vectors @ image_vector
    return {key: float(score) for key, score in zip(keys, scores)}


def classify_image(
    image: dict,
    image_vector: np.ndarray,
    prompt_vectors: dict[str, tuple[list[str], np.ndarray]],
    thresholds: dict[str, float],
) -> list[dict]:
    rows = []

    site_key = site_from_path(image["relative_path"])
    rows.append(result_row(image, "site", site_key, None, "directory_path"))

    scene_scores = scores_for_facet(
        image_vector, "scene_type", prompt_vectors
    )
    scene_key, scene_score = best_term(scene_scores)
    rows.append(
        result_row(image, "scene_type", scene_key, scene_score, "clip")
    )

    shot_scores = scores_for_facet(image_vector, "shot_type", prompt_vectors)
    shot_key, shot_score = best_term(shot_scores)
    rows.append(result_row(image, "shot_type", shot_key, shot_score, "clip"))

    people_scores = scores_for_facet(image_vector, "people", prompt_vectors)
    people_key, people_score = best_term(people_scores)
    if people_score < thresholds["people"]:
        people_key = "no_people"
        people_score = None
        people_source = "threshold_rule"
    else:
        people_source = "clip"
    rows.append(
        result_row(
            image,
            "people",
            people_key,
            people_score,
            people_source,
        )
    )

    if scene_key == "interior":
        room_scores = scores_for_facet(image_vector, "room", prompt_vectors)
        room_key, room_score = best_term(room_scores)
        if room_score < thresholds["room"]:
            rows.append(
                result_row(
                    image,
                    "room",
                    "room_unknown",
                    None,
                    "threshold_rule",
                )
            )
        else:
            rows.append(result_row(image, "room", room_key, room_score, "clip"))

    if scene_key == "exterior":
        structure_scores = scores_for_facet(
            image_vector, "structure", prompt_vectors
        )
        for term_key, score in structure_scores.items():
            if term_key in STRUCTURE_TERMS and score >= thresholds["structure"]:
                rows.append(
                    result_row(image, "structure", term_key, score, "clip")
                )

    if people_key != "no_people":
        for facet_key in ["orientation", "activity"]:
            facet_scores = scores_for_facet(
                image_vector, facet_key, prompt_vectors
            )
            for term_key, score in facet_scores.items():
                if score >= thresholds[facet_key]:
                    rows.append(
                        result_row(image, facet_key, term_key, score, "clip")
                    )

    for facet_key in ["nature", "condition"]:
        facet_scores = scores_for_facet(image_vector, facet_key, prompt_vectors)
        for term_key, score in facet_scores.items():
            if score >= thresholds[facet_key]:
                rows.append(result_row(image, facet_key, term_key, score, "clip"))

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify saved CLIP embeddings with the required vocabulary"
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=PROJECT_DIR / "config" / "vocabulary_thresholds.json",
    )
    args = parser.parse_args()

    problems = vocab.validate()
    if problems:
        raise ValueError("Vocabulary validation failed: " + "; ".join(problems))

    config = load_config()
    index, embeddings = load_clip_files()
    thresholds = load_thresholds(args.thresholds)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    from transformers import CLIPModel, CLIPProcessor

    processor: Any = CLIPProcessor.from_pretrained(
        config.clip_model,
        cache_dir=MODEL_CACHE_DIR,
    )
    model: Any = CLIPModel.from_pretrained(
        config.clip_model,
        cache_dir=MODEL_CACHE_DIR,
    )
    model = model.to(torch.device(device))
    model.eval()

    prompt_vectors = {}
    for facet_key, prompts in vocab.all_prompts().items():
        keys = list(prompts)
        vectors = text_vectors(
            [prompts[key] for key in keys],
            processor,
            model,
            device,
        )
        prompt_vectors[facet_key] = (keys, vectors)

    output_rows = []
    for image, image_vector in zip(index.to_dict(orient="records"), embeddings):
        output_rows.extend(
            classify_image(
                image,
                image_vector,
                prompt_vectors,
                thresholds,
            )
        )

    output_path = OUTPUT_DIR / "clip_vocabulary_tags.csv"
    atomic_write_csv(pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS), output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
