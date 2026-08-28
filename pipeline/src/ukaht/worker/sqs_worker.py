"""
sqs_worker.py
─────────────
Polls SQS for new image upload messages and runs the full pipeline
on each image automatically.

Processes per image:
  1. CLIP encoding      → embeddings.vector_json
  2. Florence caption   → ai_tags.caption
  3. Quality scoring    → quality_scores
  4. Vocabulary tags    → ai_tags.scene_type, tags, categories

Start with PM2:
  pm2 start --name pipeline-worker --interpreter python3 -- -m ukaht.worker.sqs_worker
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import boto3
import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

PIPELINE_DIR = Path(__file__).resolve().parents[3]
PYTHON       = sys.executable
SQS_REGION   = os.environ.get("AWS_REGION", "eu-west-2")
QUEUE_URL    = os.environ.get("SQS_QUEUE_URL", "")


def get_db_conn():
    return mysql.connector.connect(
        host     = os.environ.get("DB_HOST",     "localhost"),
        port     = int(os.environ.get("DB_PORT",  3306)),
        user     = os.environ.get("DB_USER",     "root"),
        password = os.environ.get("DB_PASSWORD", ""),
        database = os.environ.get("DB_NAME",     "ukaht"),
    )


def mark_processed(image_uid: str, success: bool):
    try:
        conn   = get_db_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE images SET processed = %s WHERE image_uid = %s",
            (success, image_uid)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as err:
        print(f"DB update failed: {err}")


def run_script(module: str, image_uid: str, image_path: str) -> bool:
    env = {
        **os.environ,
        "PYTHONPATH":           str(PIPELINE_DIR / "src"),
        "KMP_DUPLICATE_LIB_OK": "TRUE",
    }
    result = subprocess.run(
        [PYTHON, "-m", module,
         "--image-uid",  image_uid,
         "--image-path", image_path],
        cwd = PIPELINE_DIR,
        env = env,
        capture_output = True,
        text = True,
    )
    if result.stdout: print(result.stdout.strip())
    if result.stderr: print(result.stderr.strip())
    return result.returncode == 0


def process_image(image_uid: str, image_path: str):
    print(f"processing: {image_uid}")

    steps = [
        ("ukaht.ingest.encode_single",      "CLIP encoding"),
        ("ukaht.assess.quality_single",     "quality scoring"),
        ("ukaht.tagging.vocabulary_single", "vocabulary tags"),
        ("ukaht.ingest.florence_single",    "Florence caption"),
    ]

    all_success = True
    for module, label in steps:
        print(f"  {label}...")
        ok = run_script(module, image_uid, image_path)
        if not ok:
            print(f"  {label} FAILED")
            all_success = False

    mark_processed(image_uid, all_success)
    print(f"done: {image_uid} — success={all_success}")


def main():
    if not QUEUE_URL:
        print("SQS_QUEUE_URL not set — exiting")
        sys.exit(1)

    sqs = boto3.client("sqs", region_name=SQS_REGION)
    print(f"SQS worker started — polling {QUEUE_URL}")

    while True:
        try:
            response = sqs.receive_message(
                QueueUrl            = QUEUE_URL,
                MaxNumberOfMessages = 1,
                WaitTimeSeconds     = 20,   # long polling
            )

            for msg in response.get("Messages", []):
                try:
                    body      = json.loads(msg["Body"])
                    image_uid = body.get("image_uid")
                    image_path = body.get("image_path")

                    if image_uid and image_path:
                        process_image(image_uid, image_path)
                    else:
                        print(f"invalid message: {body}")

                except Exception as err:
                    print(f"message processing error: {err}")

                finally:
                    # Always delete message — even if processing failed
                    # Failed images will have processed=FALSE in DB
                    sqs.delete_message(
                        QueueUrl      = QUEUE_URL,
                        ReceiptHandle = msg["ReceiptHandle"]
                    )

        except Exception as err:
            print(f"SQS error: {err}")
            time.sleep(5)


if __name__ == "__main__":
    main()
