import argparse
import json
import os
import sys
import tempfile
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

    # Download from S3 if needed
    if image_path.startswith("s3://"):
        tmp_path   = download_from_s3(image_path)
        image_path = tmp_path

    try:
        processor = CLIPProcessor.from_pretrained(config.clip_model, cache_dir=MODEL_CACHE_DIR)
        model     = CLIPModel.from_pretrained(config.clip_model, cache_dir=MODEL_CACHE_DIR).to(device)
        model.eval()

        image  = Image.open(image_path).convert("RGB")
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

    finally:
        if tmp_path:
            try: os.unlink(tmp_path)
            except: pass


if __name__ == "__main__":
    raise SystemExit(main())