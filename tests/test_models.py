import pytest
from pydantic import ValidationError

from app.recommendations.models import ProductOut, RecommendationRequest, RecommendationResponse, ShadeOut

VALID_PROFILE = {
    "undertone": "warm",
    "depth": "Medium",
    "L": 140,
    "a": 150,
    "b": 160,
}


def test_request_accepts_camel_case_payload():
    body = {
        "skinTone": "Medium",
        "colorCode": "#BD8453",
        "colorPalette": ["#a", "#b", "#c", "#d"],
        "profile": VALID_PROFILE,
    }
    req = RecommendationRequest.model_validate(body)
    assert req.skin_tone == "Medium"
    assert req.color_code == "#BD8453"
    assert req.profile.undertone == "warm"


def test_request_also_accepts_snake_case_payload():
    body = {
        "skin_tone": "Medium",
        "color_code": "#BD8453",
        "profile": VALID_PROFILE,
    }
    req = RecommendationRequest.model_validate(body)
    assert req.skin_tone == "Medium"


def test_request_color_palette_defaults_to_empty_list():
    req = RecommendationRequest.model_validate(
        {"skinTone": "Medium", "colorCode": "#BD8453", "profile": VALID_PROFILE}
    )
    assert req.color_palette == []


def test_request_rejects_invalid_undertone():
    body = {
        "skinTone": "Medium",
        "colorCode": "#BD8453",
        "profile": {**VALID_PROFILE, "undertone": "sideways"},
    }
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(body)


def test_response_serialises_to_camel_case():
    resp = RecommendationResponse(
        tone_label="Medium Warm",
        match_percent=88,
        categories=[],
        avoid_colors=["#FFFFFF"],
    )
    dumped = resp.model_dump(by_alias=True)
    assert dumped["toneLabel"] == "Medium Warm"
    assert dumped["matchPercent"] == 88
    assert dumped["avoidColors"] == ["#FFFFFF"]
    assert "tone_label" not in dumped


def test_product_out_rejects_match_percent_out_of_range():
    with pytest.raises(ValidationError):
        ProductOut(
            id="x",
            brand="x",
            name="x",
            image="x",
            match_percent=101,
            shades=[ShadeOut(name="a", hex="#FFFFFF")],
            price="x",
        )
