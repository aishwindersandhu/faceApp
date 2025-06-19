from fastapi import UploadFile, File
from PIL import Image
import io
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
    contents = await image.read()
    image_data = Image.open(io.BytesIO(contents))
    #faceShape = getFaceShape(contents)
    skintone = getSkinTone(contents)
    print("✅ /analyze_image was hit",image_data.filename)
    #color detection and face detection logic and send data values
    #returns json response
    return {"filename":image.filename,"skinTone":'warm', "faceShape" : 'oval',"colorCode" :skintone}

def getSkinTone(image: bytes):
    img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    img_ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    lower = np.array([0,133,77],dtype = np.uint8)
    upper = np.array([255, 173, 127],dtype = np.uint8)
    mask = cv2.inRange(img_ycrcb, lower, upper)
    skin = cv2.bitwise_and(img, img, mask=mask)
    pixels = skin[mask > 0]

    if len(pixels) == 0:
        return "unknown"

    avg = np.mean(pixels, axis=0).astype(int)
    hex_color = '#{:02x}{:02x}{:02x}'.format(avg[2], avg[1], avg[0])
     #Convert to YCrCB for color space
    print("HELLOOOOO",hex_color)
    return hex_color


   
