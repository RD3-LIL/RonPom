"""Tests for score_predictions.py. No network, synthetic only.

Run as: python3 test_score_predictions.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score_predictions import score_row, summarize  # noqa: E402


def _pred(home="Alpha Aces", away="Beta Bears", margin=6.0,
          prob=0.7, market=-5.0, trap="False"):
    return {"date": "20261111", "tipoff": "", "home": home,
            "away": away, "home_short": "Alpha",
            "away_short": "Beta", "neutral_site": "False",
            "margin": str(margin), "spread": "Alpha -6.0",
            "home_win_prob": str(prob),
            "market_spread": "" if market is None else str(market),
            "edge": "" if market is None else str(margin + market),
            "trap": trap, "trap_score": "0", "trap_flags": "",
            "trap_favorite": home if margin > 0 else away}


def _game(hs=80, aws=70):
    return {"home_score": hs, "away_score": aws}


def test_score_row_win_and_cover():
    r = score_row(_pred(), "predictions_2026_11_11.csv",
                  "20261111", _game(80, 70))
    assert r["actual_home_margin"] == 10
    assert r["home_won"] == 1
    assert r["correct_pick"] == 1
    assert float(r["model_abs_err"]) == 4.0
    # Market implied 5, actual 10, edge +1, actual on model side.
    assert r["edge_cover"] == 1


def test_score_row_loss_and_brier():
    r = score_row(_pred(prob=0.7), "predictions_2026_11_11.csv",
                  "20261111", _game(60, 70))
    assert r["home_won"] == 0
    assert r["correct_pick"] == 0
    assert abs(float(r["brier"]) - 0.49) < 1e-6


def test_score_row_no_market_is_blank():
    r = score_row(_pred(market=None), "predictions_2026_11_11.csv",
                  "20261111", _game(80, 70))
    assert r["market_abs_err"] == ""
    assert r["edge_cover"] == ""


def test_score_row_trap_dog():
    p = _pred(margin=20.0, prob=0.95, market=-30.0, trap="True")
    p["trap_favorite"] = "Alpha Aces"
    r = score_row(p, "predictions_2026_11_12.csv",
                  "20261112", _game(80, 70))
    # Favorite won by 10, market wanted 30, dog covers, dog loses.
    assert r["trap_dog_covers"] == 1
    assert r["trap_dog_wins"] == 0


def test_summarize_counts():
    rows = [
        score_row(_pred(), "f.csv", "20261111", _game(80, 70)),
        score_row(_pred(), "f.csv", "20261111", _game(60, 70)),
    ]
    s = summarize(rows)
    assert s["n"] == 2
    assert s["accuracy"] == 0.5
    assert s["n_market"] == 2


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_")]
    for t in tests:
        t()
        print(f"{t.__name__} passed")
    print("all score_predictions tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
