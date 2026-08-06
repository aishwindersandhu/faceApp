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

  Products that neither source matches fall back to a placeholder image,
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


def shade_name_for(hex_code: str, match: dict | None) -> str:
    if match:
        best_name, best_dist = None, COLOR_MATCH_MAX_DISTANCE
        for c in match["palette"]:
            dist = _rgb_distance(hex_code, c["hex"])
            if dist < best_dist:
                best_name, best_dist = c["name"], dist
        if best_name:
            return best_name
    return hex_code


# makeup-api prices are all USD. The rest of the catalogue (hand-written
# categories, and everything else in this script) is priced in ₹, so we
# convert with a fixed rate to keep the currency consistent for now. Swap
# this for a live FX rate / proper localisation later.
USD_TO_INR_RATE = 83


def format_price(api_product: dict | None) -> str:
    if not api_product or not api_product.get("price"):
        return "₹—"
    try:
        usd = float(api_product["price"])
    except (TypeError, ValueError):
        return "₹—"
    inr = round(usd * USD_TO_INR_RATE)
    return f"₹{inr:,}"


def build_catalogue(refresh: bool) -> dict:
    pudding = load_pudding_shades(refresh)
    api_candidates = load_makeup_api_candidates(refresh)
    allshades_candidates = load_allshades_candidates(refresh)

    products = []
    counts = {"makeup-api": 0, "allshades": 0, "none": 0}
    for (brand, product), hex_codes in sorted(pudding.items()):
        match = find_best_match(brand, product, api_candidates)
        source = "makeup-api"
        if not match:
            match = find_best_match(brand, product, allshades_candidates)
            source = "allshades"
        if not match:
            source = "none"

        counts[source] += 1
        label = f"-> [{source}] {match['name']}" if match else "-> no match"
        print(f"{brand:20s} {product:30s} {label}")

        products.append({
            "id": _slugify(f"{brand}-{product}"),
            "brand": brand,
            "name": match["name"] if match else product,
            "image": match["image"] if match else "/assets/products/placeholder.jpg",
            "price_prefix": match["price_prefix"] if match else "₹—",
            "dark_background": False,
            # Set when neither makeup-api nor allShades had a real match for this
            # product — catalogue.py/router.py use this to hide unverified rows
            # rather than showing a hex code standing in for a product name.
            "verified": match is not None,
            "shades": [
                {"name": shade_name_for(hex_code, match), "hex": hex_code}
                for hex_code in hex_codes
            ],
        })

    total = len(products)
    print(
        f"\n{counts['makeup-api']} matched via makeup-api, "
        f"{counts['allshades']} via allShades, "
        f"{counts['none']} unmatched (of {total})"
    )

    return {
        "key": "foundation",
        "label": "Foundation",
        "icon": "🫧",
        "skip_color_matching": False,
        "products": products,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-download source data instead of using the local cache")
    args = parser.parse_args()

    category = build_catalogue(args.refresh)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(category, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
