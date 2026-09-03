"""
Colour matching logic.

Uses the same LAB colour space as image_processing.py — keeps
the matching consistent with how the palette was derived in the
first place.

We reuse OpenCV here so there's no new dependency to install.
"""

from __future__ import annotations

import math
from functools import lru_cache

import cv2
import numpy as np


@lru_cache(maxsize=4096)
def hex_to_lab(hex_color: str) -> tuple[float, float, float]:
    """
    Convert a hex colour string to OpenCV LAB values.
    Returns (L, a, b) as floats in OpenCV scale (L: 0-255, a/b: 0-255).

    Cached: the catalogue's shade hexes are a fixed, small set reused across
    every request, so this call (cv2.cvtColor per pixel) was ~54% of a
    /recommendations request's total time before caching — repeat lookups
    now hit the cache instead of re-invoking OpenCV.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    bgr = np.array([[[b, g, r]]], dtype=np.uint8)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2Lab)[0][0]

    return float(lab[0]), float(lab[1]), float(lab[2])


def delta_e(lab1: tuple, lab2: tuple) -> float:
    """Euclidean distance in LAB space (CIE76 Delta E)."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def match_percent(delta: float, max_delta: float = 16.0, floor: int = 25) -> int:
    """
    Map Delta E distance to a 0-100 match score.

    Tuned so (CIE76 delta-E: ~2-10 is perceptible at a glance, 10-20 is a
    clearly noticeable difference) a merely "perceptible at a glance"
    difference already reads as a mediocre match, not a great one:
      delta ~0  → ~100%  (identical colour)
      delta ~2  → ~91%   (not perceptible without close inspection)
      delta ~5  → ~77%   (perceptible at a glance)
      delta ~10 → ~53%   (clearly noticeable, borderline reject)
      delta ~16 → floor  (visibly different colour, never shows 0%)
    """
    raw = 100 - (delta / max_delta) * (100 - floor)
    return max(floor, min(100, round(raw)))


def best_shade_match(
    target_hexes: str | list[str],
    shade_hexes: list[str],
    max_delta: float = 16.0,
) -> tuple[int, int]:
    """
    Given one or more target colours and a list of product shade hexes,
    return (index of best shade, match percent) for the shade closest to
    ANY of the targets.

    For foundation, target_hexes is just the user's base skin hex — it
    should closely replicate skin colour, so the default (tight) max_delta
    applies. For categories like blush, where the "right" colour is a
    personalised palette rather than skin colour itself (and real pigments
    sit much further from any single target by design), pass the profile's
    palette (e.g. blush_shades) as target_hexes and a looser max_delta.
    """
    if isinstance(target_hexes, str):
        target_hexes = [target_hexes]
    target_labs = [hex_to_lab(h) for h in target_hexes]
    shade_labs = [hex_to_lab(h) for h in shade_hexes]
    distances = [
        min(delta_e(tl, sl) for tl in target_labs)
        for sl in shade_labs
    ]
    best_idx = min(range(len(distances)), key=lambda i: distances[i])
    return best_idx, match_percent(distances[best_idx], max_delta=max_delta)