"""
extract_exif.py
───────────────
Extracts EXIF metadata from images listed in inventory.csv
and writes the results to outputs/exif_metadata.csv.

Usage (from the pipeline folder):
    python -m ukaht.ingest.extract_exif

Output:
    outputs/exif_metadata.csv
"""

from pathlib import Path
from fractions import Fraction

import pandas as pd
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from tqdm import tqdm

from ukaht.config import OUTPUT_DIR, load_config
from ukaht.io_utils import (
    ImageRecord,
    atomic_write_csv,
    load_errors,
    load_inventory,
    record_error,
    save_errors,
    utc_now,
)

# ── Output columns ─────────────────────────────────────────────────────────────
EXIF_COLUMNS = [
    "image_uid",
    "file_name",
    "relative_path",
    # Timestamps
    "date_taken",
    "date_digitised",
    # Camera
    "camera_make",
    "camera_model",
    "serial_number",
    "lens_model",
    # Image properties
    "image_width",
    "image_height",
    "orientation",
    "software",
    # Shooting settings
    "iso",
    "exposure_time",
    "f_number",
    "focal_length",
    "flash",
    "white_balance",
    "exposure_program",
    "metering_mode",
    # GPS
    "gps_latitude",
    "gps_longitude",
    "gps_altitude",
    # Extracted at
    "extracted_at",
]

OUTPUT_PATH = OUTPUT_DIR / "exif_metadata.csv"


# ── GPS helpers ────────────────────────────────────────────────────────────────

def _to_decimal_degrees(values, ref: str) -> float | None:
    """Convert GPS DMS tuple to decimal degrees."""
    try:
        def to_float(v):
            if isinstance(v, tuple):
                return v[0] / v[1] if v[1] else 0.0
            if hasattr(v, 'numerator'):          # IFDRational
                return float(v)
            return float(v)

        degrees = to_float(values[0])
        minutes = to_float(values[1])
        seconds = to_float(values[2])
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

        if ref in ('S', 'W'):
            decimal = -decimal
        return round(decimal, 7)
    except Exception:
        return None


def _parse_gps(gps_info: dict) -> tuple[float | None, float | None, float | None]:
    """Extract latitude, longitude, altitude from raw GPS IFD."""
    lat = lon = alt = None

    try:
        lat_val = gps_info.get(2)   # GPSLatitude
        lat_ref = gps_info.get(1)   # GPSLatitudeRef
        if lat_val and lat_ref:
            lat = _to_decimal_degrees(lat_val, lat_ref)
    except Exception:
        pass

    try:
        lon_val = gps_info.get(4)   # GPSLongitude
        lon_ref = gps_info.get(3)   # GPSLongitudeRef
        if lon_val and lon_ref:
            lon = _to_decimal_degrees(lon_val, lon_ref)
    except Exception:
        pass

    try:
        alt_val = gps_info.get(6)   # GPSAltitude
        alt_ref = gps_info.get(5)   # GPSAltitudeRef (0=above, 1=below)
        if alt_val is not None:
            alt_f = float(alt_val)
            if alt_ref == b'\x01':
                alt_f = -alt_f
            alt = round(alt_f, 2)
    except Exception:
        pass

    return lat, lon, alt


# ── Safe value helpers ─────────────────────────────────────────────────────────

def _safe_str(value) -> str | None:
    if value is None:
        return None
    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, tuple) and len(value) == 2:
            return round(value[0] / value[1], 4) if value[1] else None
        if hasattr(value, 'numerator'):
            return round(float(value), 4)
        return round(float(value), 4)
    except Exception:
        return None


def _safe_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _exposure_time_str(value) -> str | None:
    """Convert exposure time to human readable e.g. 1/250."""
    if value is None:
        return None
    try:
        if isinstance(value, tuple) and len(value) == 2:
            num, den = value
        elif hasattr(value, 'numerator'):
            num, den = value.numerator, value.denominator
        else:
            f = float(value)
            frac = Fraction(f).limit_denominator(10000)
            num, den = frac.numerator, frac.denominator

        if den == 0:
            return None
        if num == 1 or den == 1:
            return f"{num}/{den}" if den != 1 else str(num)
        frac = Fraction(num, den)
        return f"{frac.numerator}/{frac.denominator}"
    except Exception:
        return None


# ── EXIF extraction ────────────────────────────────────────────────────────────

