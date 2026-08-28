import os
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json

import mysql.connector
import numpy as np
import torch
from transformers import CLIPModel, CLIPProcessor

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from ukaht.config import MODEL_CACHE_DIR, load_config

ABSOLUTE_FLOOR = float(os.environ.get("SEARCH_FLOOR", "0.20"))  # never return below this

print("Loading CLIP model...")
config    = load_config()
device    = "cuda" if torch.cuda.is_available() else "cpu"
processor = CLIPProcessor.from_pretrained(config.clip_model, cache_dir=MODEL_CACHE_DIR)
model     = CLIPModel.from_pretrained(config.clip_model, cache_dir=MODEL_CACHE_DIR).to(device)
model.eval()
print(f"Ready. Device: {device} | Absolute floor: {ABSOLUTE_FLOOR}")


def get_db_conn():
    return mysql.connector.connect(
        host     = os.environ.get("DB_HOST",     "localhost"),
        port     = int(os.environ.get("DB_PORT",  3306)),
        user     = os.environ.get("DB_USER",     "root"),
        password = os.environ.get("DB_PASSWORD", ""),
        database = os.environ.get("DB_NAME",     "ukaht"),
    )


def encode_query(query: str) -> np.ndarray:
    inputs = processor(text=[query], padding=True, return_tensors="pt").to(device)
    with torch.no_grad():
        features = model.get_text_features(**inputs)
        features = features / features.norm(dim=-1, keepdim=True)
    return features[0].cpu().numpy().astype("float32")


def dynamic_threshold(scores: np.ndarray) -> float:
    best = float(scores.max())
    mean = float(scores.mean())
    std  = float(scores.std())

    relative  = best - 0.10 
    absolute  = mean + (2 * std)
    threshold = max(relative, absolute)

    return max(threshold, ABSOLUTE_FLOOR)


def search_db(query_vector: np.ndarray, top_k: int) -> list[dict]:
    conn   = get_db_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT image_uid, vector_json
        FROM embeddings
        WHERE vector_json IS NOT NULL
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return []

    image_uids = [row[0] for row in rows]
    matrix     = np.array([json.loads(row[1]) for row in rows], dtype="float32")

    # Cosine similarity — embeddings already normalised
    scores    = matrix @ query_vector
    threshold = dynamic_threshold(scores)

    results = [
        {"image_uid": uid, "similarity_score": float(score)}
        for uid, score in zip(image_uids, scores)
        if float(score) >= threshold
    ]

    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:top_k]


class SearchHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        query  = params.get("q", [""])[0].strip()
        top_k  = int(params.get("top_k", ["200"])[0])

        if not query:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"q is required"}')
            return

        try:
            query_vector = encode_query(query)
            results      = search_db(query_vector, top_k)
            body         = json.dumps(results).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        except Exception as err:
            body = json.dumps({"error": str(err)}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("SEARCH_PORT", 5001))
    print(f"Search server running on port {port}")
    HTTPServer(("localhost", port), SearchHandler).serve_forever()