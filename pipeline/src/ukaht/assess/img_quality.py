import cv2

test_img = ['/Users/nithyadharshini/Downloads/1112 new acquisitions/A1a60a.JPG','/Users/nithyadharshini/Downloads/1112 new acquisitions/A1a60b.JPG']

def get_sharpness_val(grey_img):
    laplacian_result = cv2.Laplacian(grey_img,cv2.CV_64F)
    sharpness_val = laplacian_result.var()
    return sharpness_val

for path in test_img:
    img = cv2.imread(path)
    grey_img = cv2.cvtColor(img,cv2.COLOR_BGR2grey)
    val = get_sharpness_val(grey_img)
    print(path,"Sharpness val:",val)
