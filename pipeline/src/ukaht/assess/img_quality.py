import argparse
import csv
import cv2
from datetime import datetime
from pathlib import Path

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

# finding images
def find_jpg_images(input_list):
    jpg_files = []
    for p in input_list:
        path = Path(p)
        if path.is_dir():
            jpg_files += list(path.glob("*.jpg"))+list(path.glob("*.JPG"))
            jpg_files += list(path.glob("*.jpeg"))+list(path.glob("*.JPEG"))
        elif path.is_file():
            if path.suffix.lower() in (".jpg",".jpeg"):
                jpg_files.append(path)
            else:
                print("Skipping, not a jpg:",path)
        else:
            print("Skipping, path doesn't exist:",path)
    already_seen = set()
    unique_files = []
    for f in jpg_files:
        resolved_path = f.resolve()
        if resolved_path not in already_seen:
            already_seen.add(resolved_path)
            unique_files.append(f)
    return unique_files


def get_labeled_name(img_path):
    return f"{img_path.parent.name}/{img_path.name}"

# duplicate cluster
def load_best_in_group_info(cluster_csv_path):
    best_in_group_lookup = {}
    with open(cluster_csv_path,newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if "image_name" not in reader.fieldnames or "is_representative" not in reader.fieldnames:
            print("Cluster CSV doesn't have the columns expected")
            return {}
        for row in reader:
            image_name = row["image_name"]
            is_representative_text = row["is_representative"].strip().lower()
            best_in_group_lookup[image_name] = is_representative_text in ("true","1","yes")
    return best_in_group_lookup


def main():
    parser = argparse.ArgumentParser(description="Image quality scoring - sharpness and exposure")
    parser.add_argument("-i","--input",required=True,nargs="+")
    parser.add_argument("-o","--output",default="results.csv")
    parser.add_argument("--sharpness-ref",type=float,default=500.0)
    parser.add_argument("--cluster-csv",default=None)
    parser.add_argument("--with-diagnostics",action="store_true")
    args = parser.parse_args()
    img_list = find_jpg_images(args.input)
    print(f"No. of imgs found : {len(img_list)}")
    best_in_group_lookup = {}
    if args.cluster_csv:
        best_in_group_lookup = load_best_in_group_info(args.cluster_csv)
    run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_rows = []
    row_id = 1 
    for img_path in img_list:
        img = cv2.imread(str(img_path))
        if img is None:
            print("Skipping, unable to read:",img_path)
            continue
        grey_img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        sharpness_val = get_sharpness_val(grey_img)
        sharpness_score = get_sharpness_score(sharpness_val)
        dark_pct,bright_pct,avg_brightness,brightness_spread = get_exposure_info(grey_img)
        exposure_score = get_exposure_score(dark_pct,bright_pct,avg_brightness)
        overall_score = round((sharpness_score+exposure_score)/2,4)
        labeled_name = get_labeled_name(img_path)
        is_best_in_group = best_in_group_lookup.get(labeled_name,False)
        row = {"id":row_id,"image_id":row_id,"image_name":labeled_name,"sharpness_score":sharpness_score,"exposure_score":exposure_score,"overall_score":overall_score,"is_best_in_group":is_best_in_group,"scored_at":run_timestamp}
        if args.with_diagnostics:
            row["sharpness_raw_variance"] = round(sharpness_val,2)
            row["dark_clipped_percent"] = round(dark_pct,2)
            row["bright_clipped_percent"] = round(bright_pct,2)
            row["average_brightness"] = round(avg_brightness,2)
            row["brightness_spread"] = round(brightness_spread,2)
        all_rows.append(row)
        print(labeled_name,"sharpness:",sharpness_score,"exposure:",exposure_score,"overall:",overall_score,"best_in_group:",is_best_in_group)
        row_id += 1
    col_names = ["id","image_id","image_name","sharpness_score","exposure_score","overall_score","is_best_in_group","scored_at"]
    if args.with_diagnostics:
        col_names += ["sharpness_raw_variance","dark_clipped_percent","bright_clipped_percent","average_brightness","brightness_spread"]
    with open(args.output,"w",newline="") as csv_file:
        writer = csv.DictWriter(csv_file,fieldnames=col_names)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\nSaved {len(all_rows)} rows to {args.output}")
    if not args.cluster_csv:
        print("Note: is_best_in_group is False for everyone since no --cluster-csv was given")
 
if __name__ == "__main__":
    main()
 