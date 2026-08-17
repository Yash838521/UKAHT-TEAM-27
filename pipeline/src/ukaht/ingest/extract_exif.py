from pathlib import Path
from fractions import Fraction

import pandas as pd
from PIL import Image
from PIL.ExifTags import TAGS
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


EXIF_COLUMNS = [
    "image_uid", "file_name", "relative_path",
    "date_taken", "date_digitised",
    "camera_make", "camera_model", "serial_number", "lens_model",
    "image_width", "image_height", "orientation", "software",
    "iso", "exposure_time", "f_number", "focal_length",
    "flash", "white_balance", "exposure_program", "metering_mode",
    "gps_latitude", "gps_longitude", "gps_altitude",
    "extracted_at",
]

OUTPUT_PATH = OUTPUT_DIR / "exif_metadata.csv"

ORIENTATION_MAP = {
    1: "Horizontal", 2: "Mirror horizontal", 3: "Rotate 180",
    4: "Mirror vertical", 5: "Mirror horizontal, rotate 270",
    6: "Rotate 90", 7: "Mirror horizontal, rotate 90", 8: "Rotate 270",
}

EXPOSURE_PROGRAM_MAP = {
    0: "Not defined", 1: "Manual", 2: "Normal program",
    3: "Aperture priority", 4: "Shutter priority", 5: "Creative program",
    6: "Action program", 7: "Portrait mode", 8: "Landscape mode",
}

METERING_MODE_MAP = {
    1: "Average", 2: "Center weighted", 3: "Spot",
    4: "Multi-spot", 5: "Pattern", 6: "Partial",
}

WHITE_BALANCE_MAP = {0: "Auto", 1: "Manual"}


def _str(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _float(value) -> float | None:
    try:
        if isinstance(value, tuple) and len(value) == 2:
            return round(value[0] / value[1], 4) if value[1] else None
        if hasattr(value, "numerator"):
            return round(float(value), 4)
        return round(float(value), 4) if value is not None else None
    except Exception:
        return None


def _exposure_time(value) -> str | None:
    try:
        if isinstance(value, tuple) and len(value) == 2:
            num, den = value
        elif hasattr(value, "numerator"):
            num, den = value.numerator, value.denominator
        else:
            frac = Fraction(float(value)).limit_denominator(10000)
            num, den = frac.numerator, frac.denominator
        if den == 0:
            return None
        frac = Fraction(num, den)
        return f"{frac.numerator}/{frac.denominator}"
    except Exception:
        return None


def _dms_to_decimal(values, ref: str) -> float | None:
    try:
        def to_float(v):
            if isinstance(v, tuple):
                return v[0] / v[1] if v[1] else 0.0
            return float(v)
        decimal = to_float(values[0]) + to_float(values[1]) / 60 + to_float(values[2]) / 3600
        return round(-decimal if ref in ("S", "W") else decimal, 7)
    except Exception:
        return None


def _parse_gps(gps_info: dict) -> tuple[float | None, float | None, float | None]:
    lat = lon = alt = None
    try:
        if gps_info.get(2) and gps_info.get(1):
            lat = _dms_to_decimal(gps_info[2], gps_info[1])
    except Exception:
        pass
    try:
        if gps_info.get(4) and gps_info.get(3):
            lon = _dms_to_decimal(gps_info[4], gps_info[3])
    except Exception:
        pass
    try:
        if gps_info.get(6) is not None:
            alt = round(float(gps_info[6]) * (-1 if gps_info.get(5) == b"\x01" else 1), 2)
    except Exception:
        pass
    return lat, lon, alt


def extract_exif(record: ImageRecord) -> dict:
    row: dict = {col: None for col in EXIF_COLUMNS}
    row.update({
        "image_uid":     record.image_uid,
        "file_name":     record.file_name,
        "relative_path": record.relative_path,
        "extracted_at":  utc_now(),
    })

    with Image.open(record.path) as img:
        row["image_width"]  = img.width
        row["image_height"] = img.height
        exif_data = img._getexif()
        if not exif_data:
            return row

    tagged = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}

    row["date_taken"]     = _str(tagged.get("DateTimeOriginal"))
    row["date_digitised"] = _str(tagged.get("DateTimeDigitized"))

    for field in ("date_taken", "date_digitised"):
        if row[field]:
            row[field] = row[field].replace(":", "-", 2)

    row["camera_make"]   = _str(tagged.get("Make"))
    row["camera_model"]  = _str(tagged.get("Model"))
    row["serial_number"] = _str(tagged.get("BodySerialNumber") or tagged.get("SerialNumber"))
    row["lens_model"]    = _str(tagged.get("LensModel"))
    row["software"]      = _str(tagged.get("Software"))
    row["orientation"]   = ORIENTATION_MAP.get(_int(tagged.get("Orientation")))
    row["iso"]           = _int(tagged.get("ISOSpeedRatings") or tagged.get("PhotographicSensitivity"))
    row["exposure_time"] = _exposure_time(tagged.get("ExposureTime"))
    row["f_number"]      = _float(tagged.get("FNumber"))
    row["focal_length"]  = _float(tagged.get("FocalLength"))
    row["white_balance"]     = WHITE_BALANCE_MAP.get(_int(tagged.get("WhiteBalance")))
    row["exposure_program"]  = EXPOSURE_PROGRAM_MAP.get(_int(tagged.get("ExposureProgram")))
    row["metering_mode"]     = METERING_MODE_MAP.get(_int(tagged.get("MeteringMode")))

    flash_raw    = _int(tagged.get("Flash"))
    row["flash"] = "Fired" if flash_raw and (flash_raw & 1) else "Did not fire" if flash_raw is not None else None

    gps_raw = tagged.get("GPSInfo")
    if gps_raw and isinstance(gps_raw, dict):
        row["gps_latitude"], row["gps_longitude"], row["gps_altitude"] = _parse_gps(gps_raw)

    return row


def _clear_exif_error(errors: list[dict], image_uid: str) -> None:
    errors[:] = [r for r in errors if not (r.get("image_uid") == image_uid and r.get("model") == "EXIF")]


def run_exif(records: list[ImageRecord]) -> None:
    errors = load_errors()

    existing: dict[str, dict] = {}
    if OUTPUT_PATH.exists():
        existing = {
            row["image_uid"]: row
            for row in pd.read_csv(OUTPUT_PATH, dtype=str).to_dict(orient="records")
            if row.get("image_uid")
        }

    rows = []
    processed = skipped = failed = 0

    for record in tqdm(records, desc="Extracting EXIF"):
        if record.image_uid in existing:
            rows.append(existing[record.image_uid])
            skipped += 1
            continue

        try:
            rows.append(extract_exif(record))
            _clear_exif_error(errors, record.image_uid)
            processed += 1
        except Exception as error:
            record_error(errors, record, "EXIF", error)
            rows.append({
                "image_uid": record.image_uid, "file_name": record.file_name,
                "relative_path": record.relative_path, "extracted_at": utc_now(),
                **{col: None for col in EXIF_COLUMNS
                   if col not in ("image_uid", "file_name", "relative_path", "extracted_at")},
            })
            failed += 1

    atomic_write_csv(pd.DataFrame(rows, columns=EXIF_COLUMNS), OUTPUT_PATH)
    save_errors(errors)

    print(f"processed={processed} skipped={skipped} failed={failed}")
    print(f"output: {OUTPUT_PATH}")


def main() -> None:
    config  = load_config()
    records = load_inventory(config)
    print(f"loaded {len(records)} images from inventory")
    run_exif(records)


if __name__ == "__main__":
    main()