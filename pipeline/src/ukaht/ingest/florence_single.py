"""
florence_single.py
──────────────────
Generates a Florence-2 caption for a single image and stores it in the DB.
Called by the SQS worker after upload.

Usage:
    python -m ukaht.ingest.florence_single \
        --image-path "path/to/image.jpg" \
        --image-uid  "abc123def456..."
"""
import argparse
import os
import sys
from pathlib import Path

import mysql.connector
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from ukaht.config import MODEL_CACHE_DIR, load_config


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-path", required=True)
    parser.add_argument("--image-uid",  required=True)
    return parser.parse_args()


def download_from_s3(s3_path: str, local_path: str):
    import boto3
    s3     = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    bucket = s3_path.replace("s3://", "").split("/")[0]
    key    = "/".join(s3_path.replace("s3://", "").split("/")[1:])
    s3.download_file(bucket, key, local_path)


def main() -> int:
    args   = parse_args()
    config = load_config()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    image_path = args.image_path

    # Download from S3 if needed
    if image_path.startswith("s3://"):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        download_from_s3(image_path, tmp.name)
        image_path = tmp.name

    from transformers import AutoModelForCausalLM, AutoProcessor
    processor = AutoProcessor.from_pretrained("microsoft/Florence-2-base", cache_dir=MODEL_CACHE_DIR, trust_remote_code=True)
    model     = AutoModelForCausalLM.from_pretrained("microsoft/Florence-2-base", cache_dir=MODEL_CACHE_DIR, trust_remote_code=True).to(device)
    model.eval()

    image   = Image.open(image_path).convert("RGB")
    inputs  = processor(text="<MORE_DETAILED_CAPTION>", images=image, return_tensors="pt").to(device)

    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=256)

    caption = processor.decode(output[0], skip_special_tokens=True)
    caption = caption.replace("<MORE_DETAILED_CAPTION>", "").strip()

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
    cursor.execute("SELECT id FROM ai_tags WHERE image_id = %s", (image_id,))
    if cursor.fetchone():
        cursor.execute("UPDATE ai_tags SET caption = %s, model_name = %s WHERE image_id = %s",
            (caption, "microsoft/Florence-2-base", image_id))
    else:
        cursor.execute("INSERT INTO ai_tags (image_id, caption, model_name) VALUES (%s, %s, %s)",
            (image_id, caption, "microsoft/Florence-2-base"))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"florence: {args.image_uid} — {caption[:80]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
