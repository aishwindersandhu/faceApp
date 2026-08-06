import sys
from pathlib import Path

import pytest

# scripts/ isn't a package, so import it by adding scripts/ to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_catalogue as bc  # noqa: E402


def test_normalize_strips_accents_and_punctuation():
    assert bc._normalize("PRO FILT'R!") == "pro filt r"
    assert bc._normalize("Fenty  Beauty") == "fenty beauty"
    assert bc._normalize("Café") == "cafe"


def test_slugify_produces_url_safe_id():
    assert bc._slugify("Fenty Beauty") == "fenty-beauty"
    assert bc._slugify("PRO FILT'R Foundation") == "pro-filt-r-foundation"


def test_hex_to_rgb_roundtrip():
    assert bc._hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert bc._hex_to_rgb("000000") == (0, 0, 0)
    assert bc._hex_to_rgb("#1a2b3c") == (0x1A, 0x2B, 0x3C)


def test_rgb_distance_zero_for_identical_colours():
    assert bc._rgb_distance("#123456", "#123456") == 0


def test_rgb_distance_max_between_black_and_white():
    dist = bc._rgb_distance("#000000", "#FFFFFF")
    assert dist == pytest.approx((255**2 * 3) ** 0.5)


def test_tokens_drops_single_character_tokens():
    assert bc._tokens("PRO FILT'R - Soft Matte") == ["pro", "filt", "soft", "matte"]


def test_fuzzy_token_present_matches_close_typo():
    assert bc._fuzzy_token_present("filtr", ["filt", "soft", "matte"])
    assert not bc._fuzzy_token_present("xyz", ["filt", "soft", "matte"])


def test_token_overlap_full_and_partial():
    assert bc._token_overlap(["pro", "filtr"], ["pro", "filtr", "soft"]) == 1.0
    assert bc._token_overlap(["pro", "filtr"], ["soft", "matte"]) == 0.0
    assert bc._token_overlap([], ["soft"]) == 0.0


def test_find_best_match_requires_brand_overlap():
    candidates = [
        {"brand": "Fenty Beauty", "name": "Pro Filt'r Soft Matte Foundation"},
        {"brand": "MAC", "name": "Studio Fix Fluid"},
    ]
    match = bc.find_best_match("Fenty Beauty", "PRO FILT'R", candidates)
    assert match["brand"] == "Fenty Beauty"


def test_find_best_match_returns_none_below_threshold():
    candidates = [{"brand": "Fenty Beauty", "name": "Gloss Bomb Lip Gloss"}]
    match = bc.find_best_match("Fenty Beauty", "PRO FILT'R Foundation", candidates)
    assert match is None


def test_shade_name_for_picks_closest_palette_colour_within_max_distance():
    match = {"palette": [{"hex": "#000000", "name": "Onyx"}, {"hex": "#FFFFFF", "name": "Ivory"}]}
    assert bc.shade_name_for("#010101", match) == "Onyx"


def test_shade_name_for_falls_back_to_hex_when_no_match_or_too_far():
    assert bc.shade_name_for("#ABCDEF", None) == "#ABCDEF"

    match = {"palette": [{"hex": "#000000", "name": "Onyx"}]}
    assert bc.shade_name_for("#FFFFFF", match) == "#FFFFFF"  # distance exceeds MAX


def test_format_price_converts_usd_to_inr():
    assert bc.format_price({"price": "10"}) == f"₹{round(10 * bc.USD_TO_INR_RATE):,}"


@pytest.mark.parametrize("api_product", [None, {}, {"price": None}, {"price": "not-a-number"}])
def test_format_price_falls_back_to_placeholder(api_product):
    assert bc.format_price(api_product) == "₹—"
