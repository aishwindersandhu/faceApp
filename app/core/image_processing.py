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
    # how much room do we have before hitting ceiling
    l_headroom = 255 - L
    # scale conceal shift — use at most 40% of available headroom
    conceal_shift = min(18, int(l_headroom * 0.4))
    highlight_shift = min(22, int(l_headroom * 0.5))

    conceal   = lab_to_hex([L + conceal_shift,  a,     b    ])  # lighter, less saturated
    base      = hex_color
    contour   = lab_to_hex([max(L - 20, 0),     a + 3, b + 2])  # darker, slightly warmer
    highlight = lab_to_hex([L + highlight_shift, a - 2, b + 4])  # bright, golden warmth

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
    if L > 185:
        return "Fair"
    elif L > 145:
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
    warm_palette = get_warm_shades(L,undertone)
    cool_palette = get_cool_shades(L,undertone)
    dark_palette = get_dark_shades(L)
    jewel_tones = get_jewel_tones(L,undertone)

    print(warm_palette,"warm_palette")
    #seasons = classify_seasons()
    return{
        "undertone": undertone,
        "contrast": contrast,
        "depth": depth,
        "warm_palette":warm_palette,
        "cool_palette": cool_palette,
        "dark_palette":dark_palette,
        "jewel_tones": jewel_tones,
        "L": int(L),
        "a": int(a),
        "b": int(b)
    }

WARM_SEEDS = [
   ("Warm brown",   155, 148),      
    ("Rust",         155, 168),   # index 1 → L=116
    ("Warm olive",   118, 162),   # index 2 → L=132
    ("Burnt orange", 158, 168),   # index 3 → L=148
    ("Mustard",      130, 178),   # index 4 → L=164
    ("Camel",        135, 165),   # index 5 → L=180 — camel works light
   
]

COOL_SEEDS = [
    ("Navy",         128, 100),
    ("Emerald",      108, 130),
    ("Plum",         148, 112),
    ("Slate",        128, 118),
    ("Lavender",     138, 112),
    ("Cool grey",    128, 122),
]
JEWEL_SEEDS = {
    "warm": [
        ("Ruby",          165, 148),   # deep red-warm
        ("Topaz",         128, 172),   # warm golden yellow
        ("Amber",         138, 168),   # rich orange-gold
        ("Coral jade",    148, 158),   # warm green-coral
        ("Copper",        145, 162),   # warm metallic
        ("Bronze",        135, 160),   # earthy rich tone
    ],
    "cool": [
        ("Sapphire",      118,  98),   # deep blue
        ("Amethyst",      148, 108),   # purple-violet
        ("Aquamarine",    102, 122),   # cool blue-green
        ("Tanzanite",     130, 100),   # blue-purple
        ("Moonstone",     118, 115),   # cool neutral pearl
        ("Indigo",        125,  95),   # deep cool blue
    ],
    "neutral": [
        ("Emerald",       108, 138),   # balanced green
        ("Garnet",        155, 135),   # balanced red
        ("Turquoise",     102, 125),   # balanced blue-green
        ("Rose quartz",   132, 122),   # balanced pink
        ("Citrine",       125, 165),   # balanced yellow
        ("Jade",          108, 140),   # balanced cool green
    ]
}
# ─────────────────────────────────────────
# Dark wearable seeds — universal hue families
# Everyone gets same hues, L personalized to skin
# ─────────────────────────────────────────
DARK_SEEDS = [
    ("Wine",          162, 128),
    ("Burgundy",      158, 122),
    ("Forest green",  108, 142),
    ("Midnight blue", 118,  95),
    ("Deep plum",     148, 108),
    ("Chocolate",     140, 150),
]

