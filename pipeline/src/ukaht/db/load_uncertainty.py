"""Loading of uncertainty scores into the tag table.

Uncertainty is computed per image from four signals whose inputs are not
retained in the database. It therefore cannot be derived at query time and is
loaded alongside the assigned terms.
"""

from __future__ import annotations

import csv
from pathlib import Path

COLUMNS = (
    "uncertainty_score",
    "confidence_component",
    "quality_component",
    "agreement_component",
    "novelty_component",
    "uncertainty_reason",
    "review_recommended",
)


def uid_map(cursor) -> dict[str, int]:
    cursor.execute("SELECT id, image_uid FROM images WHERE image_uid IS NOT NULL")
    return {uid: image_id for image_id, uid in cursor.fetchall()}


def load_uncertainty(cursor, conn, path: Path) -> None:
    """Write per-image uncertainty values against existing tag rows."""
    if not path.exists():
        print(f"uncertainty file not found at {path}")
        return

    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.DictReader(handle) if any(row.values())]

    images = uid_map(cursor)
    updated = missing = 0

    for row in rows:
        image_id = images.get(str(row.get("image_uid", "")).strip())
        if image_id is None:
            missing += 1
            continue

        cursor.execute(
            """
            UPDATE ai_tags SET
                uncertainty_score    = %s,
                confidence_component = %s,
                quality_component    = %s,
                agreement_component  = %s,
                novelty_component    = %s,
                uncertainty_reason   = %s,
                review_recommended   = %s
            WHERE image_id = %s
            """,
            (
                float(row["uncertainty_score"]),
                float(row["confidence_component"]),
                float(row["quality_component"]),
                float(row["agreement_component"]),
                float(row["novelty_component"]),
                row["reason"][:255],
                str(row["review_recommended"]).strip().lower() in ("true", "1"),
                image_id,
            ),
        )
        updated += cursor.rowcount

    conn.commit()
    print(f"uncertainty: updated={updated} unmatched={missing}")
