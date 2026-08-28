import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import mysql.connector
import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from ukaht.config import MODEL_CACHE_DIR, PROJECT_DIR, load_config

PEOPLE_COUNT_MAP = {
    "no_people":    0,
    "one_person":   1,
    "two_people":   2,
    "three_people": 3,
    "group":        4,
}

SCENE_FACET       = "scene_type"
PEOPLE_FACET      = "people"
SITE_FACET        = "site"
STRUCTURED_FACETS = {SCENE_FACET, PEOPLE_FACET, SITE_FACET}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-path", required=True)
    parser.add_argument("--image-uid",  required=True)
    return parser.parse_args()


def download_from_s3(s3_path: str) -> str:
    import boto3
    s3     = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    bucket = s3_path.replace("s3://", "").split("/")[0]
    key    = "/".join(s3_path.replace("s3://", "").split("/")[1:])
    suffix = Path(key).suffix or ".jpg"
    tmp    = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    s3.download_file(bucket, key, tmp.name)
    return tmp.name


def main() -> int:
    args   = parse_args()
    config = load_config()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    image_path = args.image_path
    tmp_path   = None

    if image_path.startswith("s3://"):
        tmp_path   = download_from_s3(image_path)
        image_path = tmp_path

    try:
        prompt_vectors_path = PROJECT_DIR / "data" / "interim" / "prompt_vectors.npz"
        if not prompt_vectors_path.exists():
            print(f"prompt_vectors.npz not found at {prompt_vectors_path}")
            return 1

        prompt_data = np.load(prompt_vectors_path, allow_pickle=True)
        facets      = prompt_data["facets"].tolist()

        processor = CLIPProcessor.from_pretrained(config.clip_model, cache_dir=MODEL_CACHE_DIR)
        model     = CLIPModel.from_pretrained(config.clip_model, cache_dir=MODEL_CACHE_DIR).to(device)
        model.eval()

        image  = Image.open(image_path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt").to(device)

        with torch.no_grad():
            image_features = model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        image_vec = image_features[0].cpu().numpy().astype("float32")

        ai_data = {
            "scene_type": None, "scene_confidence": None,
            "people_count": None, "people_confidence": None,
            "tags": [], "categories": [],
        }

        for facet in facets:
            term_keys = prompt_data[f"{facet}__keys"].tolist()
            vectors   = prompt_data[f"{facet}__vectors"].astype("float32")

            scores     = vectors @ image_vec
            best_idx   = int(scores.argmax())
            best_key   = term_keys[best_idx]
            best_score = float(scores[best_idx])

            threshold = None
            if hasattr(config, "thresholds") and isinstance(config.thresholds, dict):
                threshold = config.thresholds.get(facet)

            if facet == SCENE_FACET:
                ai_data["scene_type"]       = best_key
                ai_data["scene_confidence"] = best_score

            elif facet == PEOPLE_FACET:
                ai_data["people_count"]      = PEOPLE_COUNT_MAP.get(best_key)
                ai_data["people_confidence"] = best_score

            elif facet == SITE_FACET:
                ai_data["categories"].append({
                    "category": best_key, "facet": facet,
                    "term_key": best_key, "confidence": best_score, "is_primary": True,
                })

            elif facet not in STRUCTURED_FACETS:
                if threshold is None or best_score >= threshold:
                    ai_data["tags"].append({
                        "tag": best_key, "facet": facet,
                        "term_key": best_key, "confidence": best_score, "source": "clip",
                    })

        conn   = mysql.connector.connect(
            host     = os.environ.get("DB_HOST",     "localhost"),
            port     = int(os.environ.get("DB_PORT",  3306)),
            user     = os.environ.get("DB_USER",     "root"),
            password = os.environ.get("DB_PASSWORD", ""),
            database = os.environ.get("DB_NAME",     "ukaht"),
        )
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM images WHERE image_uid = %s", (args.image_uid,))
        row = cursor.fetchone()
        if not row:
            print(f"image_uid not found: {args.image_uid}")
            return 1

        image_id = row[0]
        values = (
            ai_data["scene_type"], ai_data["scene_confidence"],
            ai_data["people_count"], ai_data["people_confidence"],
            json.dumps(ai_data["tags"]),
            json.dumps(ai_data["categories"]),
            f"{config.clip_model} + microsoft/Florence-2-base",
        )

        cursor.execute("SELECT id FROM ai_tags WHERE image_id = %s", (image_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE ai_tags SET
                    scene_type=%s, scene_confidence=%s,
                    people_count=%s, people_confidence=%s,
                    tags=%s, categories=%s, model_name=%s
                WHERE image_id = %s
            """, values + (image_id,))
        else:
            cursor.execute("""
                INSERT INTO ai_tags (image_id, scene_type, scene_confidence,
                    people_count, people_confidence, tags, categories, model_name, is_verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE)
            """, (image_id,) + values)

        conn.commit()
        cursor.close()
        conn.close()
        print(f"vocabulary: {args.image_uid} — scene={ai_data['scene_type']} people={ai_data['people_count']}")
        return 0

    finally:
        if tmp_path:
            try: os.unlink(tmp_path)
            except: pass


if __name__ == "__main__":
    raise SystemExit(main())