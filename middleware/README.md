# UKAHT Middleware

Express REST API serving the UKAHT Image Archive frontend.

## Setup

```bash
cd middleware
npm install
cp .env.example .env
# fill in your credentials in .env
npm run dev
```

Server runs on `http://localhost:3000`

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | /api/images | Browse with filters |
| GET | /api/images/recent | Recently uploaded images |
| GET | /api/images/:id | Single image detail |
| GET | /api/images/:id/similar | Similar images in same cluster |
| GET | /api/search | CLIP natural language search |
| GET | /api/categories | Category counts for home page |
| POST | /api/upload | Upload image (local dev) |
| GET | /api/upload/presigned-url | S3 pre-signed URL (prod) |
| POST | /api/upload/confirm-s3 | Register S3 upload in DB |
| GET | /api/corrections/queue | Low-confidence images for review |
| GET | /api/corrections/:imageId | Corrections for one image |
| POST | /api/corrections | Submit a correction |
| POST | /api/corrections/confirm | Confirm AI tag without changing |
| GET | /api/clusters | All duplicate clusters |
| PATCH | /api/clusters/:id/representative | Override best image |
| GET | /api/pipeline/status | Processing status counts |
| POST | /api/pipeline/run | Trigger pipeline for new images |
| GET | /api/stats/dataset | Full dataset statistics |
| GET | /api/stats/accuracy | AI accuracy vs corrections |
| GET | /health | Health check |

## Filter parameters for GET /api/images

| Param | Type | Example |
|---|---|---|
| scene_type | string | exterior |
| people_min | number | 1 |
| people_max | number | 5 |
| date_from | date | 2014-01-01 |
| date_to | date | 2020-12-31 |
| quality_min | float | 0.6 |
| best_only | boolean | true |
| no_duplicates | boolean | true |
| tag | string | tent |
| category | string | Exterior |
| sort | string | overall_score |
| order | string | DESC |
| page | number | 1 |
| limit | number | 24 |

## File structure

```
middleware/
  ├── server.js              entry point
  ├── .env.example           credentials template
  ├── README.md              this file
  ├── db/
  │   └── index.js           MySQL connection pool
  ├── routes/
  │   ├── images.js          browse, filter, detail, similar
  │   ├── search.js          CLIP live search
  │   ├── categories.js      home page category counts
  │   ├── upload.js          image upload (local + S3)
  │   ├── corrections.js     tag correction review queue
  │   ├── clusters.js        duplicate cluster review
  │   ├── pipeline.js        pipeline status and trigger
  │   └── stats.js           dataset and accuracy statistics
  └── scripts/
      └── clip_search.py     Python CLIP search (called as subprocess)
```
