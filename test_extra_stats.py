"""Tests for extra_stats.py. Synthetic ratings and games only.

Run as: python3 test_extra_stats.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extra_stats import compute_extra, pythagorean_wpct  # noqa: E402


def _ratings():
    return {
        "A": {"adj_o": 110.0, "adj_d": 100.0, "net": 10.0},
        "B": {"adj_o": 105.0, "adj_d": 105.0, "net": 0.0},
        "C": {"adj_o": 100.0, "adj_d": 110.0, "net": -10.0},
    }


def _game(home, away, home_score, away_score, conf=False):
    return {"home": home, "away": away,
            "home_score": home_score, "away_score": away_score,
            "home_conf_id": 1, "away_conf_id": 2,
            "conference_game": conf}


def test_pythagorean_even_teams_expect_half():
    assert abs(pythagorean_wpct(110.0, 110.0) - 0.5) < 1e-9


def test_pythagorean_strong_offense_expects_more():
    exp = pythagorean_wpct(120.0, 100.0)
    assert 0.80 < exp < 0.90
    # Same ratio the other way round mirrors it.
    assert abs(pythagorean_wpct(100.0, 120.0) - (1 - exp)) < 1e-9


def test_luck_is_actual_minus_expected():
    # A is even with B on efficiency (110 vs 100 is not even;
    # use B vs C instead). B (105/105) expects 0.500. B goes
    # 2-0 against C, so Luck is +0.500.
    games = [_game("B", "C", 70, 60), _game("C", "B", 60, 70)]
    extra = compute_extra(_ratings(), games)
    assert abs(extra["B"]["exp_wpct"] - 0.5) < 1e-9
    assert abs(extra["B"]["luck"] - 0.5) < 1e-9
    # C lost both, expected 0.165 (100 vs 110), so negative luck.
    assert extra["C"]["luck"] < 0


def test_sos_averages_opponent_net():
    # A plays B (Net 0) and C (Net -10): SOS -5.
    games = [_game("A", "B", 70, 60), _game("A", "C", 70, 60)]
    extra = compute_extra(_ratings(), games)
    assert abs(extra["A"]["sos"] - (-5.0)) < 1e-9
    # B played A twice (Net +10): SOS +10.
    games = [_game("B", "A", 70, 60), _game("A", "B", 60, 70)]
    extra = compute_extra(_ratings(), games)
    assert abs(extra["B"]["sos"] - 10.0) < 1e-9


def test_ncsos_uses_non_conference_only():
    # A plays B in a conference game (Net 0) and C in a
    # non-conference game (Net -10): SOS -5, NCSOS -10.
    games = [_game("A", "B", 70, 60, conf=True),
             _game("A", "C", 70, 60, conf=False)]
    extra = compute_extra(_ratings(), games)
    assert abs(extra["A"]["sos"] - (-5.0)) < 1e-9
    assert abs(extra["A"]["ncsos"] - (-10.0)) < 1e-9
    # A team with only conference games gets NCSOS None.
    games = [_game("A", "B", 70, 60, conf=True)]
    extra = compute_extra(_ratings(), games)
    assert extra["A"]["ncsos"] is None


def test_non_d1_games_ignored():
    # A game with a missing conference id is non-D1 and skipped.
    games = [_game("A", "B", 70, 60)]
    games[0]["home_conf_id"] = None
    extra = compute_extra(_ratings(), games)
    assert extra["A"]["sos"] == 0.0  # no D1 games: mean Net is 0.0
    assert extra["A"]["luck"] == 0.0 - extra["A"]["exp_wpct"]


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_")]
    for t in tests:
        t()
        print(f"{t.__name__} passed")
    print("all extra stats tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
