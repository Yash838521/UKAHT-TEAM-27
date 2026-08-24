"""
quality_single.py
─────────────────
Scores quality for a single image and stores it in the DB.
Called by the SQS worker after upload.

Usage:
    python -m ukaht.assess.quality_single \
        --image-path "path/to/image.jpg" \
        --image-uid  "abc123def456..."
"""
import argparse
import os
import sys
from pathlib import Path

import cv2
import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from ukaht.config import load_config


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-path", required=True)
    parser.add_argument("--image-uid",  required=True)
    parser.add_argument("--sharpness-ref", type=float, default=500.0)
    return parser.parse_args()


def download_from_s3(s3_path: str, local_path: str):
    import boto3
    s3     = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    bucket = s3_path.replace("s3://", "").split("/")[0]
    key    = "/".join(s3_path.replace("s3://", "").split("/")[1:])
    s3.download_file(bucket, key, local_path)


def get_sharpness_score(grey_img,ref_max=500.0):
    laplacian_result = cv2.Laplacian(grey_img,cv2.CV_64F)
    sharpness_val = laplacian_result.var()
    score = sharpness_val/ref_max
    return round(max(0.0,min(1.0,score)),4)

def get_exposure_score(grey_img):
    histogram = cv2.calcHist([grey_img],[0],None,[256],[0,256]).flatten()
    total_pixels = grey_img.size
    dark_clipped_pct = (histogram[0:5].sum()/total_pixels)*100
    bright_clipped_pct = (histogram[251:256].sum()/total_pixels)*100
    avg_brightness = grey_img.mean()
    total_clipped = dark_clipped_pct+bright_clipped_pct
    clipping_score = max(1.0-(total_clipped*0.03),0)
    dist_from_middle = abs(avg_brightness-128)
    brightness_score = max(1.0-(dist_from_middle/128),0)
    return round((0.6*clipping_score)+(0.4*brightness_score),4)


def main() -> int:
    args = parse_args()

    image_path = args.image_path

    # Download from S3 if needed
    if image_path.startswith("s3://"):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        download_from_s3(image_path, tmp.name)
        image_path = tmp.name

    img = cv2.imread(image_path)
    if img is None:
        print(f"cv2 could not read {image_path}")
        return 1

    grey_img        = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    sharpness_score = get_sharpness_score(grey_img,args.sharpness_ref)
    exposure_score  = get_exposure_score(grey_img)
    overall_score   = round((sharpness_score+exposure_score)/2,4)

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
    cursor.execute("SELECT id FROM quality_scores WHERE image_id = %s", (image_id,))
    if cursor.fetchone():
        cursor.execute("""
            UPDATE quality_scores SET
                sharpness_score=%s, exposure_score=%s, overall_score=%s
            WHERE image_id = %s
        """, (sharpness_score, exposure_score, overall_score, image_id))
    else:
        cursor.execute("""
            INSERT INTO quality_scores (image_id, sharpness_score, exposure_score, overall_score)
            VALUES (%s, %s, %s, %s)
        """, (image_id, sharpness_score, exposure_score, overall_score))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"quality: {args.image_uid} — sharpness={sharpness_score} exposure={exposure_score} overall={overall_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
