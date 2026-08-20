import argparse
import json
import os
import sys
from pathlib import Path

import mysql.connector
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from ukaht.config import MODEL_CACHE_DIR, load_config


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-path", required=True)
    parser.add_argument("--image-uid",  required=True)
    return parser.parse_args()


def main() -> int:
    args   = parse_args()
    config = load_config()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    processor = CLIPProcessor.from_pretrained(config.clip_model, cache_dir=MODEL_CACHE_DIR)
    model     = CLIPModel.from_pretrained(config.clip_model, cache_dir=MODEL_CACHE_DIR).to(device)
    model.eval()

    image  = Image.open(args.image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(device)

    with torch.no_grad():
        features = model.get_image_features(**inputs)
        features = features / features.norm(dim=-1, keepdim=True)

    vector      = features[0].cpu().numpy().astype("float32")
    vector_json = json.dumps(vector.tolist())

    conn   = mysql.connector.connect(
        host     = os.environ.get("DB_HOST",     "localhost"),
        port     = int(os.environ.get("DB_PORT",  3306)),
        user     = os.environ.get("DB_USER",     "root"),
        password = os.environ.get("DB_PASSWORD", ""),
        database = os.environ.get("DB_NAME",     "ukaht"),
    )
    cursor = conn.cursor()

    # Find image_id from image_uid
    cursor.execute("SELECT id FROM images WHERE image_uid = %s", (args.image_uid,))
    row = cursor.fetchone()
    if not row:
        print(f"image_uid not found: {args.image_uid}")
        return 1

    image_id = row[0]

    cursor.execute("SELECT id FROM embeddings WHERE image_id = %s", (image_id,))
    if cursor.fetchone():
        cursor.execute("""
            UPDATE embeddings SET vector_json=%s, model_name=%s WHERE image_id=%s
        """, (vector_json, config.clip_model, image_id))
    else:
        cursor.execute("""
            INSERT INTO embeddings (image_id, image_uid, vector_json, model_name)
            VALUES (%s, %s, %s, %s)
        """, (image_id, args.image_uid, vector_json, config.clip_model))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"encoded: {args.image_uid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())