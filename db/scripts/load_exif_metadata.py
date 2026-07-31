import os
from dotenv import load_dotenv
import pandas as pd
import mysql.connector
from datetime import datetime

CSV_PATH = '../metadata_report.csv'

# load .env
load_dotenv()

def parse_date(val):
    try:
        return datetime.strptime(str(val).strip(), '%Y:%m:%d %H:%M:%S')
    except:
        return None

def safe_int(val):
    try:
        return int(float(str(val).strip()))
    except:
        return None

def safe_str(val):
    s = str(val).strip()
    return None if s in ('', 'nan', 'None') else s

def parse_gps(val):
    try:
        s = str(val).strip()
        if s in ('', 'nan', 'None'):
            return None
        if s[-1] in ('N', 'E'):
            return float(s[:-1].strip())
        elif s[-1] in ('S', 'W'):
            return -float(s[:-1].strip())
        return float(s)
    except:
        return None

# Connect to MySQL
conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)
cursor = conn.cursor()

# Load and filter CSV
df = pd.read_csv(CSV_PATH)
df = df[df['FileType'] == 'JPEG'].copy()
df = df.reset_index(drop=True)

print(f"\nLoading {len(df)} images...")

success = 0
errors  = 0

for i, row in df.iterrows():
    try:
        # 1. images
        cursor.execute("""
            INSERT INTO images (filename, storage_url)
            VALUES (%s, %s)
        """, (
            safe_str(row['FileName']),
            safe_str(row['SourceFile'])
        ))
        image_id = cursor.lastrowid

        # 2. exif_metadata
        cursor.execute("""
            INSERT INTO exif_metadata (
                image_id,
                date_taken,
                camera_make,
                camera_model,
                serial_number,
                lens_model,
                image_width,
                image_height,
                iso,
                flash,
                white_balance,
                orientation,
                software,
                gps_latitude,
                gps_longitude
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
        """, (
            image_id,
            parse_date(row['DateTimeOriginal']),
            safe_str(row['Make']),
            safe_str(row['Model']),
            safe_str(row['SerialNumber']),
            safe_str(row['LensModel']),
            safe_int(row['ImageWidth']),
            safe_int(row['ImageHeight']),
            safe_int(row['ISO']),
            safe_str(row['Flash']),
            safe_str(row['WhiteBalance']),
            safe_str(row['Orientation']),
            safe_str(row['Software']),
            parse_gps(row.get('GPSLatitude')),
            parse_gps(row.get('GPSLongitude'))
        ))

        # 3. ai_tags (empty — categories JSON populated by AI pipeline later)
        cursor.execute(
            "INSERT INTO ai_tags (image_id) VALUES (%s)",
            (image_id,)
        )

        # 4. quality_scores (empty)
        cursor.execute(
            "INSERT INTO quality_scores (image_id) VALUES (%s)",
            (image_id,)
        )

        # 5. duplicate_clusters (empty)
        cursor.execute(
            "INSERT INTO duplicate_clusters (image_id) VALUES (%s)",
            (image_id,)
        )

        # 6. embeddings (empty)
        cursor.execute(
            "INSERT INTO embeddings (image_id) VALUES (%s)",
            (image_id,)
        )

        # corrections stays empty — only populated when humans make corrections

        success += 1

        if i % 100 == 0:
            conn.commit()
            print(f"  {i + 1}/{len(df)} processed...")

    except Exception as e:
        errors += 1
        print(f"  Error on row {i} ({row.get('FileName', '?')}): {e}")
        conn.rollback()

conn.commit()
cursor.close()
conn.close()

print(f"\nDone. {success} inserted, {errors} errors.")