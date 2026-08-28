import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pipeline" / "src"))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from ukaht.tagging.search_clip import ClipSearchEngine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query",  required=True, type=str)
    parser.add_argument("--top-k",  type=int, default=24)
    args = parser.parse_args()

    try:
        engine  = ClipSearchEngine()
        results = engine.search(args.query, args.top_k)
        output  = [
            {
                "image_uid":        row["image_uid"],
                "similarity_score": float(row["similarity_score"]),
            }
            for _, row in results.iterrows()
        ]
        print(json.dumps(output))
        return 0
    except Exception as err:
        print(json.dumps({"error": str(err)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())