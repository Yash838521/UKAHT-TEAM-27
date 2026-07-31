# Database Setup Guide

This guide walks you through setting up the local MySQL database for the UKAHT Image Archive project.

---

## Prerequisites

Before starting, make sure you have the following installed:

- [MySQL Community Server 8.0+](https://dev.mysql.com/downloads/installer/) — choose **Developer Default** during setup and **make sure you remember the root password you set**, as you will need it in every step below
- [MySQL Workbench](https://dev.mysql.com/downloads/workbench/) — installed alongside MySQL
- [Python 3.8+](https://www.python.org/downloads/)
- [Anaconda](https://www.anaconda.com/) (optional but recommended)

---

## Step 1 — Install Python dependencies

```bash
pip install mysql-connector-python pandas python-dotenv
```

---

## Step 2 — Create your `.env` file

Both `.env` and `.env.example` are located in the `db/` folder. Copy the example file:

```bash
cp db/.env.example db/.env
```

Then fill in your local MySQL credentials:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=ukaht
```

**Never commit your `.env` file to Git.** It is already listed in `.gitignore`.

---

## Step 3 — Create the database and tables

The schema file is located at `db\SQL\schema.sql` from the project root. It creates the `ukaht` database and all required tables automatically.

**Option A — MySQL Workbench**

Open MySQL Workbench, connect to your local instance (`localhost:3306`), open `db\SQL\schema.sql` from the repository, and run it using the lightning bolt button or `Ctrl+Shift+Enter`.

**Option B — Command line**

```bash
mysql -u root -p < db/SQL/schema.sql
```

Enter your root password when prompted.

---

## Step 4 — Load the EXIF metadata

Make sure the `metadata_report.csv` file is in the project root (`team27-UKAHT/`), then run:

```bash
python db/scripts/load_exif_metadata.py
```

This will:
- Read all JPEG images from the CSV
- Insert one row per image into the `images` and `exif_metadata` tables
- Create empty placeholder rows in `ai_tags`, `quality_scores`, `duplicate_clusters`, and `embeddings`

Expected output:

```
Loading 1007 images...
  1/1007 processed...
  101/1007 processed...
  ...
Done. 1007 inserted, 0 errors.
```

---

## Step 5 — Verify the setup

Run this in MySQL Workbench to confirm all tables have rows:

```sql
USE ukaht;

SELECT 'images'            AS tbl, COUNT(*) AS rows FROM images
UNION ALL
SELECT 'exif_metadata',             COUNT(*) FROM exif_metadata
UNION ALL
SELECT 'ai_tags',                   COUNT(*) FROM ai_tags
UNION ALL
SELECT 'quality_scores',            COUNT(*) FROM quality_scores
UNION ALL
SELECT 'duplicate_clusters',        COUNT(*) FROM duplicate_clusters
UNION ALL
SELECT 'embeddings',                COUNT(*) FROM embeddings
UNION ALL
SELECT 'corrections',               COUNT(*) FROM corrections;
```

You should see **1007 rows** in `images`, `exif_metadata`, `ai_tags`, `quality_scores`, `duplicate_clusters`, and `embeddings`. The `corrections` table will be empty — this is expected.

---

## Step 6 — Mock data (frontend and middleware development only)

**Only run this step if you are working on the frontend (React/Angular) or middleware (Express API).**

The mock script fills the database with realistic but artificially generated AI tags, quality scores, category assignments, duplicate clusters, and embeddings. This allows you to develop and test the UI and API without waiting for the real AI pipeline to run.

**Do NOT run this script if you are working on the AI/data pipeline.** Running it will overwrite the empty placeholder rows with fake data, which will interfere with your real pipeline output.

If you are working on frontend or middleware, run:

```bash
python db/scripts/mock/generate_mock_data.py
```

This will populate:

| Table | What gets filled |
|---|---|
| `ai_tags` | scene type, people count, object tags, categories (JSON), model name |
| `quality_scores` | sharpness, exposure, overall score, best-in-group flag |
| `duplicate_clusters` | cluster IDs, similarity scores, representative flags |
| `embeddings` | mock 8-float proxy vectors (not real CLIP embeddings) |
| `corrections` | 12 sample human corrections across 2 reviewers |

Expected output:

```
Found 1007 images to mock

Step 1: Populating ai_tags + categories...
  856 tagged, 151 failed

Step 2: Populating quality_scores...
  1007 quality scores populated

Step 3: Populating duplicate_clusters...
  120 images in 48 duplicate clusters
  887 images have no duplicates

Step 4: Populating embeddings...
  856 embeddings populated, 151 skipped

Step 5: Adding sample human corrections...
  12 corrections inserted across 2 reviewers

── Summary ───────────────────────────────────
ai_tags populated:              856
ai_tags failed/empty:           151
images with categories:         856
quality_scores populated:       1007
...
Done — database ready for frontend and middleware development.
```

---

## Resetting the database

If you need to start fresh, run this in MySQL Workbench:

```sql
USE ukaht;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE corrections;
TRUNCATE TABLE embeddings;
TRUNCATE TABLE duplicate_clusters;
TRUNCATE TABLE quality_scores;
TRUNCATE TABLE ai_tags;
TRUNCATE TABLE exif_metadata;
TRUNCATE TABLE images;
SET FOREIGN_KEY_CHECKS = 1;
```

Then re-run `db/scripts/load_exif_metadata.py` from Step 4.

---

## File structure reference

```
team27-UKAHT/
  ├── metadata_report.csv          <- source data (do not commit)
  ├── db/
  │   ├── .env                     <- your local credentials (do not commit)
  │   ├── .env.example             <- template (committed)
  │   ├── DATABASE_SETUP.md        <- this file
  │   ├── SQL/
  │   │   └── schema.sql           <- full database schema (committed)
  │   └── scripts/
  │       ├── load_exif_metadata.py <- run once to load real data
  │       └── mock/
  │           └── generate_mock_data.py <- run only for FE/middleware dev
  └── ...
```