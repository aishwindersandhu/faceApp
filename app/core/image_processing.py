from fastapi import UploadFile, File, HTTPException
from PIL import Image
from io import BytesIO
import cv2
import numpy as np
from sklearn.cluster import KMeans

# ─────────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────────

def lab_to_hex(L: int, a: int, b: int) -> str:
    """
    Convert OpenCV LAB to hex. Includes gamut-clipping recovery:
    at low L, moderate ab can produce near-achromatic RGB.
    Retries with boosted ab if output is grey.
    """
    lab = np.array([[[
        int(np.clip(L, 0, 255)),
        int(np.clip(a, 0, 255)),
        int(np.clip(b, 0, 255))
    ]]], dtype=np.uint8)
    bgr = cv2.cvtColor(lab, cv2.COLOR_Lab2BGR)[0][0]
    r, g, b_out = int(bgr[2]), int(bgr[1]), int(bgr[0])

    spread = max(abs(r - g), abs(g - b_out), abs(r - b_out))
    if spread < 8 and L < 160:
        lab2 = np.array([[[
            int(np.clip(L,     0, 255)),
            int(np.clip(a + 7, 0, 255)),
            int(np.clip(b + 7, 0, 255))
        ]]], dtype=np.uint8)
        bgr2 = cv2.cvtColor(lab2, cv2.COLOR_Lab2BGR)[0][0]
        r, g, b_out = int(bgr2[2]), int(bgr2[1]), int(bgr2[0])

    return '#{:02x}{:02x}{:02x}'.format(r, g, b_out)


def resize_image(image_data: bytes, width: int, height: int) -> bytes:
    image = Image.open(BytesIO(image_data))
    image = image.resize((width, height))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def ping():
    print("/ping endpoint was hit")
    return {"message": "pong"}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT
# ─────────────────────────────────────────────────────────────────

