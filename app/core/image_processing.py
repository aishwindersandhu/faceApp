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
        skintone,colorPalette,profile = getSkinTone(contents)
        print("/analyze_image was hit",image_data.filename)
        #color detection and face detection logic and send data values
        #returns json response
        return {
        "filename":image.filename,
        "skinTone":profile["depth"], 
        "faceShape" : 'oval',
        "colorCode" :skintone,
        "colorPalette": colorPalette,
        "profile":profile
        }
    except Exception as e : 
        print("Exception occurred:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")

def getSkinTone(image: bytes, num_colors=3):
    img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    img_ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)

    lower = np.array([0, 133, 77], dtype=np.uint8)
    upper = np.array([255, 173, 127], dtype=np.uint8)

    mask = cv2.inRange(img_ycrcb, lower, upper)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.erode(mask, kernel, iterations=1)

    skin = cv2.bitwise_and(img, img, mask=mask)
    pixels = skin[mask > 0]
    pixels = pixels[np.median(pixels, axis=1) > 80]
    pixels_lab = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2Lab).reshape(-1, 3)

    empty_profile = {"undertone": "unknown", "contrast": "unknown", "L": 0, "a": 0, "b": 0}

    if len(pixels) == 0:
        return "unknown", [] , empty_profile
    if len(pixels) < num_colors:
        return ["#%02x%02x%02x" % (p[2], p[1], p[0]) for p in pixels], [] ,empty_profile

    # KMeans to get dominant skin tone
    kmeans = KMeans(n_clusters=num_colors, n_init=10, random_state=42)
    kmeans.fit(pixels_lab)
    centers = kmeans.cluster_centers_.astype(int)

    valid_centers = [c for c in centers if is_valid_skin_lab(c)]
    if valid_centers:
        best_center = max(valid_centers, key=lambda c: c[0])
    else:
        best_center = centers[np.argmax(centers[:, 0])]
    
    profile = get_skin_profile(best_center)
    print("Skin profile:", profile)

    # Convert best Lab back to BGR and hex — this is the BASE shade
    best_lab_patch = np.array([[best_center]], dtype=np.uint8)
    best_bgr = cv2.cvtColor(best_lab_patch, cv2.COLOR_Lab2BGR)[0][0]
    hex_color = '#{:02x}{:02x}{:02x}'.format(best_bgr[2], best_bgr[1], best_bgr[0])

    # Derive the 4 palette shades from best_center in LAB space
    # LAB L channel controls lightness — we shift it up/down
    # Conceal   — lightest  (+20 L)
    # Base      — detected tone (no shift)
    # Contour   — darker   (-18 L)
    # Highlight — warmest, brightest (+25 L, slight b shift)

    def lab_to_hex(lab):
        # Clamp LAB values to valid uint8 range
        lab_clamped = np.array([[np.clip(lab, 0, 255)]], dtype=np.uint8)
        bgr = cv2.cvtColor(lab_clamped, cv2.COLOR_Lab2BGR)[0][0]
        return '#{:02x}{:02x}{:02x}'.format(bgr[2], bgr[1], bgr[0])

    L, a, b = best_center

    conceal   = lab_to_hex([min(L + 20, 255), a,     b    ])  # lighter
    base      = hex_color                                     # detected tone
    contour   = lab_to_hex([max(L - 18, 0),   a + 3, b    ])  # darker, slightly warmer
    highlight = lab_to_hex([min(L + 25, 255), a - 2, b + 5])  # brightest, warm gold

    color_palette = [conceal, base, contour, highlight]

    print("Dominant skin tone:", base)
    print("Palette [conceal, base, contour, highlight]:", color_palette)

    return base, color_palette, profile

def is_valid_skin_lab(lab):
    L, a, b = lab
    # Correct OpenCV uint8 LAB ranges for human skin, 50-80 caters only for very dark skins, mmost skins are 100-200
    return (80 <= L <= 220) and (130 <= a <= 165) and (130 <= b <= 175)

def classify_undertone(a:int,b:int):
    
    #Warm skin has more yellow bias → b dominates
    #Cool skin has more pink/red bias → a dominates
    #Neutral → balanced
    if b > a + 8:
        return "Warm Undertone"
    elif a > b + 5:
        return "Cool Undertone"
    else:
        return "Neutral Undertone"
    
def classify_contrast(L: int) -> str:
    """
    L channel in LAB = lightness (0 dark → 255 light)
    
    We use skin tone lightness as a proxy for contrast level.
    Ideally you'd compare skin L vs hair L — but skin alone
    is a solid first approximation.

    Fair skin reflects more light → lower visual contrast with
    most environments → low contrast profile
    Deep skin → bold contrast with light backgrounds → high contrast
    """
    if L > 160:
        return "low"       # fair / light skin
    elif L >= 100:
        return "medium"
    else:
        return "high"      # deep / rich skin

def classify_depth(L: int) -> str:
    """
    L in OpenCV LAB (0-255 scale)
    Divides into 4 bands: fair, medium, tan, deep
    """
    if L > 180:
        return "Fair"
    elif L > 140:
        return "Medium"
    elif L > 100:
        return "Tan"
    else:
        return "Deep"


def get_skin_profile(best_center: list) -> dict:
    """
    Takes best_center [L, a, b] from your existing getSkinTone()
    and returns a complete profile.
        profile = get_skin_profile(best_center)
    """
    L,a,b = best_center
    undertone = classify_undertone(a,b)
    contrast = classify_contrast(L)
    depth =classify_depth(L)
    #seasons = classify_seasons()
    return{
        "undertone": undertone,
        "contrast": contrast,
        "depth": depth,
        "L": int(L),
        "a": int(a),
        "b": int(b)
    }

