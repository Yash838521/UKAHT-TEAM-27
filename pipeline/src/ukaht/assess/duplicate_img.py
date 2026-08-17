import argparse
import csv
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
 
 
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

def find_imgs(input_list):
    files_found = []
    for i in input_list:
        path = Path(i)
        if path.is_dir():
            files_found += list(path.glob("*.jpg"))
            files_found += list(path.glob("*.JPG"))
            files_found += list(path.glob("*.jpeg"))
            files_found += list(path.glob("*.JPEG"))
        elif path.is_file():
            if path.suffix.lower() in (".jpg",".jpeg"):
                files_found.append(path)
            else:
                print("Skipping (not a jpg):", path)
        else:
            print("Skipping (path doesn't exist):", path)
    seen_already = set()
    unique_files = []
    for f in files_found:
        resolved_path = f.resolve()
        if resolved_path not in seen_already:
            seen_already.add(resolved_path)
            unique_files.append(f)
    return unique_files

def get_labeled_name(img_path):
    return f"{img_path.parent.name}/{img_path.name}"

 
def main():
    parser = argparse.ArgumentParser(description="Grouping duplicate imgs together")
    parser.add_argument("-i","--input",required=True,nargs="+")
    parser.add_argument("-o","--output",default="clusters.csv")
    parser.add_argument("--max-dist",type=int,default=10)
    parser.add_argument("--sharpness-ref",type=float,default=500.0)
    args = parser.parse_args()
    img_list = find_imgs(args.input)
    if len(img_list) == 0:
        print("No jpg images found, so stopping")
        return
    print(f"Found {len(img_list)} images")
    hashes = []
    quality_scores = []
    for path in img_list:
        img = cv2.imread(str(path))
        if img is None:
            print("Couldn't read, skipping:",path)
            continue
        grey_img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        hashes.append(compute_phash(grey_img))
        quality_scores.append(get_quality_score(grey_img,args.sharpness_ref))
    num_of_imgs = len(img_list)
    groups = UnionFind(num_of_imgs)
    dist_lookup = {}
    for i in range(num_of_imgs):
        for j in range(i+1,num_of_imgs):
            dist = hamming_dist(hashes[i],hashes[j])
            dist_lookup[(i,j)] = dist
            if dist<=args.max_dist:
                groups.merge_groups(i,j)
    imgs_in_group = {}
    for i in range(num_of_imgs):
        leader = groups.find_group_leader(i)
        imgs_in_group.setdefault(leader,[]).append(i)
    cluster_id_for_leader = {}
    next_cluster_id = 1
    for i in range(num_of_imgs):
        leader = groups.find_group_leader(i)
        if leader not in cluster_id_for_leader:
            cluster_id_for_leader[leader] = next_cluster_id
            next_cluster_id += 1
    run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_rows = []
    for leader,member_indexes in imgs_in_group.items():
        cluster_id = cluster_id_for_leader[leader]
        representative_index = max(member_indexes,key=lambda i: quality_scores[i])
        for i in member_indexes:
            if i == representative_index:
                similarity = 100.0
            else:
                smaller,bigger = ((i,representative_index) if i<representative_index else (representative_index,i))
                dist = dist_lookup[(smaller,bigger)]
                similarity = round((1-(dist/64))*100,2)
            row = {"image_name": get_labeled_name(img_list[i]),"cluster_id": cluster_id,"cluster_type": "phashing","similarity_score": similarity,"is_representative": i == representative_index,"clustered_at": run_timestamp}
            all_rows.append(row)
            print(get_labeled_name(img_list[i]), ": cluster", cluster_id," similarity:", similarity," representative:", i == representative_index)
    all_rows.sort(key=lambda r: (r["cluster_id"],not r["is_representative"],r["image_name"]))
    col_names = ["image_name","cluster_id","cluster_type","similarity_score","is_representative","clustered_at"]
    with open(args.output, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file,fieldnames=col_names)
        writer.writeheader()
        writer.writerows(all_rows)
    num_of_groups = len(imgs_in_group)
    num_with_duplicates = sum(1 for members in imgs_in_group.values() if len(members)>1)
    print(f"\n{num_of_imgs} images : {num_of_groups} groups "f"({num_with_duplicates} contain duplicates)")
    print("Saved to",args.output)
 
if __name__ == "__main__":
    main()