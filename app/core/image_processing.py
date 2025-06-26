from fastapi import UploadFile, File, HTTPException
from PIL import Image
from io import BytesIO
import cv2
import numpy as np
from sklearn.cluster import KMeans

def resize_image(image_data: bytes, width: int, height: int) -> bytes:
    image = Image.open(BytesIO(image_data))
    image = image.resize((width, height))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()

def ping():
    print("/ping endpoint was hit")
    return {"message": "pong"}

async def analyze_image(image: UploadFile = File(...)):
    try:
        contents = await image.read()
        image_data = Image.open(BytesIO(contents))
        #faceShape = getFaceShape(contents)
        skintone,colorPalette = getSkinTone(contents)
        print("/analyze_image was hit",image_data.filename)
        #color detection and face detection logic and send data values
        #returns json response
        return {
        "filename":image.filename,
        "skinTone":'warm', 
        "faceShape" : 'oval',
        "colorCode" :skintone,
        "colorPalette": colorPalette
        }
    except Exception as e : 
        print("Exception occurred:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")

def getSkinTone(image: bytes,num_colors=3):
    img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    img_ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)

    lower = np.array([0,133,77],dtype = np.uint8)
    upper = np.array([255, 173, 127],dtype = np.uint8)
     
    mask = cv2.inRange(img_ycrcb, lower, upper) 

    #Removing noise  
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.erode(mask, kernel, iterations=1)

    skin = cv2.bitwise_and(img, img, mask=mask)
    pixels = skin[mask > 0]
    pixels = pixels[np.median(pixels, axis=1) > 80] #mean is skewed by outliers hence using median
    pixels_lab = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2Lab).reshape(-1, 3)
    
    if len(pixels) == 0:
        return "unknown"
    if len(pixels) < num_colors: 
        return ["#%02x%02x%02x" % (p[2], p[1], p[0]) for p in pixels] 
    
    #Apply KMeans to get Dominant Skin tone
    kmeans = KMeans(n_clusters=num_colors, n_init=10, random_state=42)
    kmeans.fit(pixels_lab)
    centers = kmeans.cluster_centers_.astype(int)

    #Filter out dark clusters 
    valid_centers = [c for c in centers if is_valid_skin_lab(c)] 

    if valid_centers:
        #Choose Center closest to mean of valid ones.
        #Prioritize lighter tone among valid (maximize L)
        best_center = max(valid_centers, key=lambda c: c[0])
    else:
        # Fallback to brightest cluster
        best_center = centers[np.argmax(centers[:, 0])]

    # Convert best Lab color back to BGR
    best_lab_patch = np.array([[best_center]], dtype=np.uint8)
    best_bgr = cv2.cvtColor(best_lab_patch, cv2.COLOR_Lab2BGR)[0][0]
    hex_color = '#{:02x}{:02x}{:02x}'.format(best_bgr[2], best_bgr[1], best_bgr[0])
    color_palette = ['#{:02x}{:02x}{:02x}'.format(c[2], c[1], c[0]) for c in centers]
    # Three most dominant Skin tones
     #Convert to YCrCB for color space
    print("Dominant Skin tone",hex_color)
    print("Estimated Skin tone code is ",color_palette)
    return hex_color,color_palette

def is_valid_skin_lab(lab):
    L, a, b = lab
    return 50 <= L <= 80 and 120 <= a <= 150 and 130 <= b <= 160

