import os
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from ukaht.tagging.search_clip import ClipSearchEngine

SIMILARITY_THRESHOLD = float(os.environ.get("SEARCH_THRESHOLD", "0.25"))

print("Loading CLIP model...")
engine = ClipSearchEngine()
print(f"Ready. Similarity threshold: {SIMILARITY_THRESHOLD}")


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

        results = engine.search(query, top_k)

        output = [
            {
                "image_uid":        row["image_uid"],
                "similarity_score": float(row["similarity_score"]),
            }
            for _, row in results.iterrows()
            if float(row["similarity_score"]) >= SIMILARITY_THRESHOLD
        ]

        body = json.dumps(output).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("SEARCH_PORT", 5001))
    print(f"Search server running on port {port}")
    HTTPServer(("localhost", port), SearchHandler).serve_forever()