"""
Product catalogue.

Each product has a list of shades — the matcher picks the shade
closest to the user's detected skin tone and reports that shade's
match score.

image paths are relative to your static files / CDN root.
Replace with real Nykaa / Amazon URLs when you have them.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import TypedDict

_DATA_DIR = Path(__file__).parent / "data"


def _load_category(filename: str) -> "CatalogueCategory":
    with open(_DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


class Shade(TypedDict):
    name: str
    hex: str


class CatalogueProduct(TypedDict):
    id: str
    brand: str
    name: str
    image: str
    price_prefix: str        # e.g. "₹3,900"
    shades: list[Shade]
    dark_background: bool    # True for mascaras etc. where card needs dark bg
    # NOT declared here since it's optional: only auto-generated products
    # (see scripts/build_catalogue.py) carry a "verified" key. False means no
    # real name/image/price was found for it — router.py hides those rather
    # than showing a hex code standing in for a product name. Hand-written
    # categories have no such key and are always treated as verified.


class CatalogueCategory(TypedDict):
    key: str
    label: str
    icon: str
    products: list[CatalogueProduct]
    # If True, skip colour matching (e.g. mascara — everyone wears black)
    skip_color_matching: bool


CATALOGUE: list[CatalogueCategory] = [
    # Generated from The Pudding's "Shades of You" dataset + makeup-api.herokuapp.com —
    # see scripts/build_catalogue.py to regenerate.
    _load_category("foundation.json"),
    {
        "key": "blush",
        "label": "Blush",
        "icon": "🌸",
        "skip_color_matching": False,
        "products": [
            {
                "id": "rare-beauty-soft-pinch",
                "brand": "Rare Beauty",
                "name": "Soft Pinch Liquid Blush",
                "image": "/assets/products/rare-beauty-soft-pinch.jpg",
                "price_prefix": "₹2,900",
                "dark_background": False,
                "shades": [
                    {"name": "Encourage", "hex": "#C87A55"},
                    {"name": "Joy",       "hex": "#D4856A"},
                    {"name": "Hope",      "hex": "#B86548"},
                    {"name": "Bliss",     "hex": "#C07060"},
                ],
            },
            {
                "id": "nars-orgasm-blush",
                "brand": "NARS",
                "name": "Orgasm Blush",
                "image": "/assets/products/nars-orgasm-blush.jpg",
                "price_prefix": "₹2,600",
                "dark_background": False,
                "shades": [
                    {"name": "Orgasm",      "hex": "#D4855A"},
                    {"name": "Deep Orgasm", "hex": "#C9714A"},
                ],
            },
            {
                "id": "ct-cheek-to-chic",
                "brand": "Charlotte Tilbury",
                "name": "Cheek to Chic Blush",
                "image": "/assets/products/ct-cheek-to-chic.jpg",
                "price_prefix": "₹4,500",
                "dark_background": False,
                "shades": [
                    {"name": "Pillow Talk", "hex": "#D4906A"},
                    {"name": "Love Glow",   "hex": "#C88060"},
                ],
            },
            {
                "id": "benefit-hoola",
                "brand": "Benefit",
                "name": "Hoola Matte Bronzer",
                "image": "/assets/products/benefit-hoola.jpg",
                "price_prefix": "₹3,100",
                "dark_background": False,
                "shades": [
                    {"name": "Medium", "hex": "#A0673A"},
                    {"name": "Deep",   "hex": "#8B5530"},
                ],
            },
            {
                "id": "elf-putty-blush",
                "brand": "e.l.f.",
                "name": "Putty Blush",
                "image": "/assets/products/elf-putty-blush.jpg",
                "price_prefix": "₹650",
                "dark_background": False,
                "shades": [
                    {"name": "Persimmon", "hex": "#D4705A"},
                    {"name": "Naked",     "hex": "#C8906A"},
                ],
            },
            {
                "id": "milk-cream-blush",
                "brand": "Milk Makeup",
                "name": "Cream Blush",
                "image": "/assets/products/milk-cream-blush.jpg",
                "price_prefix": "₹2,400",
                "dark_background": False,
                "shades": [
                    {"name": "Werk",  "hex": "#C87A55"},
                    {"name": "Lit",   "hex": "#D4856A"},
                ],
            },
            {
                "id": "glossier-cloud-paint",
                "brand": "Glossier",
                "name": "Cloud Paint",
                "image": "/assets/products/glossier-cloud-paint.jpg",
                "price_prefix": "₹2,100",
                "dark_background": False,
                "shades": [
                    {"name": "Beam",  "hex": "#D4906A"},
                    {"name": "Dusk",  "hex": "#B86548"},
                ],
            },
        ],
    },
    {
        "key": "lip",
        "label": "Lip",
        "icon": "💋",
        "skip_color_matching": False,
        "products": [
            {
                "id": "fenty-gloss-bomb",
                "brand": "Fenty Beauty",
                "name": "Gloss Bomb",
                "image": "/assets/products/fenty-gloss-bomb.jpg",
                "price_prefix": "₹2,500",
                "dark_background": False,
                "shades": [
                    {"name": "Nude Silk", "hex": "#C8906A"},
                    {"name": "Fu$$y",     "hex": "#D4A078"},
                    {"name": "Hot Chocolit", "hex": "#A06040"},
                ],
            },
            {
                "id": "mac-velvet-teddy",
                "brand": "MAC",
                "name": "Velvet Teddy Lipstick",
                "image": "/assets/products/mac-velvet-teddy.jpg",
                "price_prefix": "₹2,100",
                "dark_background": False,
                "shades": [
                    {"name": "Velvet Teddy", "hex": "#B07050"},
                    {"name": "Mehr",         "hex": "#C08060"},
                ],
            },
            {
                "id": "ct-walk-of-shame",
                "brand": "Charlotte Tilbury",
                "name": "Walk of Shame",
                "image": "/assets/products/ct-walk-of-shame.jpg",
                "price_prefix": "₹3,200",
                "dark_background": False,
                "shades": [
                    {"name": "Walk of Shame",  "hex": "#7B4A2D"},
                    {"name": "Heart of Glass", "hex": "#8B5A35"},
                ],
            },
            {
                "id": "nyx-soft-matte",
                "brand": "NYX",
                "name": "Soft Matte Lip Cream",
                "image": "/assets/products/nyx-soft-matte.jpg",
                "price_prefix": "₹850",
                "dark_background": False,
                "shades": [
                    {"name": "Cairo",     "hex": "#A0503A"},
                    {"name": "Abu Dhabi", "hex": "#903C28"},
                    {"name": "Madrid",    "hex": "#B06050"},
                ],
            },
            {
                "id": "lakme-9to5",
                "brand": "Lakme",
                "name": "9to5 Primer Matte",
                "image": "/assets/products/lakme-9to5.jpg",
                "price_prefix": "₹420",
                "dark_background": False,
                "shades": [
                    {"name": "Burgundy",  "hex": "#8B3A2A"},
                    {"name": "Brick Red", "hex": "#9B4A2A"},
                    {"name": "Nude",      "hex": "#C08060"},
                ],
            },
            {
                "id": "dior-addict-lip-glow",
                "brand": "Dior",
                "name": "Addict Lip Glow",
                "image": "/assets/products/dior-addict-lip-glow.jpg",
                "price_prefix": "₹3,600",
                "dark_background": False,
                "shades": [
                    {"name": "Berry",  "hex": "#9B4A3A"},
                    {"name": "Praline", "hex": "#A0603A"},
                ],
            },
            {
                "id": "colorbar-velvet-matte",
                "brand": "Colorbar",
                "name": "Velvet Matte Lipstick",
                "image": "/assets/products/colorbar-velvet-matte.jpg",
                "price_prefix": "₹650",
                "dark_background": False,
                "shades": [
                    {"name": "Rustic",     "hex": "#8B4A2A"},
                    {"name": "Chocoholic", "hex": "#6B3A22"},
                ],
            },
        ],
    },
    {
        "key": "eye",
        "label": "Eye",
        "icon": "👁",
        # Mascara is always black — colour matching against skin tone
        # doesn't make sense here. All products get a flat high score.
        "skip_color_matching": True,
        "products": [
            {
                "id": "too-faced-better-than-sex",
                "brand": "Too Faced",
                "name": "Better Than Sex Mascara",
                "image": "/assets/products/too-faced-mascara.jpg",
                "price_prefix": "₹2,800",
                "dark_background": True,
                "shades": [{"name": "Black", "hex": "#1A1A1A"}],
            },
            {
                "id": "ct-pillow-talk-mascara",
                "brand": "Charlotte Tilbury",
                "name": "Pillow Talk Mascara",
                "image": "/assets/products/ct-pillow-talk-mascara.jpg",
                "price_prefix": "₹3,200",
                "dark_background": True,
                "shades": [{"name": "Black", "hex": "#1A1A1A"}],
            },
            {
                "id": "maybelline-sky-high",
                "brand": "Maybelline",
                "name": "Sky High Mascara",
                "image": "/assets/products/maybelline-sky-high.jpg",
                "price_prefix": "₹699",
                "dark_background": True,
                "shades": [{"name": "Blackest Black", "hex": "#1A1A1A"}],
            },
            {
                "id": "loreal-lash-paradise",
                "brand": "L'Oréal",
                "name": "Lash Paradise Mascara",
                "image": "/assets/products/loreal-lash-paradise.jpg",
                "price_prefix": "₹650",
                "dark_background": True,
                "shades": [{"name": "Black", "hex": "#1A1A1A"}],
            },
            {
                "id": "benefit-badgal-bang",
                "brand": "Benefit",
                "name": "BADgal Bang Mascara",
                "image": "/assets/products/benefit-badgal-bang.jpg",
                "price_prefix": "₹2,600",
                "dark_background": True,
                "shades": [{"name": "Black", "hex": "#1A1A1A"}],
            },
            {
                "id": "essence-lash-princess",
                "brand": "essence",
                "name": "Lash Princess Mascara",
                "image": "/assets/products/essence-lash-princess.jpg",
                "price_prefix": "₹350",
                "dark_background": True,
                "shades": [{"name": "Black", "hex": "#1A1A1A"}],
            },
            {
                "id": "huda-beauty-legit-lashes",
                "brand": "Huda Beauty",
                "name": "Legit Lashes Mascara",
                "image": "/assets/products/huda-legit-lashes.jpg",
                "price_prefix": "₹2,200",
                "dark_background": True,
                "shades": [{"name": "Black", "hex": "#1A1A1A"}],
            },
        ],
    },
    {
        "key": "highlight",
        "label": "Highlight",
        "icon": "✨",
        "skip_color_matching": False,
        "products": [
            {
                "id": "becca-champagne-pop",
                "brand": "Becca",
                "name": "Shimmering Skin Perfector",
                "image": "/assets/products/becca-champagne-pop.jpg",
                "price_prefix": "₹3,800",
                "dark_background": False,
                "shades": [
                    {"name": "Champagne Pop", "hex": "#E8C99A"},
                    {"name": "Prosecco Pop",  "hex": "#D4A870"},
                    {"name": "Rose Gold",     "hex": "#D4A090"},
                ],
            },
            {
                "id": "fenty-killawatt",
                "brand": "Fenty Beauty",
                "name": "Killawatt Freestyle",
                "image": "/assets/products/fenty-killawatt.jpg",
                "price_prefix": "₹3,500",
                "dark_background": False,
                "shades": [
                    {"name": "Trophy Wife", "hex": "#D4A855"},
                    {"name": "Moscow Mule", "hex": "#C89050"},
                ],
            },
            {
                "id": "nyx-born-to-glow",
                "brand": "NYX",
                "name": "Born to Glow Illuminator",
                "image": "/assets/products/nyx-born-to-glow.jpg",
                "price_prefix": "₹950",
                "dark_background": False,
                "shades": [
                    {"name": "Sunbeam",   "hex": "#E0B870"},
                    {"name": "Gold",      "hex": "#D4A855"},
                    {"name": "Rose Gold", "hex": "#D4A090"},
                ],
            },
            {
                "id": "lakme-illuminating-drops",
                "brand": "Lakme",
                "name": "9to5 Illuminating Drops",
                "image": "/assets/products/lakme-illuminating-drops.jpg",
                "price_prefix": "₹399",
                "dark_background": False,
                "shades": [
                    {"name": "Gold",   "hex": "#E4C888"},
                    {"name": "Bronze", "hex": "#C8A060"},
                ],
            },
            {
                "id": "milk-holographic-stick",
                "brand": "Milk Makeup",
                "name": "Holographic Highlighting Stick",
                "image": "/assets/products/milk-holographic-stick.jpg",
                "price_prefix": "₹2,700",
                "dark_background": False,
                "shades": [
                    {"name": "Supernova", "hex": "#E8C99A"},
                    {"name": "Lit",       "hex": "#D4A870"},
                ],
            },
            {
                "id": "colorbar-strobe-highlighter",
                "brand": "Colorbar",
                "name": "Strobe Highlighter",
                "image": "/assets/products/colorbar-strobe-highlighter.jpg",
                "price_prefix": "₹850",
                "dark_background": False,
                "shades": [
                    {"name": "Gold Rush", "hex": "#D4A855"},
                    {"name": "Moonlight", "hex": "#E4C888"},
                ],
            },
            {
                "id": "physicians-formula-butter-glow",
                "brand": "Physicians Formula",
                "name": "Butter Believe It Highlighter",
                "image": "/assets/products/physicians-butter-glow.jpg",
                "price_prefix": "₹1,200",
                "dark_background": False,
                "shades": [
                    {"name": "Champagne", "hex": "#E0B870"},
                    {"name": "Rose Gold", "hex": "#D4A090"},
                ],
            },
        ],
    },
]


# Colours to warn users to avoid — keyed by undertone
AVOID_COLORS: dict[str, list[str]] = {
    "warm":    ["#B0C4DE", "#C0C0C0", "#ADD8E6", "#E0B4D0", "#98D8C8", "#BDB0D0"],
    "cool":    ["#E0B07A", "#D4A05A", "#C98A4A", "#E8C9A0", "#D9B88C", "#C9A36E"],
    "neutral": ["#F0E8D8", "#D8C8B8", "#E8D5C4", "#D0C0A8", "#C8B89A", "#E0D0BC"],
}

AVOID_DESCRIPTIONS: dict[str, str] = {
    "warm":    "Cool tones and silver metallics wash out warm undertones",
    "cool":    "Overly warm golden tones can clash with cool undertones",
    "neutral": "Very chalky or ashy neutrals can flatten neutral undertones",
}