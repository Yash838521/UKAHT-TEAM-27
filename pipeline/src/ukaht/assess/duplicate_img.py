import cv2
import numpy as np
 
 
def compute_phash(grey_img):
    small_img = cv2.resize(grey_img,(32,32))
    dct_result = cv2.dct(np.float32(small_img))
    low_freq_block = dct_result[:8,:8]
    median_val = np.median(low_freq_block)
    hash_bits = low_freq_block>median_val
    return hash_bits
 
img = cv2.imread("/Users/nithyadharshini/Downloads/UK Antarctic Heritage Trust Data/SfM/SfM_A_external/DSC_7114.JPG")
grey_img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
hash_bits = compute_phash(grey_img)
print("Hash as a True & False grid:")
print(hash_bits)