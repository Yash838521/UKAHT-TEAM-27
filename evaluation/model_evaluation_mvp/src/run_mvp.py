import argparse
import time

import pandas as pd
import torch
from tqdm import tqdm

from config import (
    CATEGORY_FILE,
    MODEL_NAMES,
    OUTPUT_DIR,
    QUERY_FILE,
    read_list,
)
from image_utils import find_images, open_image


def get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def move_to_device(inputs, device: str):
    return {name: value.to(device) for name, value in inputs.items()}


def run_clip(records, categories, queries, top_k, device):
    from transformers import CLIPModel, CLIPProcessor

    model_name = MODEL_NAMES["clip"]
    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name).to(device)
    model.eval()

    category_prompts = [f"a photograph of {category}" for category in categories]
    text_inputs = move_to_device(
        processor(text=category_prompts, padding=True, return_tensors="pt"),
        device,
    )

    with torch.no_grad():
        category_features = model.get_text_features(**text_inputs)
        category_features = category_features / category_features.norm(dim=-1, keepdim=True)

    image_features = []
    category_rows = []

    for record in tqdm(records, desc="CLIP classification"):
        with open_image(record.path) as image:
            inputs = move_to_device(
                processor(images=image, return_tensors="pt"),
                device,
            )
            with torch.no_grad():
                features = model.get_image_features(**inputs)
                features = features / features.norm(dim=-1, keepdim=True)

        image_features.append(features.cpu())
        logits = model.logit_scale.exp() * features @ category_features.T
        probabilities = logits.softmax(dim=-1).squeeze(0).cpu()
        number_to_keep = min(top_k, len(categories))
        scores, indices = probabilities.topk(number_to_keep)

        for rank, (score, index) in enumerate(zip(scores, indices), start=1):
            category_rows.append(
                {
                    "image_uid": record.image_uid,
                    "file_name": record.file_name,
                    "category": categories[index.item()],
                    "confidence": round(score.item(), 5),
                    "is_primary": rank == 1,
                }
            )

    search_rows = []
    if queries:
        image_matrix = torch.cat(image_features).to(device)
        query_inputs = move_to_device(
            processor(text=queries, padding=True, return_tensors="pt"),
            device,
        )
        with torch.no_grad():
            query_features = model.get_text_features(**query_inputs)
            query_features = query_features / query_features.norm(dim=-1, keepdim=True)
            similarities = query_features @ image_matrix.T

        result_count = min(5, len(records))
        for query_index, query in enumerate(queries):
            scores, indices = similarities[query_index].topk(result_count)
            for rank, (score, index) in enumerate(zip(scores.cpu(), indices.cpu()), start=1):
                record = records[index.item()]
                search_rows.append(
                    {
                        "query": query,
                        "rank": rank,
                        "image_uid": record.image_uid,
                        "file_name": record.file_name,
                        "similarity_score": round(score.item(), 5),
                    }
                )

    return pd.DataFrame(category_rows), pd.DataFrame(search_rows)


def run_blip(records, device):
    from transformers import BlipForConditionalGeneration, BlipProcessor

    model_name = MODEL_NAMES["blip"]
    processor = BlipProcessor.from_pretrained(model_name)
    model = BlipForConditionalGeneration.from_pretrained(model_name).to(device)
    model.eval()

    rows = []
    for record in tqdm(records, desc="BLIP captions"):
        started = time.perf_counter()
        with open_image(record.path) as image:
            inputs = move_to_device(processor(images=image, return_tensors="pt"), device)
            with torch.no_grad():
                generated = model.generate(**inputs, max_new_tokens=60)
            caption = processor.decode(generated[0], skip_special_tokens=True).strip()

        rows.append(
            {
                "image_uid": record.image_uid,
                "file_name": record.file_name,
                "model": "BLIP",
                "caption": caption,
                "confidence": "",
                "runtime_seconds": round(time.perf_counter() - started, 3),
            }
        )
    return pd.DataFrame(rows)


def clean_florence_result(value) -> str:
    if isinstance(value, str):
        return " ".join(value.split())
    return " ".join(str(value).split())


