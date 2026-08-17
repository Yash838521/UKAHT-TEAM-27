"""
CLIP search script — called as a subprocess by Express routes/search.js
Usage: python clip_search.py --query "person near tent" --model clip-vit-base-patch32
Output: JSON array of { image_id, similarity } sorted by similarity desc
"""

import argparse
import json
import os
import sys

import mysql.connector
import torch
import torch.nn.functional as F
from dotenv import load_dotenv
from transformers import CLIPModel, CLIPProcessor

# Load .env from middleware root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

MINIMUM_FLOOR     = 0.18   # below this nothing is considered relevant
RELATIVE_THRESHOLD = 0.15  # max drop from best score still considered relevant

def get_embeddings_from_db(model_name):
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    cursor = conn.cursor()
    cursor.execute(
        "SELECT image_id, embedding FROM embeddings WHERE model_name = %s AND embedding IS NOT NULL",
        (model_name,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True)
    parser.add_argument('--model', default='clip-vit-base-patch32')
    args = parser.parse_args()

    # Load model
    model_map = {
        'clip-vit-base-patch32':  'openai/clip-vit-base-patch32',
        'clip-vit-large-patch14': 'openai/clip-vit-large-patch14',
        'siglip-base-patch16-224':'google/siglip-base-patch16-224',
    }
    hf_model_name = model_map.get(args.model, 'openai/clip-vit-base-patch32')

    model     = CLIPModel.from_pretrained(hf_model_name)
    processor = CLIPProcessor.from_pretrained(hf_model_name)
    model.eval()

    # Encode text query
    inputs          = processor(text=[args.query], return_tensors='pt', padding=True)
    with torch.no_grad():
        text_embedding  = model.get_text_features(**inputs)
        text_embedding  = F.normalize(text_embedding, dim=-1)

    # Load image embeddings from DB
    rows = get_embeddings_from_db(args.model)
    if not rows:
        print(json.dumps([]))
        return

    image_ids  = [r[0] for r in rows]
    image_embs = torch.tensor([json.loads(r[1]) for r in rows], dtype=torch.float32)
    image_embs = F.normalize(image_embs, dim=-1)

    # Cosine similarity
    similarities = F.cosine_similarity(text_embedding, image_embs).tolist()

    # Apply relative threshold + minimum floor
    best_score = max(similarities)
    threshold  = max(best_score - RELATIVE_THRESHOLD, MINIMUM_FLOOR)

    results = [
        {'image_id': iid, 'similarity': round(sim, 4)}
        for iid, sim in zip(image_ids, similarities)
        if sim >= threshold
    ]

    results.sort(key=lambda x: x['similarity'], reverse=True)
    print(json.dumps(results))

if __name__ == '__main__':
    main()
