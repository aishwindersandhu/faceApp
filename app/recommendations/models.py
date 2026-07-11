"""
Request / response models for POST /recommendations/{user_id}

The request shape mirrors exactly what /analyze already returns —
so the frontend can pass the analysis response straight into this
endpoint with no transformation needed.

Field names are camelCase on the wire (alias_generator=to_camel)
so they match your existing frontend TypeScript types 1:1.
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """All models serialise as camelCase on the wire."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # also accept snake_case on input
    )


# ── REQUEST ──────────────────────────────────────────────────────

class ColourSwatch(CamelModel):
    """One entry in colorPalette from /analyze."""
    name: str
    hex: str


class AnalysisProfile(CamelModel):
    """
    The profile object from /analyze — passed as-is to this endpoint.
    Only the fields we actually use are listed; extras are ignored.
    """
    undertone: Literal["warm", "cool", "neutral"]
    depth: str
    L: int
    a: int
    b: int
    lip_shades: list[ColourSwatch] = Field(default_factory=list)
    blush_shades: list[ColourSwatch] = Field(default_factory=list)
    warm_palette: list[ColourSwatch] = Field(default_factory=list)
    cool_palette: list[ColourSwatch] = Field(default_factory=list)
    jewel_tones: list[ColourSwatch] = Field(default_factory=list)


class RecommendationRequest(CamelModel):
    """
    Mirrors the response shape from POST /analyze exactly.

    Frontend usage:
        const analysis = await analyzeImage(file);
        const recs = await fetch(`/recommendations/${userId}`, {
            method: 'POST',
            body: JSON.stringify(analysis.data),   // ← pass straight through
        });
    """
    skin_tone: str = Field(alias="skinTone")          # e.g. "Medium"
    color_code: str = Field(alias="colorCode")        # e.g. "#BD8453"
    color_palette: list[str] = Field(                 # [conceal, base, contour, highlight]
        alias="colorPalette",
        default_factory=list
    )
    profile: AnalysisProfile


# ── RESPONSE ─────────────────────────────────────────────────────

class ShadeOut(CamelModel):
    name: str
    hex: str


class ProductOut(CamelModel):
    id: str
    brand: str
    name: str
    image: str
    match_percent: int = Field(ge=0, le=100)
    is_top_pick: bool = False
    shades: list[ShadeOut]
    price: str
    dark_background: bool = False


class CategoryOut(CamelModel):
    key: str
    label: str
    icon: str
    products: list[ProductOut]


class RecommendationResponse(CamelModel):
    tone_label: str                    # e.g. "Medium Warm"
    match_percent: int                 # overall score, 0-100
    categories: list[CategoryOut]
    avoid_colors: list[str]
    avoid_label: str = "Avoid these"
    avoid_description: str = "These shades clash with your undertone"