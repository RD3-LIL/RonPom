"""Extra solver cases: OT games, neutral-site games, unplayed
0-0 games, and a disconnected component with a real prior.

Owned by the solver track (Nov 20, 2026). Run as:
    python3 test_solver_cases.py

These live here, not in test_solver.py, so the solver test
runner there is untouched. Synthetic games only, no files.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from solver import (  # noqa: E402
    cap_game_margins_per_poss, solve)

STATS = {"fga": 60, "orb": 10, "tov": 10, "fta": 20}  # poss = 68.8


def _game(home, away, home_score, away_score, **extra):
    g = {"home": home, "away": away,
         "home_score": home_score, "away_score": away_score,
         "home_stats": dict(STATS), "away_stats": dict(STATS),
         "home_conf_id": 1, "away_conf_id": 2}
    g.update(extra)
    return g


def test_ot_game_solves_and_counts_its_possessions():
    # An OT game (periods 3) is a real game: it enters the
    # solve like any other, with its full boxscore
    # possessions. There is NO tempo normalization to
    # regulation possessions: the Nov 20, 2026 cap experiment
    # did not support margin caps, and OT normalization was
    # left out with it, so this test pins the current
    # behavior (OT possessions count as played) rather than
    # assuming a normalization exists.
    ot = _game("A", "B", 95, 90, overtime=True, periods=3)
    reg = _game("B", "A", 80, 70)
    teams, _, _, info = solve([ot, reg], prior_weight=0.0,
                              return_info=True)
    assert info["n_games"] == 2, info
    assert teams["A"]["games"] == 2
    assert teams["B"]["games"] == 2
    # OT stats are the same shape as regulation here, so both
    # teams show the same raw tempo; the point is the game is
    # in, not dropped, and nothing is finite-violating.
    for t in teams.values():
        assert math.isfinite(t["net"])
        assert t["poss"] > 0


def test_neutral_site_game_gets_no_home_court():
    # With home_court on, a neutral-site game must solve
    # exactly as if home_court were 0: the designated home
    # team gets no floor advantage. A non-neutral game with
    # the same scores must differ. (A hosts both games: a
    # balanced home/away pair would cancel the home-court
    # term and prove nothing.)
    neutral = [_game("A", "B", 80, 70, neutral_site=True),
               _game("A", "B", 75, 72, neutral_site=True)]
    plain = [_game("A", "B", 80, 70),
             _game("A", "B", 75, 72)]
    n_hc, _, _ = solve(neutral, home_court=3.0, prior_weight=0.0)
    n_no, _, _ = solve(neutral, home_court=0.0, prior_weight=0.0)
    for t in n_hc:
        assert abs(n_hc[t]["net"] - n_no[t]["net"]) < 1e-9, t
    p_hc, _, _ = solve(plain, home_court=3.0, prior_weight=0.0)
    p_no, _, _ = solve(plain, home_court=0.0, prior_weight=0.0)
    diff = max(abs(p_hc[t]["net"] - p_no[t]["net"]) for t in p_hc)
    assert diff > 0.1, diff


def test_unplayed_zero_zero_game_is_skipped():
    # A scheduled/postponed 0-0 game carries no result. It
    # must not enter the solve even if its stats block is
    # populated (a stale-stats glitch must not inject
    # zero-efficiency observations), and it must be counted
    # separately from the zero-possession skip.
    games = [_game("A", "B", 80, 70),
             _game("B", "A", 75, 72),
             _game("A", "C", 0, 0)]
    teams, _, _, info = solve(games, prior_weight=0.0,
                              return_info=True)
    assert set(teams) == {"A", "B"}, teams
    assert info["n_games"] == 2, info
    assert info["n_skipped_unplayed"] == 1, info
    assert info["n_skipped_zero_poss"] == 0, info
    for t in teams.values():
        assert math.isfinite(t["net"])


def test_disconnected_component_with_real_prior_stays_anchored():
    # Two teams play only each other: without a prior the
    # component is unanchored (prior_weight 0 recenters, but
    # the pair can still sit far from league average on two
    # games). With a real prior on both teams, the solve
    # stays near the prior instead of chasing the two scores.
    games = [_game("A", "B", 110, 60), _game("A", "B", 100, 55)]
    prior = {
        "A": {"prior_o": 112.0, "prior_d": 98.0, "prior_t": 69.0,
              "prior_weight": 600.0, "has_prior": True},
        "B": {"prior_o": 104.0, "prior_d": 104.0, "prior_t": 69.0,
              "prior_weight": 600.0, "has_prior": True},
    }
    teams, _, _, info = solve(games, prior=prior, return_info=True)
    assert info["converged"], info
    # A won by 50 and 45, so A is above its prior and B below
    # it, but neither runs away: both stay within 15 points
    # per 100 of their prior Net (A prior Net +14, B 0).
    assert abs(teams["A"]["net"] - 14.0) < 15, teams["A"]
    assert abs(teams["B"]["net"] - 0.0) < 15, teams["B"]
    # And the prior actually moved the result: without it the
    # same two blowouts give a much wider spread.
    bare, _, _ = solve(games, prior_weight=0.0)
    assert (bare["A"]["net"] - bare["B"]["net"]
            > teams["A"]["net"] - teams["B"]["net"])


def test_disconnected_component_without_prior_does_not_crash():
    games = [_game("A", "B", 110, 60), _game("A", "B", 100, 55)]
    teams, _, _, info = solve(games, prior_weight=0.0,
                              return_info=True)
    assert info["converged"], info
    for t in teams.values():
        assert math.isfinite(t["net"])


def test_per_poss_cap_scales_with_pace():
    # Same 30-point margin: in a slow game (40 poss) it is
    # 0.75 pts/poss and gets capped at 0.30, in a fast game
    # (100 poss) it is 0.30 pts/poss and is left alone.
    slow_stats = {"fga": 36, "orb": 6, "tov": 6, "fta": 10}   # 40.4 poss
    fast_stats = {"fga": 88, "orb": 14, "tov": 14, "fta": 28}  # ~100 poss
    slow = _game("A", "B", 80, 50)
    slow["home_stats"] = dict(slow_stats)
    slow["away_stats"] = dict(slow_stats)
    fast = _game("A", "B", 110, 80)
    fast["home_stats"] = dict(fast_stats)
    fast["away_stats"] = dict(fast_stats)
    capped = cap_game_margins_per_poss([slow, fast], 0.30)
    assert capped[0]["home_score"] < 80  # slow game capped
    assert capped[0]["home_score"] - capped[0]["away_score"] < 30
    assert capped[1]["home_score"] == 110  # fast game untouched
    assert capped[1]["away_score"] == 80
    # Total points and winner unchanged on the capped game.
    assert capped[0]["home_score"] + capped[0]["away_score"] == 130
    assert capped[0]["home_score"] > capped[0]["away_score"]


def test_per_poss_cap_rejects_non_positive():
    try:
        cap_game_margins_per_poss([], 0)
    except ValueError:
        pass
    else:
        raise AssertionError("per-poss cap 0 must raise")


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            failed += 1
            print(f"{t.__name__} FAILED: {type(e).__name__} {e}")
        else:
            print(f"{t.__name__} passed")
    if failed:
        print(f"{failed} test(s) failed")
        return 1
    print("all solver case tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
