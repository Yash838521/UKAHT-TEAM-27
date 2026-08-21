import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm
from ukaht.config import OUTPUT_DIR, load_config
from ukaht.io_utils import (
    atomic_write_csv,
    load_errors,
    load_inventory,
    save_errors,
    utc_now,
)


OUTPUT_PATH = OUTPUT_DIR / "clip_clusters.csv"
EMBEDDINGS_NPY = OUTPUT_DIR / "clip_embeddings.npy"
INDEX_CSV = OUTPUT_DIR / "clip_index.csv"
CLUSTER_COLUMNS = [
    "image_uid","file_name","relative_path",
    "cluster_id","cluster_type","similarity_score",
    "is_representative","clustered_at"]


def load_embeddings_with_index() -> tuple[np.ndarray, pd.DataFrame]:
    if not EMBEDDINGS_NPY.exists():
        raise FileNotFoundError(f"clip_embeddings.npy not found at {EMBEDDINGS_NPY}")
    if not INDEX_CSV.exists():
        raise FileNotFoundError(f"clip_index.csv not found at {INDEX_CSV}")
    embeddings = np.load(EMBEDDINGS_NPY).astype("float32")
    index = pd.read_csv(INDEX_CSV, dtype=str).fillna("")
    if len(embeddings)!=len(index):
        raise ValueError("clip_embeddings.npy and clip_index.csv row count mismatch")
    return embeddings, index

class UnionFind:
    def __init__(self,n):
        self.parent = list(range(n))
    def find(self,x):
        while self.parent[x]!=x:
            x = self.parent[x]
        return x
    def union(self,a,b):
        ra,rb = self.find(a),self.find(b)
        if ra!=rb:
            self.parent[ra] = rb

def run_clip_clustering(threshold: float=0.92, quality_csv: str=None) -> None:
    errors = load_errors()
    print("Loading CLIP embeddings")
    embeddings, index = load_embeddings_with_index()
    n = len(embeddings)
    print(f"Loaded {n} embeddings")
    # Loading quality scores for picking representative
    quality_map: dict[str, float] = {}
    if quality_csv:
        qpath = Path(quality_csv)
        if qpath.exists():
            df = pd.read_csv(qpath, dtype=str).fillna("")
            for _, row in df.iterrows():
                uid = row.get("image_uid","").strip()
                score = row.get("overall_score","").strip()
                if uid and score:
                    try: quality_map[uid] = float(score)
                    except: pass
    # Computing pairwise cosine similarity - embeddings already normalised
    print("Computing similarity matrix")
    sim_matrix = embeddings @ embeddings.T
    # Cluster using union-find — merging pairs above threshold
    groups = UnionFind(n)
    for i in tqdm(range(n), desc="Clustering"):
        for j in range(i+1, n):
            if sim_matrix[i,j] >= threshold:
                groups.union(i,j)
    leader_to_members: dict[int, list[int]] = {}
    for i in range(n):
        leader = groups.find(i)
        leader_to_members.setdefault(leader,[]).append(i)
    cluster_id = 1
    leader_to_cid = {}
    for leader, members in leader_to_members.items():
        if len(members)>1:
            leader_to_cid[leader] = cluster_id
            cluster_id+=1
    rows = []
    for leader, members in leader_to_members.items():
        cid = leader_to_cid.get(leader)
        if cid is None:
            continue

        def quality(i):
            uid = index.iloc[i]["image_uid"]
            return quality_map.get(uid, 0.0)
        rep_idx = max(members, key=quality)
        for i in members:
            row_data = index.iloc[i]
            sim = float(sim_matrix[i, rep_idx]) if i != rep_idx else 1.0
            rows.append({
                "image_uid": row_data["image_uid"],
                "file_name": row_data["file_name"],
                "relative_path": row_data["relative_path"],
                "cluster_id": cid,
                "cluster_type": "clip_embedding",
                "similarity_score": round(sim * 100, 2),
                "is_representative": i == rep_idx and cid is not None,
                "clustered_at": utc_now(),
            })

    rows.sort(key=lambda r: (r["cluster_id"] or 0, not r["is_representative"], r["file_name"]))
    atomic_write_csv(pd.DataFrame(rows, columns=CLUSTER_COLUMNS), OUTPUT_PATH)
    save_errors(errors)
    clustered = sum(1 for r in rows if r["cluster_id"] is not None)
    num_clusters = cluster_id - 1
    print(f"{n} images → {num_clusters} CLIP clusters ({clustered} images in clusters)")
    print(f"output: {OUTPUT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLIP embedding based duplicate clustering")
    parser.add_argument("--threshold", type=float, default=0.92, help="Cosine similarity threshold (default 0.92)")
    parser.add_argument("--quality-csv", default=None, help="Path to quality_scores.csv for picking representative")
    args = parser.parse_args()
    print(f"loaded embeddings from {EMBEDDINGS_NPY}")
    run_clip_clustering(args.threshold, args.quality_csv)


if __name__ == "__main__":
    main()