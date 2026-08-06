import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.recommendations.router import router

# `app/recommendations/__init__.py` does `from .router import router`, which
# overwrites the `router` *submodule* attribute on the package with the
# APIRouter instance. `import app.recommendations.router as x` resolves via
# that same attribute chain and would silently bind x to the APIRouter too —
# importlib.import_module reads sys.modules directly and avoids the trap.
router_module = importlib.import_module("app.recommendations.router")

FIXTURE_CATALOGUE = [
    {
        "key": "shelf",
        "label": "Shelf",
        "icon": "x",
        "skip_color_matching": False,
        "products": [
            {
                "id": "close-match",
                "brand": "Brand",
                "name": "Close Match",
                "image": "/img.jpg",
                "price_prefix": "₹100",
                "dark_background": False,
                "shades": [{"name": "Black", "hex": "#000000"}],
            },
            {
                "id": "unverified",
                "brand": "Brand",
                "name": "Unverified",
                "image": "/img.jpg",
                "price_prefix": "₹100",
                "dark_background": False,
                "verified": False,
                "shades": [{"name": "Black", "hex": "#000000"}],
            },
            {
                "id": "far-match",
                "brand": "Brand",
                "name": "Far Match",
                "image": "/img.jpg",
                "price_prefix": "₹100",
                "dark_background": False,
                "shades": [{"name": "White", "hex": "#FFFFFF"}],
            },
        ],
    },
    {
        "key": "mascara",
        "label": "Mascara",
        "icon": "x",
        "skip_color_matching": True,
        "products": [
            {
                "id": "any-mascara",
                "brand": "Brand",
                "name": "Any Mascara",
                "image": "/img.jpg",
                "price_prefix": "₹100",
                "dark_background": True,
                "shades": [{"name": "Black", "hex": "#1A1A1A"}],
            },
        ],
    },
    {
        "key": "all-filtered-out",
        "label": "All Filtered Out",
        "icon": "x",
        "skip_color_matching": False,
        "products": [
            {
                "id": "too-far",
                "brand": "Brand",
                "name": "Too Far",
                "image": "/img.jpg",
                "price_prefix": "₹100",
                "dark_background": False,
                "shades": [{"name": "White", "hex": "#FFFFFF"}],
            },
        ],
    },
]


def make_body(color_code="#000000"):
    return {
        "skinTone": "Deep",
        "colorCode": color_code,
        "colorPalette": ["#a", "#b", "#c", "#d"],
        "profile": {
            "undertone": "warm",
            "depth": "Deep",
            "L": 40,
            "a": 150,
            "b": 160,
        },
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(router_module, "CATALOGUE", FIXTURE_CATALOGUE)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_empty_user_id_segment_404s_before_reaching_the_handler(client):
    # The str path converter requires 1+ chars, so "/recommendations/" never
    # dispatches to get_recommendations — the `if not user_id` check in the
    # handler is unreachable in practice.
    resp = client.post("/recommendations/", json=make_body())
    assert resp.status_code == 404


def test_whitespace_user_id_is_accepted(client):
    resp = client.post("/recommendations/%20", json=make_body())
    assert resp.status_code == 200


def test_filters_out_unverified_and_low_match_products(client):
    resp = client.post("/recommendations/user1", json=make_body())
    assert resp.status_code == 200
    body = resp.json()

    shelf = next(c for c in body["categories"] if c["key"] == "shelf")
    product_ids = {p["id"] for p in shelf["products"]}
    assert product_ids == {"close-match"}  # unverified and far-match both dropped


def test_category_dropped_when_everything_filtered_out(client):
    resp = client.post("/recommendations/user1", json=make_body())
    body = resp.json()
    keys = {c["key"] for c in body["categories"]}
    assert "all-filtered-out" not in keys


def test_top_pick_is_marked_on_best_scoring_product(client):
    resp = client.post("/recommendations/user1", json=make_body())
    body = resp.json()
    shelf = next(c for c in body["categories"] if c["key"] == "shelf")
    assert shelf["products"][0]["id"] == "close-match"
    assert shelf["products"][0]["isTopPick"] is True


def test_skip_color_matching_category_always_scores_90(client):
    resp = client.post("/recommendations/user1", json=make_body())
    body = resp.json()
    mascara = next(c for c in body["categories"] if c["key"] == "mascara")
    assert mascara["products"][0]["matchPercent"] == 90


def test_tone_label_combines_depth_and_undertone(client):
    resp = client.post("/recommendations/user1", json=make_body())
    body = resp.json()
    assert body["toneLabel"] == "Deep Warm"


def test_overall_match_percent_averages_top_picks_per_shelf(client):
    resp = client.post("/recommendations/user1", json=make_body())
    body = resp.json()
    top_scores = [c["products"][0]["matchPercent"] for c in body["categories"]]
    assert body["matchPercent"] == round(sum(top_scores) / len(top_scores))


def test_avoid_colors_reflect_undertone(client):
    from app.recommendations.catalogue import AVOID_COLORS

    resp = client.post("/recommendations/user1", json=make_body())
    body = resp.json()
    assert body["avoidColors"] == AVOID_COLORS["warm"]


def test_unknown_undertone_falls_back_to_neutral_avoid_colors(client):
    from app.recommendations.catalogue import AVOID_COLORS

    body = make_body()
    body["profile"]["undertone"] = "neutral"
    resp = client.post("/recommendations/user1", json=body)
    assert resp.json()["avoidColors"] == AVOID_COLORS["neutral"]


class TestRealCatalogueSmoke:
    """Sanity check against the real, unmocked product catalogue."""

    def test_endpoint_returns_well_formed_response(self):
        from app.main import app as real_app

        client = TestClient(real_app)
        resp = client.post("/recommendations/user1", json=make_body("#BD8453"))
        assert resp.status_code == 200
        body = resp.json()
        assert 0 <= body["matchPercent"] <= 100
        for category in body["categories"]:
            for product in category["products"]:
                assert 0 <= product["matchPercent"] <= 100
