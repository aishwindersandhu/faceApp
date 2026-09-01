import pytest

from app.recommendations.matcher import best_shade_match, delta_e, hex_to_lab, match_percent


def test_hex_to_lab_black_and_white_are_extremes():
    black_L, _, _ = hex_to_lab("#000000")
    white_L, _, _ = hex_to_lab("#FFFFFF")
    assert black_L < white_L
    assert black_L == pytest.approx(0, abs=1)
    assert white_L == pytest.approx(255, abs=1)


def test_hex_to_lab_accepts_leading_hash_or_not():
    assert hex_to_lab("#BD8453") == hex_to_lab("BD8453")


def test_delta_e_identical_colours_is_zero():
    lab = hex_to_lab("#BD8453")
    assert delta_e(lab, lab) == 0


def test_delta_e_is_symmetric():
    a = hex_to_lab("#BD8453")
    b = hex_to_lab("#1A1A1A")
    assert delta_e(a, b) == pytest.approx(delta_e(b, a))


@pytest.mark.parametrize(
    "delta,expected",
    [
        (0, 100),
        (16, 25),
        (100, 25),  # never drops below floor even past max_delta
    ],
)
def test_match_percent_bounds(delta, expected):
    assert match_percent(delta) == expected


def test_match_percent_is_monotonically_decreasing():
    scores = [match_percent(d) for d in range(0, 40, 5)]
    assert scores == sorted(scores, reverse=True)


def test_match_percent_respects_custom_floor():
    assert match_percent(1000, max_delta=35.0, floor=10) == 10


def test_best_shade_match_picks_closest_shade():
    # Skin colour matches the second shade exactly.
    idx, score = best_shade_match("#BD8453", ["#1A1A1A", "#BD8453", "#FFFFFF"])
    assert idx == 1
    assert score == 100


def test_best_shade_match_returns_percent_for_closest_when_no_exact_match():
    idx, score = best_shade_match("#BD8453", ["#1A1A1A", "#FFFFFF"])
    assert idx in (0, 1)
    assert 0 <= score <= 100