async def analyze_image(image: UploadFile = File(...)):
    try:
        contents = await image.read()
        skintone, colorPalette, profile = getSkinTone(contents)
        return {
            "filename":     image.filename,
            "skinTone":     profile["depth"],
            "faceShape":    "oval",
            "colorCode":    skintone,
            "colorPalette": colorPalette,
            "profile":      profile
        }
    except Exception as e:
        print("Exception occurred:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ─────────────────────────────────────────────────────────────────
# CORE: SKIN DETECTION
# ─────────────────────────────────────────────────────────────────

def getSkinTone(image: bytes, num_colors: int = 5):
    img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return "unknown", [], _empty_profile()

    h, w = img.shape[:2]

    # ── 1. Center ellipse mask (original size — don't shrink this) ──
    center_mask = np.zeros((h, w), dtype=np.uint8)
    cx, cy = w // 2, h // 2
    cv2.ellipse(center_mask, (cx, cy),
                (int(w * 0.38), int(h * 0.45)),
                0, 0, 360, 255, -1)

    img_ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    y_channel = img_ycrcb[:, :, 0]

    # ── 2. Standard YCrCb mask (fair → medium skin) ──
    mask_std = cv2.inRange(img_ycrcb,
                           np.array([0,   133,  85], dtype=np.uint8),
                           np.array([255, 173, 120], dtype=np.uint8))
    mask_std = cv2.bitwise_and(mask_std, center_mask)

    # ── 3. Skin depth probe — sample Y from MASKED pixels only ──
    # Hair, background, clothing are already excluded by the YCrCb filter.
    # So the Y distribution here reflects actual skin luminance.
    # This is far more reliable than sampling from the raw ellipse region.
    masked_y_vals = y_channel[mask_std > 0]
    if len(masked_y_vals) > 50:
        skin_median_Y = int(np.median(masked_y_vals))
    else:
        skin_median_Y = 200   # too few pixels — assume fair, use standard mask
    print(f"Skin median Y (from masked pixels): {skin_median_Y}")

    # ── 4. Adaptive mask: only add deep-skin range when skin IS dark ──
    if skin_median_Y < 100:
        # Genuine deep skin — standard mask misses dark skin pixels.
        # OR in extended range (lower Y, wider Cr/Cb bounds).
        mask_deep = cv2.inRange(img_ycrcb,
                                np.array([0,   125,  80], dtype=np.uint8),
                                np.array([110, 175, 125], dtype=np.uint8))
        mask_deep = cv2.bitwise_and(mask_deep, center_mask)
        mask = cv2.bitwise_or(mask_std, mask_deep)
        is_deep = True
        print("Deep skin mask activated")
    else:
        mask = mask_std
        is_deep = False
        print("Standard mask used")

    # Original erosion kernel — don't over-erode
    kernel = np.ones((3, 3), np.uint8)
    mask   = cv2.erode(mask, kernel, iterations=1)

    skin   = cv2.bitwise_and(img, img, mask=mask)
    pixels = skin[mask > 0]
    pixels = pixels[np.max(pixels, axis=1) > 15]

    if len(pixels) == 0:
        return "unknown", [], _empty_profile()

    pixels_lab = cv2.cvtColor(
        pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2Lab
    ).reshape(-1, 3).astype(float)

    if len(pixels_lab) < num_colors:
        hex_c = '#{:02x}{:02x}{:02x}'.format(
            int(pixels[0][2]), int(pixels[0][1]), int(pixels[0][0])
        )
        return hex_c, [], _empty_profile()

    # ── 5. KMeans clustering in LAB space ──
    kmeans = KMeans(n_clusters=num_colors, n_init=10, random_state=42)
    kmeans.fit(pixels_lab)
    centers = kmeans.cluster_centers_.astype(int)
    print(f"All KMeans centers : {centers}")

    valid_centers = [c for c in centers if _is_valid_skin_lab(c)]
    best_center   = _get_best_center(valid_centers, centers, is_deep)

    if best_center is None:
        return "unknown", [], _empty_profile()

    print(f"Valid centers: {valid_centers}")
    print(f"Best center chosen: {best_center}")
    L, a, b = int(best_center[0]), int(best_center[1]), int(best_center[2])
    print(f"L={L}, a={a}, b={b}")

    # ── 6. Base hex ──
    best_lab_patch = np.array([[best_center]], dtype=np.uint8)
    best_bgr       = cv2.cvtColor(best_lab_patch, cv2.COLOR_Lab2BGR)[0][0]
    hex_color      = '#{:02x}{:02x}{:02x}'.format(
        int(best_bgr[2]), int(best_bgr[1]), int(best_bgr[0])
    )

    # ── 7. Makeup palette — proportional L shifts by skin depth ──
    depth_factor = float(np.clip(L / 175.0, 0.35, 1.0))
    ab_boost     = max(1.0, 1.8 - depth_factor)

    conceal_L   = int(np.clip(L + max(10, int(20 * depth_factor)), 0, 250))
    contour_L   = int(np.clip(L - max(8,  int(18 * depth_factor)), 20, 255))
    highlight_L = int(np.clip(L + max(12, int(24 * depth_factor)), 0, 250))

    conceal   = lab_to_hex(conceal_L,   a - 2,                 b - 2)
    base      = hex_color
    contour   = lab_to_hex(contour_L,   int(a + 4 * ab_boost), int(b + 5 * ab_boost))
    highlight = lab_to_hex(highlight_L, a - 3,                 int(b + 6 * ab_boost))
    color_palette = [conceal, base, contour, highlight]

    print("Dominant skin tone:", base)
    print("Palette [conceal, base, contour, highlight]:", color_palette)

    # ── 8. Full colour profile ──
    profile = _get_skin_profile(best_center)
    return base, color_palette, profile


def _empty_profile() -> dict:
    return {
        "undertone":   "unknown",
        "contrast":    "unknown",
        "depth":       "unknown",
        "L": 0, "a": 0, "b": 0,
        "warm_palette":  [],
        "cool_palette":  [],
        "dark_palette":  [],
        "jewel_tones":   [],
        "lip_shades":    [],
        "blush_shades":  []
    }


# ─────────────────────────────────────────────────────────────────
# CLASSIFICATION
# ─────────────────────────────────────────────────────────────────

def _is_valid_skin_lab(lab) -> bool:
    """
    Gate clusters before scoring.
    ab_signal minimum scales DOWN at low L — deep skin has
    compressed chromatic channels, not absent ones.
    """
    L, a, b   = int(lab[0]), int(lab[1]), int(lab[2])
    ab_signal = (a - 128) + (b - 128)

    if L < 80:
        min_signal = 3
    elif L < 120:
        min_signal = 5
    else:
        min_signal = 8 + max(0, (L - 140)) * 0.3

    return (
        28  <= L <= 215 and
        120 <= a <= 180 and
        115 <= b <= 190 and
        ab_signal >= min_signal
    )


def _get_best_center(valid_centers: list, centers, is_deep: bool):
    """
    Select the cluster best representing actual skin tone.

    Background rejection:
    - True background (walls, ceilings): ab_signal typically ≤ 8
    - Real skin at any depth: ab_signal typically ≥ 15
    - Rule: reject only if ab_signal is BOTH below scaled threshold
      AND strictly below 15 — this protects fair skin clusters at high L
      which legitimately have moderate ab_signal (15-25).

    Fair skin fast-path:
    - Brightest cluster with ab_signal ≥ threshold → return immediately.

    Deep skin scoring:
    - Minimise L bonus so specular highlights don't outscore actual skin.
    """
    candidates = valid_centers if len(valid_centers) > 0 else list(centers)
    if not candidates:
        return min(centers, key=lambda c: abs(int(c[0]) - 140))

    L_values = [int(c[0]) for c in candidates]
    L_range  = max(L_values) - min(L_values)

    if L_range > 35:
        candidates_sorted = sorted(candidates, key=lambda c: int(c[0]), reverse=True)
        to_remove = []

        for cluster in candidates_sorted[:2]:
            cL        = int(cluster[0])
            ca        = int(cluster[1])
            cb        = int(cluster[2])
            ab_signal = (ca - 128) + (cb - 128)

            # Gentle threshold capped at 20 — never rejects real skin
            bg_threshold = min(10 + max(0, (cL - 150)) * 0.25, 20)

            # BOTH conditions must be true to reject:
            # 1. ab_signal below the (already gentle) threshold
            # 2. ab_signal strictly < 15 (real skin always ≥ 15)
            if ab_signal < bg_threshold and ab_signal < 15:
                to_remove.append(cluster)
                print(f"Rejected bg cluster: L={cL}, ab={ab_signal:.1f}, threshold={bg_threshold:.1f}")
            elif cL > 170 and not is_deep:
                # Fair skin fast-path: bright + genuine ab_signal
                required = 10 + max(0, (cL - 170)) * 0.25
                if ab_signal >= required:
                    print(f"Fair skin fast-path: L={cL}, ab={ab_signal:.1f}")
                    return cluster

        for c in to_remove:
            filtered = [x for x in candidates if not np.array_equal(x, c)]
            if filtered:
                candidates = filtered

    if not candidates:
        candidates = list(centers)

    def skin_score(c):
        L, a, b   = int(c[0]), int(c[1]), int(c[2])
        ab_signal = (a - 128) + (b - 128)
        # Truly achromatic + bright = specular or white wall
        if L > 170 and ab_signal < 10:
            return -999
        l_bonus = L * 0.05 if is_deep else L * 0.12
        return ab_signal + l_bonus

    return max(candidates, key=skin_score)


def _classify_undertone(a: int, b: int, L: int) -> str:
    """
    OpenCV LAB neutral: a=128, b=128
    Warm  → b (yellow) dominates
    Cool  → a (pink/red) dominates

    Fair skin (high L) has compressed ab — tighten cool gap
    so cool fair skin isn't collapsed into neutral.
    """
    a_sig = a - 128
    b_sig = b - 128

    cool_gap = 1 if L > 170 else 2 if L > 140 else 3

    if b_sig > a_sig + 6:
        return "warm"
    elif a_sig > b_sig + cool_gap:
        return "cool"
    else:
        return "neutral"


def _classify_contrast(L: int) -> str:
    if L > 170:
        return "low"
    elif L >= 105:
        return "medium"
    else:
        return "high"


def _classify_depth(L: int) -> str:
    if L > 190:   return "Fair"
    elif L > 168: return "Light"
    elif L > 142: return "Light Medium"
    elif L > 115: return "Medium"
    elif L > 88:  return "Tan"
    elif L > 58:  return "Deep"
    else:         return "Rich Deep"


# ─────────────────────────────────────────────────────────────────
# PROFILE BUILDER
# ─────────────────────────────────────────────────────────────────

def _get_skin_profile(best_center) -> dict:
    L, a, b   = int(best_center[0]), int(best_center[1]), int(best_center[2])
    undertone = _classify_undertone(a, b, L)
    return {
        "undertone":    undertone,
        "contrast":     _classify_contrast(L),
        "depth":        _classify_depth(L),
        "warm_palette": _get_warm_shades(L, undertone),
        "cool_palette": _get_cool_shades(L, undertone),
        "dark_palette": _get_dark_shades(L, undertone),
        "jewel_tones":  _get_jewel_tones(L, undertone),
        "lip_shades":   _get_lip_shades(L, undertone),
        "blush_shades": _get_blush_shades(L, undertone),
        "L": L, "a": a, "b": b
    }


# ─────────────────────────────────────────────────────────────────
# COLOUR SEEDS
# Hues: (name, a, b) in OpenCV LAB. Neutral = a=128, b=128.
# L always derived mathematically from skin L — never hardcoded.
# ─────────────────────────────────────────────────────────────────

_WARM_SEEDS = [
    ("Camel",         133, 163),
    ("Warm Brown",    148, 152),
    ("Rust",          153, 165),
    ("Burnt Orange",  155, 170),
    ("Mustard",       128, 175),
    ("Warm Olive",    120, 160),
]

_COOL_SEEDS = [
    ("Navy",          128,  98),
    ("Slate Blue",    130, 110),
    ("Emerald",       108, 132),
    ("Plum",          150, 112),
    ("Lavender",      138, 115),
    ("Cool Grey",     130, 122),
]

_JEWEL_SEEDS = {
    "warm": [
        ("Ruby",        185, 138),   # deep saturated red — high a, neutral b
        ("Topaz",       128, 185),   # rich golden yellow — high b
        ("Amber",       155, 185),   # vivid amber — red+yellow
        ("Coral",       168, 165),   # true saturated coral
        ("Copper",      158, 175),   # rich copper — warm red+gold
        ("Bronze",      148, 180),   # deep bronze gold
    ],
    "cool": [
        ("Sapphire",    108,  80),   # rich blue — low a, very low b
        ("Amethyst",    165,  95),   # vivid purple — high a, low b
        ("Aquamarine",   88, 118),   # cyan-green — low a, slightly low b
        ("Tanzanite",   138,  82),   # blue-violet
        ("Moonstone",   120, 108),   # blue-grey iridescent
        ("Indigo",      118,  78),   # deep indigo blue
    ],
    "neutral": [
        ("Emerald",      88, 148),   # rich green — low a, slightly high b
        ("Garnet",      178, 132),   # deep red-brown
        ("Turquoise",    90, 122),   # true turquoise — low a
        ("Rose Quartz", 148, 118),   # pink — high a, slightly cool b
        ("Citrine",     128, 188),   # vivid yellow-green
        ("Jade",         95, 145),   # true jade green
    ],
}

_DARK_SEEDS = [
    ("Wine",          162, 128),
    ("Burgundy",      158, 122),
    ("Forest Green",  108, 142),
    ("Midnight Blue", 118,  96),
    ("Deep Plum",     148, 108),
    ("Chocolate",     140, 150),
]

_LIP_SEEDS = {
    "warm": [
        ("Terracotta",  158, 162),
        ("Coral",       152, 158),
        ("Warm Nude",   140, 150),
        ("Peach",       140, 158),
        ("Brick Red",   165, 152),
        ("Warm Mauve",  148, 140),
    ],
    "cool": [
        ("Berry",       158, 118),
        ("Cool Rose",   145, 122),
        ("Pink Nude",   138, 125),
        ("Raspberry",   162, 115),
        ("Cool Mauve",  148, 120),
        ("Plum",        152, 112),
    ],
    "neutral": [
        ("MLBB",        148, 138),
        ("Dusty Rose",  142, 128),
        ("Rosy Nude",   140, 132),
        ("Fig",         152, 125),
        ("Berry Rose",  150, 128),
        ("Soft Coral",  143, 148),
    ],
}

_BLUSH_SEEDS = {
    "warm": [
        ("Peach Blush",  138, 158),
        ("Apricot",      135, 162),
        ("Warm Pink",    142, 148),
        ("Coral Blush",  148, 158),
    ],
    "cool": [
        ("Baby Pink",    138, 122),
        ("Cool Rose",    140, 118),
        ("Lilac Blush",  138, 115),
        ("Soft Berry",   145, 118),
    ],
    "neutral": [
        ("Soft Rose",    138, 132),
        ("Nude Blush",   135, 135),
        ("Rose",         140, 128),
        ("Mauve Blush",  142, 125),
    ],
}

# Pastel blush (above) reads as ashy/washed-out on deep skin, and at low L
# its modest chroma is barely distinguishable from a bronzer/contour shade
# — which is exactly what deep-skin users were being matched to. Deep skin
# is classically recommended much more saturated, higher-a berry/wine/plum
# blush instead, which stays vivid rather than muddy at low lightness.
# Used for "Deep"/"Rich Deep" (skin_L <= 88, see _classify_depth).
_BLUSH_SEEDS_DEEP = {
    "warm": [
        ("Brick",       158, 150),
        ("Terracotta",  162, 155),
        ("Warm Berry",  165, 140),
        ("Deep Coral",  160, 148),
    ],
    "cool": [
        ("Berry",       162, 115),
        ("Wine",        158, 108),
        ("Plum",        155, 105),
        ("Deep Rose",   160, 120),
    ],
    "neutral": [
        ("Deep Rose",   158, 125),
        ("Berry",       160, 118),
        ("Wine",        156, 112),
        ("Rosewood",    150, 130),
    ],
}


# ─────────────────────────────────────────────────────────────────
# L DERIVATION HELPERS
# ─────────────────────────────────────────────────────────────────

def _derive_clothing_L(skin_L: int, index: int, total: int = 6) -> int:
    spread = 65
    if skin_L > 165:
        centre = int(skin_L * 0.70)
    elif skin_L > 110:
        centre = skin_L - 25
    else:
        centre = skin_L + 10
    start = centre - (spread // 2)
    step  = spread / max(total - 1, 1)
    return int(np.clip(start + index * step, 38, 222))


def _derive_jewel_L(skin_L: int, index: int, total: int = 6) -> int:
    # Jewel tones need higher L to be vivid — was 75-135, now 110-165
    jmin, jmax = 110, 165
    centre = int(np.clip(skin_L * 0.78, jmin, jmax))
    spread = 40
    start  = max(jmin, centre - spread // 2)
    end    = min(jmax, start + spread)
    step   = (end - start) / max(total - 1, 1)
    return int(np.clip(start + index * step, jmin, jmax))


def _derive_dark_L(skin_L: int, index: int, total: int = 6) -> int:
    ceiling = min(skin_L - 35, 102)
    floor   = max(ceiling - 52, 32)
    step    = (ceiling - floor) / max(total - 1, 1)
    return int(np.clip(floor + index * step, 32, 108))


def _derive_lip_L(skin_L: int, index: int, total: int = 6) -> int:
    spread = 50
    centre = int(skin_L * 0.75) if skin_L > 165 else max(skin_L - 15, 55)
    start  = centre - spread // 2
    step   = spread / max(total - 1, 1)
    return int(np.clip(start + index * step, 40, 200))


def _derive_blush_L(skin_L: int, index: int, total: int = 4) -> int:
    spread = 30
    centre = int(skin_L * 0.88) if skin_L > 165 else skin_L + 8
    start  = centre - spread // 2
    step   = spread / max(total - 1, 1)
    return int(np.clip(start + index * step, 60, 220))


# ─────────────────────────────────────────────────────────────────
# PALETTE BUILDERS
# ─────────────────────────────────────────────────────────────────

def _get_warm_shades(skin_L: int, undertone: str) -> list:
    db = {"warm": +10, "neutral": +3, "cool": -5}.get(undertone, 0)
    return [
        {"name": name, "hex": lab_to_hex(_derive_clothing_L(skin_L, i), a, b + db)}
        for i, (name, a, b) in enumerate(_WARM_SEEDS)
    ]


def _get_cool_shades(skin_L: int, undertone: str) -> list:
    da = {"cool": +8, "neutral": +2, "warm": -5}.get(undertone, 0)
    return [
        {"name": name, "hex": lab_to_hex(_derive_clothing_L(skin_L, i), a + da, b)}
        for i, (name, a, b) in enumerate(_COOL_SEEDS)
    ]


def _get_dark_shades(skin_L: int, undertone: str) -> list:
    da = {"cool": +5, "neutral": 0, "warm": -3}.get(undertone, 0)
    db = {"warm": +5, "neutral": 0, "cool": -3}.get(undertone, 0)
    return [
        {"name": name, "hex": lab_to_hex(_derive_dark_L(skin_L, i), a + da, b + db)}
        for i, (name, a, b) in enumerate(_DARK_SEEDS)
    ]


def _get_jewel_tones(skin_L: int, undertone: str) -> list:
    seeds = _JEWEL_SEEDS.get(undertone, _JEWEL_SEEDS["neutral"])
    return [
        {"name": name, "hex": lab_to_hex(_derive_jewel_L(skin_L, i), a, b)}
        for i, (name, a, b) in enumerate(seeds)
    ]


def _get_lip_shades(skin_L: int, undertone: str) -> list:
    seeds = _LIP_SEEDS.get(undertone, _LIP_SEEDS["neutral"])
    return [
        {"name": name, "hex": lab_to_hex(_derive_lip_L(skin_L, i), a, b)}
        for i, (name, a, b) in enumerate(seeds)
    ]


def _get_blush_shades(skin_L: int, undertone: str) -> list:
    seed_table = _BLUSH_SEEDS_DEEP if skin_L <= 88 else _BLUSH_SEEDS
    seeds = seed_table.get(undertone, seed_table["neutral"])
    return [
        {"name": name, "hex": lab_to_hex(_derive_blush_L(skin_L, i), a, b)}
        for i, (name, a, b) in enumerate(seeds)
    ]