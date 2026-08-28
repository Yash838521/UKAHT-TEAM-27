# UKAHT Image Filtering System

Automated description and search for the UK Antarctic Heritage Trust photo
archive.

MSc Data Science group project, University of Bristol, 2026. Team 27: Yash
Pravin Ghorpade, Saisha Prashant Hiray, Ruthreshwaramurthy Pandian, Nithya
Dharshini Uthayasankar.

## The problem

The archive holds 1,009 photos of three historic British Antarctic bases, taken
between 2009 and 2024. Camera metadata is nearly complete: 94.5% of images have
a capture date. Nothing records what any photo shows. You can search the archive
by when a photo was taken but not by what is in it.

This system generates that missing metadata automatically, and indicates how far
each generated label can be trusted.

## How it works

An offline pipeline runs over the archive once, and over new images as they are
uploaded. It extracts camera metadata, computes CLIP embeddings and Florence-2
descriptions, measures sharpness and exposure, groups near-duplicates, assigns
terms from a controlled vocabulary of 176 terms, and scores each image for
uncertainty.

A web application serves the results. It supports natural-language search over
the embeddings, filtering by scene type, room, people, condition and object
tags, duplicate cluster review, and a review queue ordered by uncertainty.
Corrections made by a person override the generated values in later searches.

## Results

| Measure | Value |
|---|---|
| Images processed | 1,007 of 1,009 (2 files unreadable) |
| Vocabulary | 176 terms, 10 facets |
| Client terms covered | 76 of 81 |
| Reference set | 107 images labelled by hand |
| Agreement between two annotators | mean Cohen's kappa 0.843 |
| Threshold calibration | mean F1 0.434 to 0.482 cross-validated |
| Uncertainty against observed error | rho 0.335, p 0.0003 |
| Florence-2 vs BLIP | 0.747 vs 0.209 term corroboration |
| Survey images grouped by embedding clustering | 264 of 291 |

Method and full evaluation are in the project report.

## What is not in this repository

The image archive is confidential and is not included. Nor are the annotation
sheets, which contain image paths, or the embedding files. All are excluded by
`.gitignore`.

Aggregate results contain no image data and are committed under
`evaluation/results/`.

## Layout

```
pipeline/          offline processing
  src/ukaht/
    ingest/          inventory, EXIF, single-image encoding
    enrich/          Florence-2 descriptions
    assess/          quality scoring, duplicate detection
    tagging/         vocabulary, term assignment, calibration, evaluation
    uncertainty/     uncertainty scoring and validation
    db/              loading outputs into MySQL
    api/             embedding search service
    worker/          queue worker for uploads
  config/          model settings, calibrated thresholds
  tests/           vocabulary tests

backend/           Express REST API
frontend/          Angular interface
db/                schema and setup notes
evaluation/        committed results
docs/              vocabulary specification, technical write-up
```

`clip_pipeline.py` and `search_clip.py` are under `tagging/` rather than
`enrich/`. They were written there early on and left in place.

## Setup

Python 3.13, Node 20, Angular CLI 17, MySQL 8.4. The archive path is set in
`pipeline/config/settings.json`.

```bash
cd pipeline
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

CLIP and Florence-2 download on first use, about 2 GB.

## Running the pipeline

Run each stage from the `pipeline` directory with `PYTHONPATH=src`. Stages skip
images they have already processed unless the file has changed, so an
interrupted run can be resumed by issuing the same command again.

Three ordering constraints. Embedding must run before clustering and term
assignment. Clustering must run before quality scoring, which reads cluster
membership to pick a representative image. Term assignment must run before
uncertainty scoring.

```bash
cd pipeline
source .venv/bin/activate

PYTHONPATH=src python -m ukaht.ingest.build_inventory
PYTHONPATH=src python -m ukaht.ingest.extract_exif

PYTHONPATH=src python -m ukaht.tagging.clip_pipeline
PYTHONPATH=src python -m ukaht.enrich.florence_pipeline

