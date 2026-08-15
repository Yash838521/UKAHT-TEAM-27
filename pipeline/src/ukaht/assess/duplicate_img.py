import argparse
import csv
import cv2
import numpy as np
from pathlib import Path
 
 
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
 
def find_imgs(folder_path):
    folder = Path(folder_path)
    img_files = list(folder.glob("*.jpg"))+list(folder.glob("*.JPG"))
    img_files += list(folder.glob("*.jpeg"))+list(folder.glob("*.JPEG"))
    return img_files
 
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
 
 
def main():
    parser = argparse.ArgumentParser(description="Grouping duplicate imgs together")
    parser.add_argument("-i","--input",required=True)
    parser.add_argument("-o","--output",default="clusters.csv")
    parser.add_argument("--max-dist",type=int, default=10)
    args = parser.parse_args()
    img_list = find_imgs(args.input)
    print(f"Found {len(img_list)} images")
    hashes = []
    for path in img_list:
        img = cv2.imread(str(path))
        grey_img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        hashes.append(compute_phash(grey_img))
    num_of_imgs = len(img_list)
    groups = UnionFind(num_of_imgs)
    for i in range(num_of_imgs):
        for j in range(i+1,num_of_imgs):
            dist = hamming_dist(hashes[i],hashes[j])
            if dist<=args.max_dist:
                groups.merge_groups(i,j)
    group_of_img = [groups.find_group_leader(i) for i in range(num_of_imgs)]
    with open(args.output,"w",newline="") as csv_file:
        col_names = ["image_name","group_number"]
        writer = csv.DictWriter(csv_file,fieldnames=col_names)
        writer.writeheader()
        for i,path in enumerate(img_list):
            writer.writerow({"image_name":path.name,"group_number":group_of_img[i]})
            print(path.name,": group",group_of_img[i])
    print("Saved to",args.output)
 
if __name__ == "__main__":
    main()