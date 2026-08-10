import argparse
import csv
import cv2
from pathlib import Path

def get_sharpness_val(grey_img):
    laplacian_result = cv2.Laplacian(grey_img,cv2.CV_64F)
    sharpness_val = laplacian_result.var()
    return sharpness_val

def get_sharpness_score(sharpness_val,ref_max=500):
    score = sharpness_val/ref_max
    if score>1:
        score = 1
    elif score<0:
        score = 0
    return round(score,4)

def get_exposure_info(grey_img):
    histogram = cv2.calcHist([grey_img],[0],None,[256],[0,256]).flatten()
    total_pixels = grey_img.size
    dark_clipped_pcnt = (histogram[0:5].sum()/total_pixels)*100
    bright_clipped_pcnt = (histogram[251:256].sum()/total_pixels)*100
    avg_brightness = grey_img.mean()
    return dark_clipped_pcnt,bright_clipped_pcnt,avg_brightness

def get_exposure_score(dark_clipped_pcnt,bright_clipped_pcnt,avg_brightness):
    total_clipped = dark_clipped_pcnt+bright_clipped_pcnt
    clipping_score = max(1.0-(total_clipped*0.03),0)
    distance_from_middle = abs(avg_brightness-128)
    brightness_score = max(1.0-(distance_from_middle/128),0)
    exposure_score = (0.6*clipping_score)+(0.4*brightness_score)
    return round(exposure_score,4)

def find_jpg_images(folder_path):
    folder = Path(folder_path)
    jpg_files = list(folder.glob("*.jpg"))+list(folder.glob("*.JPG"))
    jpg_files += list(folder.glob("*.jpeg"))+list(folder.glob("*.JPEG"))
    return jpg_files

def main():
    parser = argparse.ArgumentParser(description="Image quality scoring - sharpness and exposure")
    parser.add_argument("-i","--input",required=True)
    parser.add_argument("-o","--output",default="results.csv")
    args = parser.parse_args()
    img_list = find_jpg_images(args.input)
    print(f"No. of imgs found : {len(img_list)}")
    all_results = []
    for img_path in img_list:
        img = cv2.imread(str(img_path))
        if img is None:
            print("Skipping, unable to read:",img_path)
            continue
        grey_img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        sharpness_val = get_sharpness_val(grey_img)
        sharpness_score = get_sharpness_score(sharpness_val)
        dark_pct,bright_pct,avg_brightness = get_exposure_info(grey_img)
        exposure_score = get_exposure_score(dark_pct, bright_pct,avg_brightness)
        overall_score = round((sharpness_score+exposure_score)/2,4)
        print(img_path.name,"sharpness:",sharpness_score,"exposure:",exposure_score)
        all_results.append({"img_name":img_path.name,"sharpness_score":sharpness_score,"exposure_score":exposure_score,"overall_score":overall_score})
    with open(args.output,"w",newline="") as csv_file:
        col_names = ["img_name","sharpness_score","exposure_score","overall_score"]
        writer = csv.DictWriter(csv_file,fieldnames=col_names)
        writer.writeheader()
        writer.writerows(all_results)
    print("Saved results to",args.output)

if __name__ == "__main__":
    main()