import argparse
import json
import os
import sys
from pathlib import Path

import mysql.connector
import pandas as pd


PIPELINE_DIR = Path(__file__).resolve().parents[3]
OUTPUT_DIR   = PIPELINE_DIR / "outputs"
DATA_DIR     = PIPELINE_DIR / "data"

CSV_PATHS = {
    "inventory":  DATA_DIR   / "inventory.csv",
    "exif":       OUTPUT_DIR / "exif_metadata.csv",
    "florence":   OUTPUT_DIR / "florence_descriptions.csv",
    "vocabulary": OUTPUT_DIR / "clip_vocabulary_tags.csv",
    "clip_index": OUTPUT_DIR / "clip_index.csv",
    "quality":    OUTPUT_DIR / "quality_scores.csv",
    "clusters":   OUTPUT_DIR / "clusters.csv",
}

SCENE_FACET       = "scene_type"
PEOPLE_FACET      = "people"
SITE_FACET        = "site"
STRUCTURED_FACETS = {SCENE_FACET, PEOPLE_FACET, SITE_FACET}

PEOPLE_COUNT_MAP = {
    "no_people":    0,
    "one_person":   1,
    "two_people":   2,
    "three_people": 3,
    "group":        4,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host",     default=os.environ.get("DB_HOST",     "localhost"))
    parser.add_argument("--port",     default=int(os.environ.get("DB_PORT",  3306)), type=int)
    parser.add_argument("--user",     default=os.environ.get("DB_USER",     "root"))
    parser.add_argument("--password", default=os.environ.get("DB_PASSWORD", ""))
    parser.add_argument("--database", default=os.environ.get("DB_NAME",     "ukaht"))
    parser.add_argument(
        "--steps",
        nargs="+",
        default=["images", "inventory", "exif", "florence", "vocabulary", "embeddings", "quality", "clusters"],
        choices=["images", "inventory", "exif", "florence", "vocabulary", "embeddings", "quality", "clusters"],
    )
    return parser.parse_args()


def connect(args):
    config = {
        "host":     args.host,
        "port":     args.port,
        "user":     args.user,
        "password": args.password,
        "database": args.database,
    }
    if args.host not in ("localhost", "127.0.0.1"):
        config["ssl_disabled"] = False
    try:
        return mysql.connector.connect(**config)
    except mysql.connector.Error as err:
        print(f"Connection failed: {err}")
        sys.exit(1)


def uid_map(cursor) -> dict[str, int]:
    cursor.execute("SELECT id, image_uid FROM images WHERE image_uid IS NOT NULL")
    return {row[1]: row[0] for row in cursor.fetchall()}


def filename_map(cursor) -> dict[str, int]:
    cursor.execute("SELECT id, filename FROM images")
    return {row[1]: row[0] for row in cursor.fetchall()}


def s(row, col) -> str | None:
    v = str(row.get(col, "")).strip()
    return v if v else None

def i(row, col) -> int | None:
    v = s(row, col)
    try: return int(float(v)) if v else None
    except: return None

def f(row, col) -> float | None:
    v = s(row, col)
    try: return float(v) if v else None
    except: return None


def load_images(cursor, conn):
    path = CSV_PATHS["inventory"]
    if not path.exists():
        print(f"inventory.csv not found at {path}")
        return

    df       = pd.read_csv(path, dtype=str).fillna("")
    base     = os.environ.get("LOCAL_IMAGE_BASE", "")
    inserted = skipped = 0

    for _, row in df.iterrows():
        file_name     = s(row, "file_name")
        relative_path = s(row, "relative_path")
        if not file_name or not relative_path:
            continue

        storage_url = f"{base}/{relative_path}".replace("\\", "/") if base else relative_path

        cursor.execute("SELECT id FROM images WHERE filename = %s", (file_name,))
        if cursor.fetchone():
            skipped += 1
            continue

        cursor.execute("""
            INSERT INTO images (filename, storage_url, uploaded_at, processed)
            VALUES (%s, %s, NOW(), FALSE)
        """, (file_name, storage_url))
        inserted += 1

    conn.commit()
    print(f"images: inserted={inserted} skipped={skipped}")


def load_inventory(cursor, conn):
    path = CSV_PATHS["inventory"]
    if not path.exists():
        print(f"inventory.csv not found at {path}")
        return

    df    = pd.read_csv(path, dtype=str).fillna("")
    fmap  = filename_map(cursor)
    updated = skipped = missing = 0

    for _, row in df.iterrows():
        image_uid = s(row, "image_uid")
        file_name = s(row, "file_name")
        if not image_uid or not file_name:
            continue

        image_id = fmap.get(file_name)
        if not image_id:
            print(f"  not in images table: {file_name}")
            missing += 1
            continue

        cursor.execute(
            "UPDATE images SET image_uid = %s WHERE id = %s AND (image_uid IS NULL OR image_uid = '')",
            (image_uid, image_id),
        )
        updated += 1 if cursor.rowcount > 0 else 0
        skipped += 1 if cursor.rowcount == 0 else 0

    conn.commit()
    print(f"inventory: updated={updated} skipped={skipped} missing={missing}")


def load_exif(cursor, conn):
    path = CSV_PATHS["exif"]
    if not path.exists():
        print(f"exif_metadata.csv not found at {path}")
        return

    df   = pd.read_csv(path, dtype=str).fillna("")
    umap = uid_map(cursor)
    inserted = updated = missing = 0

    for _, row in df.iterrows():
        image_id = umap.get(s(row, "image_uid"))
        if not image_id:
            missing += 1
            continue

        values = (
            s(row, "date_taken"),    s(row, "date_digitised"),
            s(row, "camera_make"),   s(row, "camera_model"),
            s(row, "serial_number"), s(row, "lens_model"),
            i(row, "image_width"),   i(row, "image_height"),
            s(row, "orientation"),   s(row, "software"),
            i(row, "iso"),           s(row, "exposure_time"),
            f(row, "f_number"),      f(row, "focal_length"),
            s(row, "flash"),         s(row, "white_balance"),
            s(row, "exposure_program"), s(row, "metering_mode"),
            f(row, "gps_latitude"),  f(row, "gps_longitude"), f(row, "gps_altitude"),
        )

        cursor.execute("SELECT id FROM exif_metadata WHERE image_id = %s", (image_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE exif_metadata SET
                    date_taken=%s, date_digitised=%s,
                    camera_make=%s, camera_model=%s, serial_number=%s, lens_model=%s,
                    image_width=%s, image_height=%s, orientation=%s, software=%s,
                    iso=%s, exposure_time=%s, f_number=%s, focal_length=%s,
                    flash=%s, white_balance=%s, exposure_program=%s, metering_mode=%s,
                    gps_latitude=%s, gps_longitude=%s, gps_altitude=%s
                WHERE image_id = %s
            """, values + (image_id,))
            updated += 1
        else:
            cursor.execute("""
                INSERT INTO exif_metadata (
                    image_id,
                    date_taken, date_digitised,
                    camera_make, camera_model, serial_number, lens_model,
                    image_width, image_height, orientation, software,
                    iso, exposure_time, f_number, focal_length,
                    flash, white_balance, exposure_program, metering_mode,
                    gps_latitude, gps_longitude, gps_altitude
                ) VALUES (%s, %s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s)
            """, (image_id,) + values)
            inserted += 1

    conn.commit()
    print(f"exif: inserted={inserted} updated={updated} missing={missing}")


def load_ai_tags(cursor, conn):
    vocab_path    = CSV_PATHS["vocabulary"]
    florence_path = CSV_PATHS["florence"]

    if not vocab_path.exists() and not florence_path.exists():
        print("neither vocabulary nor florence CSV found")
        return

    umap = uid_map(cursor)

    captions: dict[str, str] = {}
    if florence_path.exists():
        df = pd.read_csv(florence_path, dtype=str).fillna("")
        for _, row in df.iterrows():
            uid  = s(row, "image_uid")
            desc = s(row, "description")
            if uid and desc:
                captions[uid] = desc

    ai_data: dict[str, dict] = {}
    if vocab_path.exists():
        df = pd.read_csv(vocab_path, dtype=str).fillna("")
        for _, row in df.iterrows():
            uid      = s(row, "image_uid")
            facet    = s(row, "facet")
            term_key = s(row, "term_key")
            label    = s(row, "label")
            score    = f(row, "similarity_score")
            source   = s(row, "source")

            if not uid or not facet:
                continue

            if uid not in ai_data:
                ai_data[uid] = {
                    "scene_type": None, "scene_confidence": None,
                    "people_count": None, "people_confidence": None,
                    "tags": [], "categories": [],
                }

            if facet == SCENE_FACET:
                ai_data[uid]["scene_type"]       = term_key
                ai_data[uid]["scene_confidence"] = score

            elif facet == PEOPLE_FACET:
                ai_data[uid]["people_count"]      = PEOPLE_COUNT_MAP.get(term_key)
                ai_data[uid]["people_confidence"] = score

            elif facet == SITE_FACET:
                ai_data[uid]["categories"].append({
                    "category": label, "facet": facet,
                    "term_key": term_key, "confidence": score, "is_primary": True,
                })

            elif facet not in STRUCTURED_FACETS:
                ai_data[uid]["tags"].append({
                    "tag": label, "facet": facet,
                    "term_key": term_key, "confidence": score, "source": source,
                })

    inserted = updated = missing = 0

    for uid in set(ai_data.keys()) | set(captions.keys()):
        image_id = umap.get(uid)
        if not image_id:
            missing += 1
            continue

        data   = ai_data.get(uid, {})
        values = (
            data.get("scene_type"),    data.get("scene_confidence"),
            data.get("people_count"),  data.get("people_confidence"),
            json.dumps(data.get("tags", [])),
            json.dumps(data.get("categories", [])),
            captions.get(uid),
            "openai/clip-vit-base-patch32 + microsoft/Florence-2-base",
        )

        cursor.execute("SELECT id FROM ai_tags WHERE image_id = %s", (image_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE ai_tags SET
                    scene_type=%s, scene_confidence=%s,
                    people_count=%s, people_confidence=%s,
                    tags=%s, categories=%s, caption=%s, model_name=%s
                WHERE image_id = %s
            """, values + (image_id,))
            updated += 1
        else:
            cursor.execute("""
                INSERT INTO ai_tags (
                    image_id,
                    scene_type, scene_confidence,
                    people_count, people_confidence,
                    tags, categories, caption, model_name, is_verified
                ) VALUES (%s, %s,%s, %s,%s, %s,%s,%s,%s, FALSE)
            """, (image_id,) + values)
            inserted += 1

    conn.commit()
    print(f"ai_tags: inserted={inserted} updated={updated} missing={missing}")


def load_embeddings(cursor, conn):
    path = CSV_PATHS["clip_index"]
    if not path.exists():
        print(f"clip_index.csv not found at {path}")
        return

    df   = pd.read_csv(path, dtype=str).fillna("")
    umap = uid_map(cursor)
    inserted = updated = missing = 0

    for _, row in df.iterrows():
        image_uid = s(row, "image_uid")
        image_id  = umap.get(image_uid)
        if not image_id:
            missing += 1
            continue

        values = (
            image_uid,
            i(row, "row_index"),
            s(row, "model") or "openai/clip-vit-base-patch32",
            s(row, "file_hash"),
        )

        cursor.execute("SELECT id FROM embeddings WHERE image_id = %s", (image_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE embeddings SET
                    image_uid=%s, row_index=%s, model_name=%s, file_hash=%s
                WHERE image_id = %s
            """, values + (image_id,))
            updated += 1
        else:
            cursor.execute("""
                INSERT INTO embeddings (image_id, image_uid, row_index, model_name, file_hash)
                VALUES (%s, %s, %s, %s, %s)
            """, (image_id,) + values)
            inserted += 1

    conn.commit()
    print(f"embeddings: inserted={inserted} updated={updated} missing={missing}")


def load_quality(cursor, conn):
    path = CSV_PATHS["quality"]
    if not path.exists():
        print(f"quality_scores.csv not found at {path}")
        return

    df   = pd.read_csv(path, dtype=str).fillna("")
    umap = uid_map(cursor)
    inserted = updated = missing = 0

    for _, row in df.iterrows():
        image_id = umap.get(s(row, "image_uid"))
        if not image_id:
            missing += 1
            continue

        values = (
            f(row, "sharpness_score"),
            f(row, "exposure_score"),
            f(row, "overall_score"),
            s(row, "is_best_in_group") in ("True","true","1","yes"),
        )

        cursor.execute("SELECT id FROM quality_scores WHERE image_id = %s", (image_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE quality_scores SET
                    sharpness_score=%s, exposure_score=%s,
                    overall_score=%s, is_best_in_group=%s
                WHERE image_id = %s
            """, values + (image_id,))
            updated += 1
        else:
            cursor.execute("""
                INSERT INTO quality_scores (image_id, sharpness_score, exposure_score, overall_score, is_best_in_group)
                VALUES (%s, %s, %s, %s, %s)
            """, (image_id,) + values)
            inserted += 1

    conn.commit()
    print(f"quality: inserted={inserted} updated={updated} missing={missing}")


def load_clusters(cursor, conn):
    path = CSV_PATHS["clusters"]
    if not path.exists():
        print(f"clusters.csv not found at {path}")
        return

    df   = pd.read_csv(path, dtype=str).fillna("")
    umap = uid_map(cursor)
    inserted = updated = missing = 0

    for _, row in df.iterrows():
        image_id = umap.get(s(row, "image_uid"))
        if not image_id:
            missing += 1
            continue

        values = (
            i(row, "cluster_id"),
            f(row, "similarity_score"),
            s(row, "is_representative") in ("True","true","1","yes"),
        )

        cursor.execute("SELECT id FROM duplicate_clusters WHERE image_id = %s", (image_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE duplicate_clusters SET
                    cluster_id=%s, similarity_score=%s, is_representative=%s
                WHERE image_id = %s
            """, values + (image_id,))
            updated += 1
        else:
            cursor.execute("""
                INSERT INTO duplicate_clusters (image_id, cluster_id, similarity_score, is_representative)
                VALUES (%s, %s, %s, %s)
            """, (image_id,) + values)
            inserted += 1

    conn.commit()
    print(f"clusters: inserted={inserted} updated={updated} missing={missing}")


def main() -> int:
    args   = parse_args()
    conn   = connect(args)
    cursor = conn.cursor()

    print(f"connected to {args.database} on {args.host}")
    print(f"steps: {', '.join(args.steps)}")

    try:
        if "images"     in args.steps: load_images(cursor, conn)
        if "inventory"  in args.steps: load_inventory(cursor, conn)
        if "exif"       in args.steps: load_exif(cursor, conn)
        if "florence"   in args.steps or "vocabulary" in args.steps: load_ai_tags(cursor, conn)
        if "embeddings" in args.steps: load_embeddings(cursor, conn)
        if "quality"    in args.steps: load_quality(cursor, conn)
        if "clusters"   in args.steps: load_clusters(cursor, conn)
    except Exception as err:
        print(f"error: {err}")
        conn.rollback()
        return 1
    finally:
        cursor.close()
        conn.close()

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())