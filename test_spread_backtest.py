"""Tests for spread_backtest.py. No network, synthetic games only.

Run as: python3 test_spread_backtest.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from spread_backtest import (  # noqa: E402
    _bucket, _cover, fit_margin_scale, fit_margin_scale_slope_only,
    summarize)


def test_margin_scales():
    # Perfect calibration: actual == predicted.
    pairs = [(10.0, 10.0), (-5.0, -5.0), (3.0, 3.0)]
    a, b = fit_margin_scale(pairs)
    assert abs(a) < 1e-9 and abs(b - 1.0) < 1e-9
    _, b2 = fit_margin_scale_slope_only(pairs)
    assert abs(b2 - 1.0) < 1e-9
    # Compressed predictions: actual is 2x predicted.
    pairs = [(5.0, 10.0), (-5.0, -10.0), (2.0, 4.0)]
    _, b3 = fit_margin_scale_slope_only(pairs)
    assert abs(b3 - 2.0) < 1e-9


def _row(predicted, implied, actual, neutral=False):
    return {"date": "20250101", "event_id": 1, "home": "A",
            "away": "B", "neutral_site": neutral,
            "predicted": predicted, "implied": implied,
            "actual": actual, "edge": predicted - implied}


def test_mae_and_bias():
    rows = [_row(10.0, 7.0, 8.0), _row(-5.0, -3.0, -6.0)]
    s = summarize(rows)
    assert s["n"] == 2
    # Model errors: +2, +1 -> MAE 1.5, bias +1.5.
    assert abs(s["model_mae"] - 1.5) < 1e-9
    assert abs(s["model_bias"] - 1.5) < 1e-9
    # Market errors: -1, +3 -> MAE 2.0, bias +1.0.
    assert abs(s["market_mae"] - 2.0) < 1e-9
    assert abs(s["market_bias"] - 1.0) < 1e-9
    # Model vs market gaps: +3, -2 -> MAE 2.5.
    assert abs(s["model_vs_market_mae"] - 2.5) < 1e-9


def test_cover_counts_model_side_wins():
    # Edge +3, actual lands above the market line: model wins.
    # Edge -4, actual lands below the market line: model wins.
    # Edge +5, actual lands below the market line: model loses.
    rows = [_row(10.0, 7.0, 8.0),
            _row(-7.0, -3.0, -5.0),
            _row(12.0, 7.0, 5.0)]
    c = _cover(rows, 2.0)
    assert c["n"] == 3
    assert abs(c["rate"] - 2 / 3) < 1e-9
    # At a 5-point threshold only the third row qualifies, a loss.
    c5 = _cover(rows, 5.0)
    assert c5["n"] == 1
    assert c5["rate"] == 0.0


def test_cover_ignores_pushes():
    # Actual exactly on the market line is neither a win nor a
    # loss for the model; it counts in n but not in wins.
    rows = [_row(10.0, 7.0, 7.0)]
    c = _cover(rows, 2.0)
    assert c["n"] == 1
    assert c["rate"] == 0.0


def test_buckets_split_by_market_line():
    rows = [_row(10.0, 25.0, 20.0), _row(0.0, -3.0, -1.0),
            _row(5.0, 3.0, 4.0, neutral=True)]
    s = summarize(rows)
    assert s["buckets"]["home by 21+"]["n"] == 1
    assert s["buckets"]["away by 0-7"]["n"] == 1
    assert s["buckets"]["home by 0-7"]["n"] == 1
    assert s["neutral"][True]["n"] == 1
    assert s["neutral"][False]["n"] == 2


def test_bucket_boundaries():
    assert _bucket(21.0) == "home by 21+"
    assert _bucket(20.9) == "home by 14-21"
    assert _bucket(0.0) == "home by 0-7"
    assert _bucket(-0.5) == "away by 0-7"
    assert _bucket(-14.0) == "away by 7-14"
    assert _bucket(-14.1) == "away by 14+"


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_")]
    for t in tests:
        t()
        print(f"{t.__name__} passed")
    print("all spread backtest tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