PYTHONPATH=src python -m ukaht.assess.duplicate_img
PYTHONPATH=src python -m ukaht.assess.clip_cluster --threshold 0.92 \
    --quality-csv outputs/quality_scores.csv

PYTHONPATH=src python -m ukaht.assess.img_quality \
    --cluster-csv outputs/clip_clusters.csv

PYTHONPATH=src python -m ukaht.tagging.classify_vocabulary

PYTHONPATH=src python -m ukaht.uncertainty.score \
    --index outputs/clip_index.csv \
    --embeddings outputs/clip_embeddings.npy \
    --quality outputs/quality_scores.csv \
    --descriptions outputs/florence_descriptions.csv \
    --annotations ../data/ground_truth/reference.csv \
    --thresholds config/vocabulary_thresholds.json \
    --weights measured \
    --output outputs
```

Output goes to `pipeline/outputs/` as CSV, plus a NumPy array of embeddings. Any
image that fails a stage is written to an error log, so the counts add up to the
number of files supplied.

## Loading the database

```bash
mysql -u root -p < db/SQL/schema.sql
mysql -u root -p < db/SQL/add_uncertainty_columns.sql

cd pipeline
PYTHONPATH=src python -m ukaht.db.load_pipeline_outputs
```

The loader updates existing rows rather than duplicating them, so it can be run
again after a partial pipeline run. Connection settings go in `db/.env`, see
`db/.env.example`.

The RDS certificate bundle is not tracked. Fetch it before deploying:

```bash
curl -O https://truststore.pki.rds.amazonaws.com/global-bundle.pem
```

## Running the application

Three processes.

```bash
cd pipeline
PYTHONPATH=src python -m ukaht.api.search_server

cd backend && npm install && npm start

cd frontend && npm install && npm start
```

The interface runs at `http://localhost:4200`.

A deployed instance runs on AWS. The frontend is served from S3 behind
CloudFront, the API and search service run on EC2, and MySQL runs on RDS. New
uploads are processed through an SQS queue. The deployment was set up through
the AWS console, not as infrastructure code, so there is nothing to run here.

## Reproducing the evaluation

The annotated reference set is not in this repository. With it, each result comes
from one command.

```bash
cd pipeline

PYTHONPATH=src python -c "from ukaht.tagging import vocabulary as v; print(v.summary())"
PYTHONPATH=src python -m pytest tests/test_vocabulary.py -q

PYTHONPATH=src python -m ukaht.tagging.agreement \
    --first ../data/ground_truth/saisha/annotations_saisha.csv \
    --second ../data/ground_truth/yash/annotations_yash.csv \
    --names saisha yash --output ../evaluation/results

PYTHONPATH=src python -m ukaht.tagging.calibration [...]
PYTHONPATH=src python -m ukaht.tagging.cross_validation [...]
PYTHONPATH=src python -m ukaht.uncertainty.validation [...]
PYTHONPATH=src python -m ukaht.tagging.model_comparison [...]
```

Sampling uses fixed seeds: 27 for vocabulary derivation, 91 for validation, 113
for the ground-truth set. Every selection can be reproduced exactly.

Results are in `evaluation/results/`.

## Tests

```bash
cd pipeline
PYTHONPATH=src python -m pytest tests/ -q
```

88 tests on the vocabulary: internal consistency, how many values each facet
takes, that excluded terms stay excluded, and that every term the client asked
for is present.

CI rejects any commit containing image files or credentials.

## Known problems

Image identifiers were generated randomly at first rather than derived from the
file path. Outputs from one pipeline run therefore cannot be joined to outputs
from another. The fix is in `build_inventory.py` but the committed outputs were
produced before it, and applying it means running every stage again.

The condition facet only reaches 0.489 agreement between two annotators. Judging
how much wear counts as wear is a matter of degree, and the six condition terms
force it into a yes or no answer. An ordered scale would work better.

Four structure terms cannot be assigned from the photographs alone. Telling a
generator shed from an emergency shed needs site maps, which were requested from
the client and did not arrive.
