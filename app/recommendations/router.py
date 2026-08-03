"""
POST /recommendations/{user_id}

Accepts the output of /analyze and returns a ProductsPanel payload.

Frontend flow:
    1. POST /analyze  → get skin tone analysis
    2. POST /recommendations/{userId}  → pass analysis, get products
    3. Pass response directly into <ProductsPanel ... />
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.recommendations.catalogue import AVOID_COLORS, AVOID_DESCRIPTIONS, CATALOGUE
from app.recommendations.matcher import best_shade_match
from app.recommendations.models import (
    CategoryOut,
    ProductOut,
    RecommendationRequest,
    RecommendationResponse,
    ShadeOut,
)
router = APIRouter()

  
@router.post("/recommendations/{user_id}", response_model=RecommendationResponse)
async def get_recommendations(
    user_id: str,
    body: RecommendationRequest,
) -> RecommendationResponse:
    """
    Match the user's detected skin tone against the product catalogue
    and return a shelf-row payload for the Products panel.
    """
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")

    skin_hex  = body.color_code           # e.g. "#BD8453"
    undertone = body.profile.undertone    # "warm" | "cool" | "neutral"
    depth     = body.profile.depth        # e.g. "Medium"

    categories_out: list[CategoryOut] = []

    for category in CATALOGUE:
        products_out: list[ProductOut] = []

        for product in category["products"]:
            shade_hexes = [s["hex"] for s in product["shades"]]

            if category["skip_color_matching"]:
                # Eye/mascara — doesn't need skin tone matching
                score = 90
            else:
                _, score = best_shade_match(skin_hex, shade_hexes)

            products_out.append(
                ProductOut(
                    id=product["id"],
                    brand=product["brand"],
                    name=product["name"],
                    image=product["image"],
                    match_percent=score,
                    is_top_pick=False,          # set below after sort
                    shades=[
                        ShadeOut(name=s["name"], hex=s["hex"])
                        for s in product["shades"]
                    ],
                    price=product["price_prefix"],
                    dark_background=product["dark_background"],
                )
            )

        # Sort by match score descending, mark the top one
        products_out.sort(key=lambda p: p.match_percent, reverse=True)
        if products_out:
            products_out[0].is_top_pick = True

        categories_out.append(
            CategoryOut(
                key=category["key"],
                label=category["label"],
                icon=category["icon"],
                products=products_out,
            )
        )

    # Overall match = average of each shelf's top pick score
    top_scores = [c.products[0].match_percent for c in categories_out if c.products]
    overall    = round(sum(top_scores) / len(top_scores)) if top_scores else 0

    # Tone label e.g. "Medium Warm" or "Fair Cool"
    tone_label = f"{depth} {undertone.capitalize()}"

    return RecommendationResponse(
        tone_label=tone_label,
        match_percent=overall,
        categories=categories_out,
        avoid_colors=AVOID_COLORS.get(undertone, AVOID_COLORS["neutral"]),
        avoid_label="Avoid these",
        avoid_description=AVOID_DESCRIPTIONS.get(
            undertone, AVOID_DESCRIPTIONS["neutral"]
        ),
    )