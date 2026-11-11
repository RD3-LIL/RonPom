"""Tests for backtest.py. Offline, no network, no full-season data.

Run: python3 test_backtest.py

Covers:
  - margin sign: a bad opposing defense raises your expected
    points under the model-consistent formula, and lowers them
    under the rubric-literal formula (the sign flip)
  - raw-Net baseline differs from the solver margin when raw
    and adjusted Nets disagree
  - logistic fit recovers known coefficients on synthetic data
  - score() accuracy / Brier / log loss on a tiny case
  - home court direct estimate recovers a planted value
"""

import math
import random
import sys

sys.path.insert(0, ".")
from backtest import (  # noqa: E402
    estimate_home_court, fit_logistic, margin_model,
    margin_net, margin_rubric_literal, score, win_prob,
)


def _ratings(spec):
    """spec: team -> (adj_o, adj_d, adj_t, raw_o, raw_d)."""
    return {t: {"adj_o": o, "adj_d": d, "adj_t": tp,
                "raw_o": ro, "raw_d": rd}
            for t, (o, d, tp, ro, rd) in spec.items()}


def _game(home, away, home_score, away_score):
    return {"home": home, "away": away,
            "home_score": home_score, "away_score": away_score}


def test_margin_defense_sign():
    # A has a terrible defense (AdjD 115). At home, H should
    # score more against them, so the model margin rises when
    # A's defense gets worse. The rubric-literal formula does
    # the opposite, which is the sign error.
    base = _ratings({"H": (110, 100, 68, 110, 100),
                     "A": (105, 115, 68, 105, 115)})
    good_d = _ratings({"H": (110, 100, 68, 110, 100),
                       "A": (105, 95, 68, 105, 95)})
    g = _game("H", "A", 80, 70)
    m_bad = margin_model(base, 107.0, 68.0, g, 0.0)
    m_good = margin_model(good_d, 107.0, 68.0, g, 0.0)
    assert m_bad > m_good, (m_bad, m_good)
    r_bad = margin_rubric_literal(base, 107.0, 68.0, g, 0.0)
    r_good = margin_rubric_literal(good_d, 107.0, 68.0, g, 0.0)
    assert r_bad < r_good, (r_bad, r_good)


def test_raw_net_differs_from_solver():
    # H is better on adjusted Net (+15 vs 0) but worse on raw
    # Net (0 vs +10). The two predictors must disagree in sign.
    ratings = _ratings({"H": (115, 100, 68, 105, 105),
                        "A": (105, 105, 68, 110, 100)})
    g = _game("H", "A", 80, 70)
    assert margin_model(ratings, 107.0, 68.0, g, 0.0) > 0
    assert margin_net(ratings, 107.0, 68.0, g, 0.0) < 0


def test_logistic_recovers_known_coefficients():
    rng = random.Random(7)
    margins = [rng.uniform(-15, 15) for _ in range(2000)]
    outcomes = [1 if rng.random() < win_prob(m, 0.0, 0.25) else 0
                for m in margins]
    a, b = fit_logistic(margins, outcomes)
    assert abs(a) < 0.15, a
    assert abs(b - 0.25) < 0.05, b


def test_score_tiny_case():
    s = score([0.9, 0.1], [1, 0])
    assert s["accuracy"] == 1.0
    assert abs(s["brier"] - 0.01) < 1e-9
    assert abs(s["logloss"] - (-math.log(0.9))) < 1e-9


def test_home_court_estimate_recovers_planted_value():
    # Both teams exactly league average, tempo 100, so the
    # model margin at hc=0 is 0 and the actual margin is the
    # home court effect, 3 points per 100 possessions.
    ratings = _ratings({"H": (107, 107, 100, 107, 107),
                        "A": (107, 107, 100, 107, 107)})
    games = [_game("H", "A", 73, 70),
             _game("A", "H", 74, 71)]
    hc = estimate_home_court(ratings, 107.0, 100.0, games)
    assert abs(hc - 3.0) < 1e-9, hc


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            try:
                fn()
                print(name, "passed")
            except AssertionError as e:
                failed += 1
                print(name, "FAILED:", e)
    if failed:
        print(f"{failed} test(s) failed")
        sys.exit(1)
    print("all backtest tests passed")
