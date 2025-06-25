from fastapi import UploadFile, File, HTTPException
from PIL import Image
from io import BytesIO
import cv2
import numpy as np

def resize_image(image_data: bytes, width: int, height: int) -> bytes:
    image = Image.open(BytesIO(image_data))
    image = image.resize((width, height))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()

def ping():
    print("✅ /ping endpoint was hit")
    return {"message": "pong"}

async def analyze_image(image: UploadFile = File(...)):
    try:
        contents = await image.read()
        image_data = Image.open(BytesIO(contents))
        #faceShape = getFaceShape(contents)
        skintone = getSkinTone(contents)
        print("✅ /analyze_image was hit",image_data.filename)
        #color detection and face detection logic and send data values
        #returns json response
        return {
        "filename":image.filename,
        "skinTone":'warm', 
        "faceShape" : 'oval',
        "colorCode" :skintone
        }
    except Exception as e : 
        print("🔥 Exception occurred:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")

def getSkinTone(image: bytes):
    img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    img_ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)

    lower = np.array([0,133,77],dtype = np.uint8)
    upper = np.array([255, 173, 127],dtype = np.uint8)
     
    mask = cv2.inRange(img_ycrcb, lower, upper)
    #optional cleanup 
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.erode(mask, kernel, iterations=1)

    skin = cv2.bitwise_and(img, img, mask=mask)
    pixels = skin[mask > 0]
    pixels = pixels[np.median(pixels, axis=1) > 80] #mean is skewed by outliers
   

    if len(pixels) == 0:
        return "unknown"

    avg = np.median(pixels, axis=0).astype(int)
    hex_color = '#{:02x}{:02x}{:02x}'.format(avg[2], avg[1], avg[0])
     #Convert to YCrCB for color space
    print("Estimated Skin tone code is ",hex_color)
    return hex_color
