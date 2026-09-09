"""
Build the "foundation" catalogue category from three public data sources:

  - The Pudding's "Shades of You" dataset: real foundation shades as hex
    codes, grouped by brand/product line. This is the base — every shade
    in the catalogue comes from here.
    https://github.com/the-pudding/data/blob/master/makeup-shades/shades.csv

  - makeup-api.herokuapp.com: product name / image / price. Tried first
    for enrichment, since it's the only source with real pricing. Its
    foundation catalogue only covers ~28 mostly North American drugstore
    brands, so most Pudding products won't find a match here.

  - The Pudding's second dataset, foundation-names/allShades.csv (~6800
    Sephora + Ulta shades, 107 brands): tried as a fallback when
    makeup-api has no match. Covers several prestige brands makeup-api
    doesn't (NARS, MAC, Estée Lauder, Lancôme, Bobbi Brown, Make Up For
    Ever, Shiseido, bareMinerals...). It has no price field, and its
    images are shade swatch chips, not full product photography — still
    better than a generic placeholder, but flagged here since it's a
    different kind of image than the makeup-api product shots.
    https://github.com/the-pudding/data/tree/master/foundation-names

  - A Nykaa.com product scrape (Kaggle: jithinanievarghese/nykaa-popular-
    brands-cosmetics-beauty-products), tried last for Indian brands that
    neither of the above (both US/UK-centric) carry — Lakmé, Nykaa,
    Colorbar, Blue Heaven, Lotus Herbals, House of Tara, Bharat & Doris.
    Kaggle requires an account to download, so unlike the other two
    sources this file isn't fetched over the network: it must be placed
    manually at scripts/data/raw/nyka_popular_brands_products_2022_10_16.csv
    (--refresh does not touch it). If missing, this source is just skipped.
    It has no per-shade palette, so matched products still show hex codes
    as shade names — but get a real product name/photo/price instead of
    being hidden as unverified.

  Products that no source matches fall back to a placeholder image,
  a "₹—" price, and the hex code as the shade name.

Run:
    python scripts/build_catalogue.py [--refresh]

Writes app/recommendations/data/foundation.json, which catalogue.py loads
at import time and drops into the CATALOGUE list in place of the
hardcoded foundation category.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import html
import json
import re
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

SHADES_CSV_URL = "https://raw.githubusercontent.com/the-pudding/data/master/makeup-shades/shades.csv"
MAKEUP_API_URL = "http://makeup-api.herokuapp.com/api/v1/products.json?product_type=foundation"
ALLSHADES_CSV_URL = "https://raw.githubusercontent.com/the-pudding/data/master/foundation-names/allShades.csv"

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "scripts" / "data" / "raw"
OUT_PATH = ROOT / "app" / "recommendations" / "data" / "foundation.json"

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Manually downloaded from Kaggle (see module docstring) — no fetch URL, since
# Kaggle needs an account. Kept local-only; --refresh does not affect it.
NYKAA_CSV_PATH = RAW_DIR / "nyka_popular_brands_products_2022_10_16.csv"

MATCH_THRESHOLD = 0.66          # min fraction of product-name tokens found in the candidate
COLOR_MATCH_MAX_DISTANCE = 40   # max RGB distance to borrow a shade name from an enrichment source


def _fetch(url: str, cache_path: Path, refresh: bool) -> bytes:
    if cache_path.exists() and not refresh:
        return cache_path.read_bytes()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = resp.read()
    cache_path.write_bytes(data)
    return data


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    h = hex_code.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_distance(a: str, b: str) -> float:
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    return ((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2) ** 0.5


def load_pudding_shades(refresh: bool) -> dict[tuple[str, str], list[str]]:
    raw = _fetch(SHADES_CSV_URL, RAW_DIR / "shades.csv", refresh)
    reader = csv.DictReader(raw.decode("utf-8").splitlines())
    products: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in reader:
        key = (row["brand"].strip(), row["product"].strip())
        products[key].append("#" + row["hex"].strip().lstrip("#").upper())
    return products


def _resolve_allshades_image(img_src: str, product_url: str) -> str:
    if img_src.startswith("http"):
        return img_src
    if img_src.startswith("//"):
        return "https:" + img_src
    if "sephora.com" in product_url:
        return "https://www.sephora.com" + img_src
    if "ulta.com" in product_url:
        return "https://www.ulta.com" + img_src
    return img_src


def _allshades_label(row: dict) -> str:
    name = (row.get("name") or "").strip()
    if name and name.upper() != "NA":
        return name
    desc = re.sub(r"\s+selected$", "", (row.get("description") or "").strip(), flags=re.I).strip()
    if desc:
        return desc
    return (row.get("specific") or "").strip() or row["hex"]


# Every enrichment candidate — whether from makeup-api or allShades.csv — is
# normalized to this same shape, so matching/shade-naming code doesn't care
# which source it came from.
#   {"brand": str, "name": str, "image": str, "price_prefix": str,
#    "palette": [{"hex": str, "name": str}, ...]}

def load_makeup_api_candidates(refresh: bool) -> list[dict]:
    raw = _fetch(MAKEUP_API_URL, RAW_DIR / "makeup_api_foundation.json", refresh)
    api_products = json.loads(raw.decode("utf-8"))
    return [
        {
            "brand": p["brand"] or "",
            "name": p["name"] or "",
            "image": p["image_link"],
            "price_prefix": format_price(p),
            "palette": [
                {"hex": c["hex_value"], "name": c["colour_name"].strip()}
                for c in (p.get("product_colors") or [])
            ],
        }
        for p in api_products
    ]


def load_allshades_candidates(refresh: bool) -> list[dict]:
    raw = _fetch(ALLSHADES_CSV_URL, RAW_DIR / "allShades.csv", refresh)
    reader = csv.DictReader(raw.decode("utf-8").splitlines())

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in reader:
        key = (row["brand"].strip(), row["product"].strip())
        groups[key].append(row)

    candidates = []
    for (brand, product), rows in groups.items():
        candidates.append({
            "brand": brand,
            "name": product,
            "image": _resolve_allshades_image(rows[0]["imgSrc"], rows[0]["url"]),
            "price_prefix": "₹—",
            "palette": [
                {"hex": "#" + row["hex"].strip().lstrip("#").upper(), "name": _allshades_label(row)}
                for row in rows
                if row.get("hex")
            ],
        })
    return candidates


def load_nykaa_candidates() -> list[dict]:
    if not NYKAA_CSV_PATH.exists():
        return []
    with open(NYKAA_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        candidates = []
        for row in reader:
            price = row.get("price") or row.get("mrp")
            try:
                price_prefix = f"₹{round(float(price)):,}" if price else "₹—"
            except ValueError:
                price_prefix = "₹—"
            candidates.append({
                "brand": (row.get("brand_name") or "").strip(),
                "name": (row.get("product_title") or "").strip(),
                "image": row.get("image_url") or "",
                "price_prefix": price_prefix,
                "palette": [],  # no per-shade colour data in this source
            })
    return candidates


def _tokens(text: str) -> list[str]:
    return [t for t in _normalize(text).split() if len(t) > 1]


def _fuzzy_token_present(token: str, candidate_tokens: list[str]) -> bool:
    return any(difflib.SequenceMatcher(None, token, ct).ratio() >= 0.75 for ct in candidate_tokens)


def _token_overlap(product_tokens: list[str], candidate_tokens: list[str]) -> float:
    if not product_tokens:
        return 0.0
    matched = sum(1 for t in product_tokens if _fuzzy_token_present(t, candidate_tokens))
    return matched / len(product_tokens)


def find_best_match(brand: str, product: str, candidates_pool: list[dict]) -> dict | None:
    norm_brand = _normalize(brand)
    candidates = []
    for c in candidates_pool:
        cand_brand = _normalize(c["brand"])
        if cand_brand and (cand_brand in norm_brand or norm_brand in cand_brand):
            candidates.append(c)
    if not candidates:
        return None

    # Match on the product-line name only (brand is already filtered on above) —
    # token overlap handles "PRO FILT'R" matching "PRO FILT'R - Soft Matte Longwear
    # Foundation" far better than whole-string similarity, which favours whichever
    # candidate happens to share the most characters overall.
    product_tokens = _tokens(product)
    best, best_score = None, (0.0, 0.0)
    for candidate in candidates:
        overlap = _token_overlap(product_tokens, _tokens(candidate["name"]))
        ratio = difflib.SequenceMatcher(None, _normalize(product), _normalize(candidate["name"])).ratio()
        score = (overlap, ratio)
        if score > best_score:
            best, best_score = candidate, score
    return best if best_score[0] >= MATCH_THRESHOLD else None


# Generic descriptive shade names — used as a last resort when a matched
# product has no per-shade names of its own (the Nykaa source has no colour
# data at all, so its "palette" is always empty). Nearest by RGB distance
# beats showing a bare hex code. These are plausible cosmetic-style
# descriptors spanning fair-to-deep / warm-to-cool, not real per-brand shade
# names, so treat them as a display fallback rather than product data.
_GENERIC_SHADE_REFERENCE: list[tuple[str, str]] = [
    ("Porcelain",     "#F5E1D3"),
    ("Ivory",         "#F0DCC4"),
    ("Cool Ivory",    "#EDDBCE"),
    ("Warm Ivory",    "#EEDAB8"),
    ("Sand",          "#E6C9A8"),
    ("Buff",          "#E2C09B"),
    ("Rose Beige",    "#DEBCA8"),
    ("Golden Beige",  "#D9AE81"),
    ("Warm Beige",    "#DFB68D"),
    ("Honey",         "#CD9D77"),
    ("Warm Sand",     "#D2A67E"),
    ("Neutral Beige", "#CBA07E"),
    ("Cool Beige",    "#C8A48D"),
    ("Almond",        "#C2895D"),
    ("Golden Tan",    "#BC8B63"),
    ("Warm Tan",      "#B98259"),
    ("Caramel",       "#B87A4C"),
    ("Amber",         "#A9724E"),
    ("Chestnut",      "#9C6640"),
    ("Cocoa",         "#8F5A38"),
    ("Deep Bronze",   "#6B4530"),
    ("Espresso",      "#5A3925"),
    ("Mahogany",      "#4A2F1F"),
    ("Ebony",         "#3A2418"),
]


def _generic_shade_name(hex_code: str) -> str:
    return min(_GENERIC_SHADE_REFERENCE, key=lambda ref: _rgb_distance(hex_code, ref[1]))[0]


def shade_name_for(hex_code: str, match: dict | None) -> str:
    if match:
        best_name, best_dist = None, COLOR_MATCH_MAX_DISTANCE
        for c in match["palette"]:
            dist = _rgb_distance(hex_code, c["hex"])
            if dist < best_dist:
                best_name, best_dist = c["name"], dist
        if best_name:
            return best_name
    return _generic_shade_name(hex_code)


def _dedupe_shade_names(names: list[str]) -> list[str]:
    """Two hexes in one product can land on the same nearest generic name —
    number the repeats so the product never shows two identically-named shades."""
    seen: dict[str, int] = {}
    deduped = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        deduped.append(name if seen[name] == 1 else f"{name} {seen[name]}")
    return deduped


# makeup-api prices are all USD. The rest of the catalogue (hand-written
# categories, and everything else in this script) is priced in ₹, so we
# convert with a fixed rate to keep the currency consistent for now. Swap
# this for a live FX rate / proper localisation later.
# Snapshot as of 2026-09-06 (spot rate was ~94.4-95.6 that week) — re-check
# and bump this periodically, since a stale rate silently underprices (or
# overprices) every makeup-api-sourced product in the catalogue.
USD_TO_INR_RATE = 95


def format_price(api_product: dict | None) -> str:
    if not api_product or not api_product.get("price"):
        return "₹—"
    try:
        usd = float(api_product["price"])
    except (TypeError, ValueError):
        return "₹—"
    if usd <= 0:
        # makeup-api uses "0.0" as its "no price on file" sentinel, not a
        # literal free product.
        return "₹—"
    inr = round(usd * USD_TO_INR_RATE)
    return f"₹{inr:,}"


# Real Indian retail prices (Nykaa / Sephora India / Tira Beauty, checked
# 2026-09-06), for products whose automated source has a real name/image but
# no price at all — mainly allShades.csv, which has no price field by
# design. Keyed by (brand, product name) exactly as it appears in the built
# catalogue, applied only when the automated price is "₹—" so a source that
# *does* have real pricing is never overridden. Deliberately left out for
# products with no confirmed Indian listing (Black Up, Shiseido Synchro Skin,
# and various small US-only indie brands) rather than guessing a number.
MANUAL_PRICE_OVERRIDES: dict[tuple[str, str], str] = {
    ("MAC", "Studio Fix Powder Plus Foundation"): "₹3,900",
    ("Estée Lauder", "Double Wear Stay-in-Place Makeup"): "₹4,600",
    ("Lancôme", "Teint Idole Ultra Wear 24H Long Wear Foundation"): "₹4,400",
    ("Bobbi Brown", "Skin Long-Wear Weightless Foundation SPF 15"): "₹4,900",
    ("bareMinerals", "BAREPRO Longwear Powder Foundation"): "₹3,100",
    ("Make Up For Ever", "Ultra HD Invisible Cover Foundation"): "₹3,900",
    ("Clinique", "Clinique Pop™ Oil Lip & Cheek Glow"): "₹2,800",
}


def _apply_price_override(brand: str, name: str, price_prefix: str) -> str:
    if price_prefix == "₹—":
        return MANUAL_PRICE_OVERRIDES.get((brand, name), price_prefix)
    return price_prefix


# Products no automated source can match, but that are worth surfacing
# anyway — patched in by hand with real name/image/price sourced directly
# from the brand's own site. Black Up is a notable deep/dark-skin-tone
# specialist brand that neither makeup-api nor allShades carries (verified:
# a fresh live fetch of makeup-api's foundation catalogue has no "Black Up"
# brand at all), so without this override it silently disappears from the
# "rich deep" end of the shelf on every regen. Keyed by the exact (brand,
# product-line) pair as it appears in shades.csv. These take priority over
# the automated tiers and are never overwritten by them.
MANUAL_OVERRIDES: dict[tuple[str, str], dict] = {
    ("Black Up", "Matifying Fluid"): {
        "name": "Mattifying Fluid Foundation",
        "image": "https://www.blackup.com/cdn/shop/files/NFL00.jpg?v=1745508070&width=500",
        "price_prefix": "₹—",
    },
}


def build_catalogue(refresh: bool) -> dict:
    pudding = load_pudding_shades(refresh)
    api_candidates = load_makeup_api_candidates(refresh)
    allshades_candidates = load_allshades_candidates(refresh)
    nykaa_candidates = load_nykaa_candidates()

    products = []
    counts = {"makeup-api": 0, "allshades": 0, "nykaa": 0, "manual": 0, "none": 0}
    for (brand, product), hex_codes in sorted(pudding.items()):
        override = MANUAL_OVERRIDES.get((brand, product))
        if override:
            match, source = {**override, "palette": []}, "manual"
        else:
            match = find_best_match(brand, product, api_candidates)
            source = "makeup-api"
            if not match:
                match = find_best_match(brand, product, allshades_candidates)
                source = "allshades"
            if not match:
                match = find_best_match(brand, product, nykaa_candidates)
                source = "nykaa"
            if not match:
                source = "none"

        counts[source] += 1
        label = f"-> [{source}] {match['name']}" if match else "-> no match"
        print(f"{brand:20s} {product:30s} {label}")

        final_name = match["name"] if match else product
        products.append({
            "id": _slugify(f"{brand}-{product}"),
            "brand": brand,
            "name": final_name,
            "image": match["image"] if match else "/assets/products/placeholder.jpg",
            "price_prefix": _apply_price_override(
                brand, final_name, match["price_prefix"] if match else "₹—"
            ),
            "dark_background": False,
            # Set when neither makeup-api nor allShades had a real match for this
            # product — catalogue.py/router.py use this to hide unverified rows
            # rather than showing a hex code standing in for a product name.
            "verified": match is not None,
            "shades": [
                {"name": name, "hex": hex_code}
                for name, hex_code in zip(
                    _dedupe_shade_names([shade_name_for(h, match) for h in hex_codes]),
                    hex_codes,
                )
            ],
        })

    total = len(products)
    print(
        f"\n{counts['makeup-api']} matched via makeup-api, "
        f"{counts['allshades']} via allShades, "
        f"{counts['nykaa']} via nykaa, "
        f"{counts['manual']} manual override, "
        f"{counts['none']} unmatched (of {total})"
    )

    return {
        "key": "foundation",
        "label": "Foundation",
        "icon": "🫧",
        "skip_color_matching": False,
        "products": products,
    }


# ── Categories sourced entirely from makeup-api ─────────────────────
#
# Unlike foundation, makeup-api is self-sufficient for these: every product
# already carries its own shade names *and* hex codes (product_colors), so
# there's no separate base dataset or enrichment/borrowing step — just
# fetch, drop products with no shade or brand/name data, and format.

# makeup-api brand names are lowercase free text — .title() gets most of
# them right (e.g. "physicians formula" -> "Physicians Formula") but mangles
# a few with their own stylisation or capitalisation the catalogue already
# uses elsewhere (e.g. "e.l.f." in the hand-written categories).
_BRAND_DISPLAY_OVERRIDES = {
    "e.l.f.": "e.l.f.",
    "nyx": "NYX",
    "covergirl": "CoverGirl",
    "l'oreal": "L'Oréal",
    "lotus cosmetics usa": "Lotus Cosmetics USA",
    # str.title() capitalises the letter right after any apostrophe, which
    # is right for "L'Oréal" but wrong for a plain possessive or "c'est".
    "burt's bees": "Burt's Bees",
    "c'est moi": "C'est Moi",
    "sally b's skin yummies": "Sally B's Skin Yummies",
    "wet n wild": "Wet n Wild",
}


def _display_brand(raw_brand: str) -> str:
    key = raw_brand.strip().lower()
    return _BRAND_DISPLAY_OVERRIDES.get(key, html.unescape(raw_brand.strip()).title())


# makeup-api tags a handful of bronzer/contour palettes as product_type
# "blush" even though their actual pigments are brown, not pink — e.g. NYX's
# "Cheek Contour Duo Palette" (#8F4D3D, #6B4530...). Matching these against
# a user's blush palette either buries real blush under contour shades, or
# (for deep skin, where blush and bronzer sit closer in lightness) shows a
# literal contour product as a "blush" recommendation. Name-based, since
# makeup-api has no separate contour/bronzer product_type to filter on instead.
_NON_BLUSH_NAME_MARKERS = ("contour", "bronz")


def build_makeup_api_category(
    product_type: str, key: str, label: str, icon: str, refresh: bool
) -> dict:
    url = f"http://makeup-api.herokuapp.com/api/v1/products.json?product_type={product_type}"
    raw = _fetch(url, RAW_DIR / f"makeup_api_{product_type}.json", refresh)
    api_products = json.loads(raw.decode("utf-8"))

    products = []
    skipped = 0
    for p in api_products:
        colors = p.get("product_colors") or []
        if not colors or not p.get("brand") or not p.get("name"):
            skipped += 1
            continue
        if key == "blush" and any(m in p["name"].lower() for m in _NON_BLUSH_NAME_MARKERS):
            skipped += 1
            continue

        brand = _display_brand(p["brand"])
        name = html.unescape(p["name"].strip())

        # A handful of "colours" (e.g. Clinique's contouring palettes) pack
        # several comma-separated hex codes under one colour_name — split
        # those into one shade per hex instead of one bad multi-hex string.
        hexes: list[str] = []
        raw_names: list[str] = []
        for c in colors:
            colour_name = html.unescape((c.get("colour_name") or "").strip())
            for hex_part in (c.get("hex_value") or "").split(","):
                hex_code = "#" + hex_part.strip().lstrip("#").upper()
                if not HEX_RE.match(hex_code):
                    continue
                hexes.append(hex_code)
                raw_names.append(colour_name or _generic_shade_name(hex_code))

        if not hexes:
            skipped += 1
            continue

        shade_names = _dedupe_shade_names(raw_names)

        products.append({
            "id": _slugify(f"{brand}-{name}"),
            "brand": brand,
            "name": name,
            "image": p["image_link"],
            "price_prefix": _apply_price_override(brand, name, format_price(p)),
            "dark_background": False,
            "shades": [
                {"name": shade_name, "hex": hex_code}
                for shade_name, hex_code in zip(shade_names, hexes)
            ],
        })

    print(f"{key}: {len(products)} products with shade data, {skipped} skipped (no colours/brand/name)")

    return {
        "key": key,
        "label": label,
        "icon": icon,
        "skip_color_matching": False,
        "products": products,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-download source data instead of using the local cache")
    args = parser.parse_args()

    foundation = build_catalogue(args.refresh)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(foundation, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUT_PATH}")

    data_dir = ROOT / "app" / "recommendations" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    blush = build_makeup_api_category("blush", "blush", "Blush", "🌸", args.refresh)
    (data_dir / "blush.json").write_text(json.dumps(blush, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {data_dir / 'blush.json'}")

    lipstick = build_makeup_api_category("lipstick", "lip", "Lip", "💋", args.refresh)
    (data_dir / "lip.json").write_text(json.dumps(lipstick, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {data_dir / 'lip.json'}")


if __name__ == "__main__":
    main()
