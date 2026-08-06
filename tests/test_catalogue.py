import re

import pytest

from app.recommendations.catalogue import AVOID_COLORS, AVOID_DESCRIPTIONS, CATALOGUE

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_catalogue_has_expected_categories():
    keys = {c["key"] for c in CATALOGUE}
    assert keys == {"foundation", "blush", "lip", "eye", "highlight"}


def test_category_keys_are_unique():
    keys = [c["key"] for c in CATALOGUE]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("category", CATALOGUE, ids=lambda c: c["key"])
def test_category_has_required_fields(category):
    for field in ("key", "label", "icon", "products", "skip_color_matching"):
        assert field in category
    assert isinstance(category["products"], list)
    assert len(category["products"]) > 0


def test_product_ids_are_globally_unique():
    ids = [p["id"] for c in CATALOGUE for p in c["products"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("category", CATALOGUE, ids=lambda c: c["key"])
def test_every_product_has_at_least_one_valid_shade(category):
    for product in category["products"]:
        assert len(product["shades"]) > 0
        for shade in product["shades"]:
            assert HEX_RE.match(shade["hex"]), f"{product['id']} has bad hex {shade['hex']!r}"


@pytest.mark.parametrize("category", CATALOGUE, ids=lambda c: c["key"])
def test_every_product_has_required_fields(category):
    required = {"id", "brand", "name", "image", "price_prefix", "shades", "dark_background"}
    for product in category["products"]:
        assert required.issubset(product.keys())


def test_eye_category_skips_color_matching():
    eye = next(c for c in CATALOGUE if c["key"] == "eye")
    assert eye["skip_color_matching"] is True


def test_avoid_colors_and_descriptions_cover_all_undertones():
    for undertone in ("warm", "cool", "neutral"):
        assert undertone in AVOID_COLORS
        assert undertone in AVOID_DESCRIPTIONS
        assert all(HEX_RE.match(h) for h in AVOID_COLORS[undertone])
