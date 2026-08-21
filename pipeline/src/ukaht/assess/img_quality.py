import argparse
import csv
import cv2
from pathlib import Path
import pandas as pd
from tqdm import tqdm
from ukaht.config import OUTPUT_DIR, load_config
from ukaht.io_utils import (ImageRecord,atomic_write_csv,load_errors,load_inventory,record_error,save_errors,utc_now)


OUTPUT_PATH = OUTPUT_DIR / "quality_scores.csv"

QUALITY_COLUMNS = ["image_uid","file_name","relative_path","sharpness_score","exposure_score","overall_score","is_best_in_group","scored_at",]

def get_sharpness_val(grey_img):
    laplacian_result = cv2.Laplacian(grey_img,cv2.CV_64F)
    sharpness_val = laplacian_result.var()
    return sharpness_val

# sharpness
def get_sharpness_score(sharpness_val,ref_max=500):
    score = sharpness_val/ref_max
    if score>1:
        score = 1
    elif score<0:
        score = 0
    return round(score,4)

# exposure
def get_exposure_info(grey_img):
    histogram = cv2.calcHist([grey_img],[0],None,[256],[0,256]).flatten()
    total_pixels = grey_img.size
    dark_clipped_pcnt = (histogram[0:5].sum()/total_pixels)*100
    bright_clipped_pcnt = (histogram[251:256].sum()/total_pixels)*100
    avg_brightness = grey_img.mean()
    brightness_spread = grey_img.std()
    return dark_clipped_pcnt,bright_clipped_pcnt,avg_brightness,brightness_spread

def get_exposure_score(dark_clipped_pcnt,bright_clipped_pcnt,avg_brightness):
    total_clipped = dark_clipped_pcnt+bright_clipped_pcnt
    clipping_score = max(1.0-(total_clipped*0.03),0)
    distance_from_middle = abs(avg_brightness-128)
    brightness_score = max(1.0-(distance_from_middle/128),0)
    exposure_score = (0.6*clipping_score)+(0.4*brightness_score)
    return round(exposure_score,4)

# duplicate cluster
def load_best_in_group_info(cluster_csv_path):
    if not Path(cluster_csv_path).exists():
        raise FileNotFoundError(f"Cluster CSV not found: {cluster_csv_path} - run the clustering step first")
    best_in_group_lookup = {}
    with open(cluster_csv_path, newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing = {"image_uid", "is_representative"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{cluster_csv_path} missing columns: {sorted(missing)}")
        for row in reader:
            is_representative_text = (row.get("is_representative") or "").strip().lower()
            best_in_group_lookup[row["image_uid"]] = is_representative_text in ("true", "1", "yes")
    return best_in_group_lookup

def run_quality(records: list[ImageRecord],sharpness_ref: float=500.0,cluster_csv: str=None) -> None:
    errors = load_errors()
    best_in_group_lookup = {}
    if cluster_csv:
        best_in_group_lookup = load_best_in_group_info(cluster_csv)
        hits = sum(1 for r in records if r.image_uid in best_in_group_lookup)
        print(f"cluster lookup matched {hits}/{len(records)} records")
        if hits == 0:
            raise ValueError("Cluster CSV matched no records - key mismatch")
    rows = []
    processed = failed = 0
    for record in tqdm(records,desc="Quality scoring"):
        try:
            img = cv2.imread(str(record.path))
            if img is None:
                raise ValueError(f"Skipping, unable to read: {record.path}")
            grey_img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            sharpness_val = get_sharpness_val(grey_img)
            sharpness_score = get_sharpness_score(sharpness_val,sharpness_ref)
            dark_pct,bright_pct,avg_brightness,brightness_spread = get_exposure_info(grey_img)
            exposure_score = get_exposure_score(dark_pct,bright_pct,avg_brightness)
            overall_score = round((sharpness_score+exposure_score)/2,4)
            is_best_in_group = best_in_group_lookup.get(record.image_uid, False)
            rows.append({"image_uid":record.image_uid,"file_name":record.file_name,"relative_path":record.relative_path,"sharpness_score":sharpness_score,"exposure_score":exposure_score,"overall_score":overall_score,"is_best_in_group":is_best_in_group,"scored_at":utc_now()})
            processed += 1
        except Exception as error:
            record_error(errors,record,"quality",error)
            rows.append({"image_uid":record.image_uid,"file_name":record.file_name,"relative_path":record.relative_path,"sharpness_score":None,"exposure_score":None,"overall_score":None,"is_best_in_group":best_in_group_lookup.get(record.image_uid,False),"scored_at":utc_now()})
            failed += 1
    atomic_write_csv(pd.DataFrame(rows,columns=QUALITY_COLUMNS),OUTPUT_PATH)
    save_errors(errors)
    print(f"processed={processed} failed={failed}")
    print(f"output: {OUTPUT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Image quality scoring - sharpness and exposure")
    parser.add_argument("--sharpness-ref",type=float,default=500.0)
    parser.add_argument("--cluster-csv", default=str(OUTPUT_DIR/"clip_clusters.csv"))
    args = parser.parse_args()
    config = load_config()
    records = load_inventory(config)
    print(f"No. of imgs found : {len(records)}")
    run_quality(records,args.sharpness_ref,args.cluster_csv)


if __name__ == "__main__":
    main()