def derive_jewel_L(skin_L: int, index: int, total: int = 6) -> int:
    """
    Jewel tones live in L range 80–130 regardless of skin depth.
    We distribute the 6 shades across this range,
    but bias the center toward the skin's L clamped into that range.
    
    Fair skin (L=200) → center pulls toward 130 end
    Deep skin (L=100) → center pulls toward 80 end
    Medium skin (L=175) → center around 110
    """
    jewel_min = 80
    jewel_max = 130
    # Clamp skin L into jewel range to get center
    center = int(np.clip(skin_L * 0.6, jewel_min, jewel_max))
    spread = 40
    start  = max(jewel_min, center - spread // 2)
    end    = min(jewel_max, start + spread)
    step   = (end - start) / (total - 1)
    L      = start + (index * step)
    return int(np.clip(L, jewel_min, jewel_max))


def derive_dark_L(skin_L: int, index: int, total: int = 6) -> int:
    """
    Dark wearables always sit below skin tone.
    Cap at L=100 so deep skin tones don't lose color into black.
    Spread across a narrow deep range so all 6 are visibly distinct.

    Fair skin (L=200)   → range ~60–100  (rich deep colors)
    Medium skin (L=175) → range ~55–95
    Deep skin (L=110)   → range ~40–80   (still colored, not black)
    """
    dark_ceiling = min(skin_L - 40, 100)   # always below skin, never muddy
    dark_floor   = max(dark_ceiling - 50, 35)
    step         = (dark_ceiling - dark_floor) / (total - 1)
    L            = dark_floor + (index * step)
    return int(np.clip(L, 35, 105))


def get_jewel_tones(skin_L: int, undertone: str) -> list:
    seeds = JEWEL_SEEDS.get(undertone, JEWEL_SEEDS["neutral"])
    result = []
    for i, (name, a, b) in enumerate(seeds):
        L = derive_jewel_L(skin_L, i)
        result.append({
            "name": name,
            "hex":  lab_to_hex(L, a, b)
        })
    return result


def get_dark_shades(skin_L: int) -> list:
    """
    Universal — same hue families for everyone.
    L derived from skin so deep skin gets visibly colored darks
    and fair skin gets properly deep rich darks.
    """
    result = []
    for i, (name, a, b) in enumerate(DARK_SEEDS):
        L = derive_dark_L(skin_L, i)
        result.append({
            "name": name,
            "hex":  lab_to_hex(L, a, b)
        })
    return result
def derive_clothing_L(skin_L: int, shade_index: int, total: int = 6) -> int:
    """
    Distributes shades across a lightness range centered on skin tone.
    
    skin_L = 175 (medium fair) →  range spans ~100 to 210
    skin_L = 120 (deep)        →  range spans ~60  to 160
    skin_L = 200 (fair)        →  range spans ~140 to 230
    
    This means deep skin gets deeper versions of rust/navy etc
    and fair skin gets lighter versions — same hue, different depth.
    """
    spread = 60
    
    # for fair skin, don't centre on skin L
    # anchor the range lower so colours stay visible and distinct from skin
    if skin_L > 160:
        centre = int(skin_L * 0.72)   # fixed anchor for fair skin
    else:
        centre = skin_L - 20   # for medium/deep, stay below skin

    start = centre - (spread // 2)
    step  = spread // (total - 1)
    L     = start + (shade_index * step)
    return int(np.clip(L, 40, 220))   # safety clamp


def get_warm_shades(skin_L: int, undertone: str) -> list:
    """
    Hue family fixed (warm seeds), exact lightness derived from skin L.
    Undertone shifts the b channel slightly to stay harmonious.
    """
    undertone_b_adjust = {"warm": +8, "neutral": 0, "cool": -8}
    db = undertone_b_adjust.get(undertone, 0)

    result = []
    for i, (name, a, b) in enumerate(WARM_SEEDS):
        L   = derive_clothing_L(skin_L, i)
        print(f"{i} {name}: derived L={L}, a={a}, b={b} → {lab_to_hex(L, a, b)}")
        result.append({
            "name": name,
            "hex":  lab_to_hex(L, a, b + db)
        })
    return result


def get_cool_shades(skin_L: int, undertone: str) -> list:
    """
    Hue family fixed (cool seeds), exact lightness derived from skin L.
    Undertone shifts the a channel slightly to stay harmonious.
    """
    undertone_a_adjust = {"cool": +8, "neutral": 0, "warm": -8}
    da = undertone_a_adjust.get(undertone, 0)

    result = []
    for i, (name, a, b) in enumerate(COOL_SEEDS):
        L   = derive_clothing_L(skin_L, i)
        result.append({
            "name": name,
            "hex":  lab_to_hex(L, a + da, b)
        })
    return result

def lab_to_hex(L: int, a: int, b: int) -> str:
    lab = np.array([[[
        int(np.clip(L, 0, 255)),
        int(np.clip(a, 0, 255)),
        int(np.clip(b, 0, 255))
    ]]], dtype=np.uint8)
    bgr = cv2.cvtColor(lab, cv2.COLOR_Lab2BGR)[0][0]
    return '#{:02x}{:02x}{:02x}'.format(int(bgr[2]), int(bgr[1]), int(bgr[0]))