def extract_exif(record: ImageRecord) -> dict:
    """
    Open image and extract all EXIF fields.
    Returns a dict with image_uid and all EXIF columns.
    Missing fields are None.
    """
    row: dict = {col: None for col in EXIF_COLUMNS}
    row["image_uid"]     = record.image_uid
    row["file_name"]     = record.file_name
    row["relative_path"] = record.relative_path
    row["extracted_at"]  = utc_now()

    try:
        with Image.open(record.path) as img:
            # Image dimensions — always available even without EXIF
            row["image_width"]  = img.width
            row["image_height"] = img.height

            # Get raw EXIF data
            exif_data = img._getexif()
            if not exif_data:
                return row

            # Build tag name → value map
            tagged = {
                TAGS.get(tag_id, tag_id): value
                for tag_id, value in exif_data.items()
            }

            # ── Timestamps ────────────────────────────────────
            row["date_taken"]     = _safe_str(tagged.get("DateTimeOriginal"))
            row["date_digitised"] = _safe_str(tagged.get("DateTimeDigitized"))

            # Normalise datetime format: "2020:07:24 14:32:11" → "2020-07-24 14:32:11"
            for field in ("date_taken", "date_digitised"):
                if row[field]:
                    row[field] = row[field].replace(":", "-", 2)

            # ── Camera ────────────────────────────────────────
            row["camera_make"]   = _safe_str(tagged.get("Make"))
            row["camera_model"]  = _safe_str(tagged.get("Model"))
            row["serial_number"] = _safe_str(tagged.get("BodySerialNumber") or tagged.get("SerialNumber"))
            row["lens_model"]    = _safe_str(tagged.get("LensModel"))
            row["software"]      = _safe_str(tagged.get("Software"))

            # ── Orientation ───────────────────────────────────
            orientation_map = {
                1: "Horizontal",  2: "Mirror horizontal",
                3: "Rotate 180",  4: "Mirror vertical",
                5: "Mirror horizontal, rotate 270",
                6: "Rotate 90",   7: "Mirror horizontal, rotate 90",
                8: "Rotate 270"
            }
            ori_raw = _safe_int(tagged.get("Orientation"))
            row["orientation"] = orientation_map.get(ori_raw, _safe_str(ori_raw))

            # ── Shooting settings ─────────────────────────────
            row["iso"]              = _safe_int(tagged.get("ISOSpeedRatings") or tagged.get("PhotographicSensitivity"))
            row["exposure_time"]    = _exposure_time_str(tagged.get("ExposureTime"))
            row["f_number"]         = _safe_float(tagged.get("FNumber"))
            row["focal_length"]     = _safe_float(tagged.get("FocalLength"))

            flash_raw = _safe_int(tagged.get("Flash"))
            row["flash"] = "Fired" if flash_raw and (flash_raw & 1) else "Did not fire" if flash_raw is not None else None

            wb_map = { 0: "Auto", 1: "Manual" }
            row["white_balance"] = wb_map.get(_safe_int(tagged.get("WhiteBalance")), None)

            ep_map = {
                0: "Not defined", 1: "Manual",       2: "Normal program",
                3: "Aperture priority", 4: "Shutter priority",
                5: "Creative program", 6: "Action program",
                7: "Portrait mode",    8: "Landscape mode"
            }
            row["exposure_program"] = ep_map.get(_safe_int(tagged.get("ExposureProgram")), None)

            mm_map = {
                1: "Average",    2: "Center weighted",  3: "Spot",
                4: "Multi-spot", 5: "Pattern",          6: "Partial"
            }
            row["metering_mode"] = mm_map.get(_safe_int(tagged.get("MeteringMode")), None)

            # ── GPS ───────────────────────────────────────────
            gps_raw = tagged.get("GPSInfo")
            if gps_raw and isinstance(gps_raw, dict):
                lat, lon, alt = _parse_gps(gps_raw)
                row["gps_latitude"]  = lat
                row["gps_longitude"] = lon
                row["gps_altitude"]  = alt

    except Exception as error:
        # Return partial row — caller handles error logging
        raise error

    return row


# ── Main ───────────────────────────────────────────────────────────────────────

def run_exif(records: list[ImageRecord]) -> None:
    """
    Extract EXIF from all records and write to exif_metadata.csv.
    Skips images that have already been processed unless the file changed.
    """
    errors = load_errors()

    # Load existing results so we don't reprocess unchanged images
    existing: dict[str, dict] = {}
    if OUTPUT_PATH.exists():
        df_existing = pd.read_csv(OUTPUT_PATH, dtype=str)
        existing = {
            row["image_uid"]: row
            for row in df_existing.to_dict(orient="records")
            if row.get("image_uid")
        }

    rows     = []
    skipped  = 0
    failed   = 0
    processed = 0

    for record in tqdm(records, desc="Extracting EXIF"):
        # If already extracted and file hasn't changed — reuse
        if record.image_uid in existing:
            rows.append(existing[record.image_uid])
            skipped += 1
            continue

        try:
            row = extract_exif(record)
            rows.append(row)
            processed += 1
            # Clear any previous error for this image
            clear_error_exif(errors, record.image_uid)
        except Exception as error:
            # Log error — keep partial row with just uid/filename
            record_error(errors, record, "EXIF", error)
            rows.append({
                "image_uid":     record.image_uid,
                "file_name":     record.file_name,
                "relative_path": record.relative_path,
                "extracted_at":  utc_now(),
                **{col: None for col in EXIF_COLUMNS
                   if col not in ("image_uid", "file_name", "relative_path", "extracted_at")}
            })
            failed += 1

    # Write output
    df = pd.DataFrame(rows, columns=EXIF_COLUMNS)
    atomic_write_csv(df, OUTPUT_PATH)
    save_errors(errors)

    print(f"\nEXIF extraction complete:")
    print(f"  Processed : {processed}")
    print(f"  Skipped   : {skipped} (already extracted)")
    print(f"  Failed    : {failed}")
    print(f"  Output    : {OUTPUT_PATH}")
    if failed > 0:
        print(f"  Errors    : {OUTPUT_DIR / 'processing_errors.csv'}")


def clear_error_exif(errors: list[dict], image_uid: str) -> None:
    """Remove any previous EXIF error for this image_uid."""
    errors[:] = [
        row for row in errors
        if not (row.get("image_uid") == image_uid and row.get("model") == "EXIF")
    ]


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    config  = load_config()
    records = load_inventory(config)
    print(f"Loaded {len(records)} images from inventory")
    run_exif(records)


if __name__ == "__main__":
    main()