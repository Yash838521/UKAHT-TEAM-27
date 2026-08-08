import argparse
from typing import Any

import numpy as np
import pandas as pd
import torch

from ukaht.config import MODEL_CACHE_DIR, OUTPUT_DIR, load_config


class ClipSearchEngine:
    def __init__(self):
        from transformers import CLIPModel, CLIPProcessor

        self.config = load_config()
        index_path = OUTPUT_DIR / "clip_index.csv"
        embedding_path = OUTPUT_DIR / "clip_embeddings.npy"

        if not index_path.exists() or not embedding_path.exists():
            raise FileNotFoundError(
                "CLIP index files were not found. Run the CLIP pipeline first."
            )

        self.index = pd.read_csv(index_path, dtype=str).fillna("")
        self.embeddings = np.load(embedding_path).astype("float32")
        if len(self.index) != len(self.embeddings):
            raise ValueError("CLIP index and embedding files do not match")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor: Any = CLIPProcessor.from_pretrained(
            self.config.clip_model,
            cache_dir=MODEL_CACHE_DIR,
        )
        self.model: Any = CLIPModel.from_pretrained(
            self.config.clip_model,
            cache_dir=MODEL_CACHE_DIR,
        )
        getattr(self.model, "to")(self.device)
        self.model.eval()

    def search(self, query: str, top_k: int = 10) -> pd.DataFrame:
        query = query.strip()
        if not query:
            raise ValueError("Search query cannot be empty")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        inputs = self.processor(
            text=[query],
            padding=True,
            return_tensors="pt",
        )
        inputs = {name: value.to(self.device) for name, value in inputs.items()}

        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        query_vector = text_features[0].cpu().numpy().astype("float32")
        scores = self.embeddings @ query_vector
        number_to_return = min(top_k, len(scores))
        best_rows = np.argsort(scores)[::-1][:number_to_return]

        results = self.index.iloc[best_rows].copy().reset_index(drop=True)
        results.insert(0, "rank", np.arange(1, number_to_return + 1))
        results.insert(1, "similarity_score", scores[best_rows].round(5))
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the CLIP image index")
    parser.add_argument("query", help="Words describing the image to find")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    engine = ClipSearchEngine()
    results = engine.search(args.query, args.top_k)
    columns = [
        column
        for column in [
            "rank",
            "similarity_score",
            "file_name",
            "image_uid",
            "relative_path",
        ]
        if column in results.columns
    ]
    print(results[columns].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
