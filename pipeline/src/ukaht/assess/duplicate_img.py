import argparse
import csv
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import pandas as pd
from tqdm import tqdm
from ukaht.config import OUTPUT_DIR, load_config
from ukaht.io_utils import (ImageRecord,atomic_write_csv,load_errors,load_inventory,record_error,save_errors,utc_now)


OUTPUT_PATH = OUTPUT_DIR/"clusters.csv"

CLUSTER_COLUMNS = ["image_uid","file_name","relative_path","cluster_id","cluster_type","similarity_score","is_representative","clustered_at"]


def compute_phash(grey_img):
    small_img = cv2.resize(grey_img,(32,32))
    dct_result = cv2.dct(np.float32(small_img))
    low_freq_block = dct_result[:8,:8]
    median_val = np.median(low_freq_block)
    hash_bits = low_freq_block>median_val
    hash_num = 0
    for bit in hash_bits.flatten():
        hash_num = (hash_num<<1)|int(bit)
    return hash_num

def hamming_dist(hash_a,hash_b):
    xor_result = hash_a^hash_b
    return bin(xor_result).count("1")

def get_sharpness_score(grey_img,ref_max=500.0):
    laplacian_result = cv2.Laplacian(grey_img,cv2.CV_64F)
    sharpness_val = laplacian_result.var()
    score = sharpness_val/ref_max
    return max(0.0,min(1.0,score))

def get_exposure_score(grey_img):
    histogram = cv2.calcHist([grey_img],[0],None,[256],[0,256]).flatten()
    total_pixels = grey_img.size
    dark_clipped_pct = (histogram[0:5].sum()/total_pixels)*100
    bright_clipped_pct = (histogram[251:256].sum()/total_pixels)*100
    avg_brightness = grey_img.mean()
    total_clipped = dark_clipped_pct+bright_clipped_pct
    clipping_score = max(1.0-(total_clipped*0.03),0)
    dist_from_middle = abs(avg_brightness-128)
    brightness_score = max(1.0-(dist_from_middle/128),0)
    return (0.6*clipping_score)+(0.4*brightness_score)

def get_quality_score(grey_img,sharpness_ref):
    sharpness = get_sharpness_score(grey_img,sharpness_ref)
    exposure = get_exposure_score(grey_img)
    return (sharpness+exposure)/2

class UnionFind:
    def __init__(self,num_times):
        self.parent = list(range(num_times))
    def find_group_leader(self,item):
        while self.parent[item]!=item:
            item = self.parent[item]
        return item
    def merge_groups(self,item_a,item_b):
        leader_a = self.find_group_leader(item_a)
        leader_b = self.find_group_leader(item_b)
        if leader_a!=leader_b:
            self.parent[leader_a] = leader_b

def run_clustering(records: list[ImageRecord],max_dist: int=5,sharpness_ref: float=500.0) -> None:
    errors = load_errors()
    valid_records = []
    hashes = []
    quality_scores = []
    for record in tqdm(records,desc="Computing hashes"):
        try:
            img = cv2.imread(str(record.path))
            if img is None:
                raise ValueError(f"cv2 could not read {record.path}")
            grey_img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            hashes.append(compute_phash(grey_img))
            quality_scores.append(get_quality_score(grey_img,sharpness_ref))
            valid_records.append(record)
        except Exception as error:
            record_error(errors,record,"clustering",error)
    num_of_imgs = len(valid_records)
    groups = UnionFind(num_of_imgs)
    dist_lookup = {}
    for i in range(num_of_imgs):
        for j in range(i+1,num_of_imgs):
            dist = hamming_dist(hashes[i],hashes[j])
            dist_lookup[(i,j)] = dist
            if dist<=max_dist:
                groups.merge_groups(i,j)
    imgs_in_group = {}
    for i in range(num_of_imgs):
        leader = groups.find_group_leader(i)
        imgs_in_group.setdefault(leader,[]).append(i)

    cluster_id_for_leader = {}
    next_cluster_id = 1
    for leader,member_indexes in imgs_in_group.items():
        if len(member_indexes) > 1: 
            cluster_id_for_leader[leader] = next_cluster_id
            next_cluster_id += 1
    all_rows = []
    for leader,member_indexes in imgs_in_group.items():
        if len(member_indexes) == 1:
            continue
        cluster_id = cluster_id_for_leader[leader]
        representative_index = max(member_indexes,key=lambda i: quality_scores[i])
        for i in member_indexes:
            if i==representative_index:
                similarity = 100.0
            else:
                smaller,bigger = ((i,representative_index) if i<representative_index else (representative_index,i))
                dist = dist_lookup[(smaller,bigger)]
                similarity = round((1-(dist/64))*100,2)
            record = valid_records[i]
            all_rows.append({"image_uid":record.image_uid,"file_name":record.file_name,"relative_path":record.relative_path,"cluster_id":cluster_id,"cluster_type":"phashing","similarity_score":similarity,"is_representative":i==representative_index,"clustered_at":utc_now()})
    all_rows.sort(key=lambda r: (r["cluster_id"],not r["is_representative"],r["file_name"]))
    atomic_write_csv(pd.DataFrame(all_rows,columns=CLUSTER_COLUMNS),OUTPUT_PATH)
    save_errors(errors)
    num_with_duplicates = sum(1 for members in imgs_in_group.values() if len(members)>1)
    print(f"{num_of_imgs} images : {num_with_duplicates} duplicate groups")
    print(f"output: {OUTPUT_PATH}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Grouping duplicate imgs together")
    parser.add_argument("--max-dist",type=int,default=5)
    parser.add_argument("--sharpness-ref",type=float,default=500.0)
    args = parser.parse_args()
    config = load_config()
    records = load_inventory(config)
    print(f"loaded {len(records)} images from inventory")
    run_clustering(records,args.max_dist,args.sharpness_ref)

if __name__ == "__main__":
    main()