def run_florence(records, device):
    from transformers import AutoModelForCausalLM, AutoProcessor

    model_name = MODEL_NAMES["florence"]
    dtype = torch.float16 if device == "cuda" else torch.float32
    processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=dtype,
        trust_remote_code=True,
    ).to(device)
    model.eval()

    rows = []
    task = "<MORE_DETAILED_CAPTION>"
    for record in tqdm(records, desc="Florence-2 captions"):
        started = time.perf_counter()
        with open_image(record.path) as image:
            inputs = move_to_device(
                processor(text=task, images=image, return_tensors="pt"),
                device,
            )
            if "pixel_values" in inputs:
                inputs["pixel_values"] = inputs["pixel_values"].to(dtype=dtype)

            with torch.no_grad():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=160,
                    num_beams=3,
                    do_sample=False,
                )

            generated_text = processor.batch_decode(
                generated_ids,
                skip_special_tokens=False,
            )[0]
            parsed = processor.post_process_generation(
                generated_text,
                task=task,
                image_size=(image.width, image.height),
            )
            caption = clean_florence_result(parsed.get(task, generated_text))

        rows.append(
            {
                "image_uid": record.image_uid,
                "file_name": record.file_name,
                "model": "Florence-2",
                "caption": caption,
                "confidence": "",
                "runtime_seconds": round(time.perf_counter() - started, 3),
            }
        )
    return pd.DataFrame(rows)


def build_combined_results(records, categories, captions):
    combined = pd.DataFrame(
        {
            "image_uid": [record.image_uid for record in records],
            "file_name": [record.file_name for record in records],
            "relative_path": [record.relative_path for record in records],
        }
    )

    if not categories.empty:
        primary = categories[categories["is_primary"]].copy()
        primary = primary.rename(
            columns={
                "category": "clip_category",
                "confidence": "clip_confidence",
            }
        )
        combined = combined.merge(
            primary[["image_uid", "clip_category", "clip_confidence"]],
            on="image_uid",
            how="left",
        )

    if not captions.empty:
        caption_table = captions.pivot(
            index="image_uid",
            columns="model",
            values="caption",
        ).reset_index()
        caption_table = caption_table.rename(
            columns={"BLIP": "blip_caption", "Florence-2": "florence_caption"}
        )
        combined = combined.merge(caption_table, on="image_uid", how="left")

    return combined


def write_review_template(combined):
    review = combined.copy()
    review["classification_result"] = ""
    review["best_caption_blip_florence"] = ""
    review["notes"] = ""
    review.to_csv(OUTPUT_DIR / "review_template.csv", index=False)


def load_existing_csv(file_name):
    path = OUTPUT_DIR / file_name
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def update_caption_results(new_captions):
    existing = load_existing_csv("captions.csv")
    if new_captions.empty:
        return existing
    if not existing.empty:
        models_run = set(new_captions["model"].unique())
        existing = existing[~existing["model"].isin(models_run)]
    return pd.concat([existing, new_captions], ignore_index=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="MVP version of the image classification")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=["clip", "blip", "florence"],
        default=["clip", "blip", "florence"],
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    records = find_images()
    if not records:
        print("No images found in data\\sample_images.")
        return 1

    categories = read_list(CATEGORY_FILE)
    if "clip" in args.models and not categories:
        print("No categories found in config\\categories.txt.")
        return 1

    queries = read_list(QUERY_FILE)
    device = get_device()
    print(f"Images: {len(records)}")
    print(f"Device: {device}")

    category_results = pd.DataFrame()
    search_results = pd.DataFrame()
    caption_results = []

    if "clip" in args.models:
        category_results, search_results = run_clip(
            records,
            categories,
            queries,
            max(1, args.top_k),
            device,
        )
    if "blip" in args.models:
        caption_results.append(run_blip(records, device))
    if "florence" in args.models:
        caption_results.append(run_florence(records, device))

    captions = (
        pd.concat(caption_results, ignore_index=True)
        if caption_results
        else pd.DataFrame()
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not category_results.empty:
        category_results.to_csv(OUTPUT_DIR / "categories.csv", index=False)
        saved_categories = category_results
    else:
        saved_categories = load_existing_csv("categories.csv")
    if not search_results.empty:
        search_results.to_csv(OUTPUT_DIR / "clip_search_results.csv", index=False)
    saved_captions = update_caption_results(captions)
    if not saved_captions.empty:
        saved_captions.to_csv(OUTPUT_DIR / "captions.csv", index=False)

    combined = build_combined_results(records, saved_categories, saved_captions)
    combined.to_csv(OUTPUT_DIR / "mvp_results.csv", index=False)
    write_review_template(combined)

    print("Execution completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
