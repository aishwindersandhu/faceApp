"""
Colour matching logic.

Uses the same LAB colour space as image_processing.py — keeps
the matching consistent with how the palette was derived in the
first place.

We reuse OpenCV here so there's no new dependency to install.
"""

from __future__ import annotations

import math
import cv2
import numpy as np


def hex_to_lab(hex_color: str) -> tuple[float, float, float]:
    """
    Convert a hex colour string to OpenCV LAB values.
    Returns (L, a, b) as floats in OpenCV scale (L: 0-255, a/b: 0-255).
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    bgr = np.array([[[b, g, r]]], dtype=np.uint8)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2Lab)[0][0]

    return float(lab[0]), float(lab[1]), float(lab[2])


def delta_e(lab1: tuple, lab2: tuple) -> float:
    """Euclidean distance in LAB space (CIE76 Delta E)."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def match_percent(delta: float, max_delta: float = 35.0, floor: int = 45) -> int:
    """
    Map Delta E distance to a 0-100 match score.

    Tuned so (CIE76 delta-E: ~2-10 is perceptible at a glance, 10-20 is a
    clearly noticeable difference):
      delta ~0  → ~100%  (identical colour)
      delta ~10 → ~85%   (close match)
      delta ~20 → ~69%   (noticeably different)
      delta ~35 → floor  (visibly different colour, never shows 0%)
    """
    raw = 100 - (delta / max_delta) * (100 - floor)
    return max(floor, min(100, round(raw)))


def best_shade_match(
    skin_hex: str,
    shade_hexes: list[str],
) -> tuple[int, int]:
    """
    Given the user's base skin hex and a list of product shade hexes,
    return (index of best shade, match percent).
    """
    skin_lab = hex_to_lab(skin_hex)
    distances = [delta_e(skin_lab, hex_to_lab(h)) for h in shade_hexes]
    best_idx = min(range(len(distances)), key=lambda i: distances[i])
    return best_idx, match_percent(distances[best_idx])