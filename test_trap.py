"""Tests for trap.py. No network: all fixtures are synthetic.

Run as: python3 test_trap.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from trap import build_history, flags_for_game, rank_map  # noqa: E402


def _ratings():
    return {
        "Alpha Aces": {"net": 30.0},
        "Beta Bears": {"net": 10.0},
        "Gamma Goats": {"net": 5.0},
        "Delta Dogs": {"net": -5.0},
    }


def _played(date_str, home, away, hs, aws, neutral=False):
    return {"date": date_str, "event_id": date_str + home[:2],
            "home": home, "away": away, "home_score": hs,
            "away_score": aws, "neutral_site": neutral}


def test_no_trap_without_market_gap():
    ranks = rank_map(_ratings())
    hist = build_history([], ranks)
    game = {"home": "Alpha Aces", "away": "Beta Bears",
            "date": "20261112", "neutral_site": False}
    r = flags_for_game(game, 10.0, None, ranks, hist)
    assert r["favorite"] == "Alpha Aces"
    assert "MARKET_GAP" not in r["flags"]
    assert r["trap"] is False


def test_trap_needs_gap_plus_two_more():
    ranks = rank_map(_ratings())
    # Alpha is rank 1 (top 25), won last game by 25, played
    # 3 games in last 7 days, at Beta (road favorite).
    hist_games = [
        _played("20261105", "Alpha Aces", "Delta Dogs", 90, 60),
        _played("20261107", "Gamma Goats", "Alpha Aces", 70, 80),
        _played("20261110", "Alpha Aces", "Delta Dogs", 95, 70),
    ]
    hist = build_history(hist_games, ranks)
    # Beta has not played recently, so short rest also fires:
    # Alpha last played Nov 10, game Nov 12 is 2 days rest,
    # so SHORT_REST does not fire. TOP25 + BIG_WIN + BUSY +
    # ROAD_FAV + MARKET_GAP should still trap.
    game = {"home": "Beta Bears", "away": "Alpha Aces",
            "date": "20261112", "neutral_site": False}
    # Model says Alpha by 6 (margin -6, away favorite).
    # Market says home line +12, so market fav margin is 12.
    r = flags_for_game(game, -6.0, 12.0, ranks, hist)
    assert "TOP25" in r["flags"], r
    assert "BIG_WIN" in r["flags"], r
    assert "BUSY" in r["flags"], r
    assert "ROAD_FAV" in r["flags"], r
    assert "MARKET_GAP" in r["flags"], r
    assert r["trap"] is True, r
    assert r["score"] >= 3


def test_gap_alone_is_not_a_trap():
    ranks = rank_map(_ratings())
    hist = build_history([], ranks)
    game = {"home": "Alpha Aces", "away": "Beta Bears",
            "date": "20261112", "neutral_site": False}
    # Home favorite, model 6, market 11, gap 5, but no other flag
    # except TOP25 (rank 1). That is 2 flags, below the bar.
    r = flags_for_game(game, 6.0, -11.0, ranks, hist)
    assert r["flags"] == ["TOP25", "MARKET_GAP"], r
    assert r["trap"] is False


def test_no_clear_favorite_is_no_trap():
    ranks = rank_map(_ratings())
    hist = build_history([], ranks)
    game = {"home": "Alpha Aces", "away": "Beta Bears",
            "date": "20261112", "neutral_site": False}
    r = flags_for_game(game, 1.0, -11.0, ranks, hist)
    assert r["favorite"] is None
    assert r["trap"] is False


def test_history_uses_only_prior_games():
    ranks = rank_map(_ratings())
    # A big win AFTER the game date must not count.
    hist_games = [
        _played("20261113", "Alpha Aces", "Delta Dogs", 100, 60),
    ]
    hist = build_history(hist_games, ranks)
    game = {"home": "Alpha Aces", "away": "Beta Bears",
            "date": "20261112", "neutral_site": False}
    r = flags_for_game(game, 6.0, -11.0, ranks, hist)
    assert "BIG_WIN" not in r["flags"], r
    assert "BUSY" not in r["flags"], r


def test_short_rest_flag():
    ranks = rank_map(_ratings())
    hist_games = [
        _played("20261111", "Alpha Aces", "Delta Dogs", 80, 70),
        _played("20261108", "Beta Bears", "Delta Dogs", 70, 60),
    ]
    hist = build_history(hist_games, ranks)
    game = {"home": "Alpha Aces", "away": "Beta Bears",
            "date": "20261112", "neutral_site": False}
    r = flags_for_game(game, 6.0, -6.0, ranks, hist)
    # Alpha rest 1 day, Beta rest 4 days, gap 3. TOP25 also fires.
    assert "SHORT_REST" in r["flags"], r


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_")]
    for t in tests:
        t()
        print(f"{t.__name__} passed")
    print("all trap tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
