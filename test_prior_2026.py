"""Tests for build_prior_2026.py's adopted no-shrink prior
(build_prior_noshrink, base weight 600).

Rewritten Nov 20, 2026: the old file tested the abandoned
build_transfer_prior and asserted base weight 300, so it
failed against the adopted builder. The transfer-blended
builder is still in build_prior_2026.py for reference, but
nothing live calls it and nothing here tests it.

Synthetic profiles only, except the last test, which loads
the real 2025-26 ratings and profiles and checks the two
headline prior values reproduce. Run as:
    python3 test_prior_2026.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_prior_2026 import (  # noqa: E402
    build_prior_noshrink, load_last_ratings, load_profiles)

LEAGUE_O = 109.3
LEAGUE_T = 68.2
BASE = 600.0


def _ratings():
    return {
        "A": {"adj_o": 120.0, "adj_d": 100.0, "adj_t": 70.0},
        "B": {"adj_o": 115.0, "adj_d": 105.0, "adj_t": 66.0},
    }


def _profile(aid, team, mins):
    return {"athlete_id": aid, "team": team,
            "totals": {"min": mins}}


def test_returning_transfer_and_new_shares():
    # Team A this season: 100 min returning (was on A), 100 min
    # transfer (was on B), 100 min new (no last-season profile).
    last = [_profile(1, "A", 500), _profile(2, "B", 500)]
    this = [_profile(1, "A", 100), _profile(2, "A", 100),
            _profile(3, "A", 100)]
    prior = build_prior_noshrink(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["A"]
    assert abs(p["returning_share"] - 1 / 3) < 1e-4
    assert abs(p["transfer_share"] - 1 / 3) < 1e-4
    assert p["has_prior"] is True
    info = 2 / 3
    assert abs(p["prior_weight"] - BASE * (0.25 + 0.75 * info)) < 1e-9


def test_prior_value_is_own_team_not_source_teams():
    # The point of the no-shrink prior: a transfer from B does
    # not drag A's prior toward B's rating. A's value is its
    # own last-season rating, regressed 0.85 toward league.
    last = [_profile(1, "A", 500), _profile(2, "B", 500)]
    this = [_profile(1, "A", 100), _profile(2, "A", 100),
            _profile(3, "A", 100)]
    prior = build_prior_noshrink(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["A"]
    assert abs(p["prior_o"] - (LEAGUE_O + 0.85 * (120.0 - LEAGUE_O))) < 1e-9
    assert abs(p["prior_d"] - (LEAGUE_O + 0.85 * (100.0 - LEAGUE_O))) < 1e-9
    assert abs(p["prior_t"] - (LEAGUE_T + 0.70 * (70.0 - LEAGUE_T))) < 1e-9


def test_all_transfer_team_keeps_own_prior():
    # LSU-like: no returners, 64% of minutes from transfers.
    # Value is still the team's own last-season rating; only
    # the weight scales with the informed share.
    last = [_profile(1, "B", 500), _profile(2, "B", 500)]
    this = [_profile(1, "A", 64), _profile(2, "A", 36),
            _profile(3, "A", 36)]
    prior = build_prior_noshrink(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["A"]
    assert p["returning_share"] == 0.0
    assert abs(p["transfer_share"] - 100 / 136) < 1e-4
    assert p["has_prior"] is True
    assert abs(p["prior_o"] - (LEAGUE_O + 0.85 * (120.0 - LEAGUE_O))) < 1e-9
    info = 100 / 136
    assert abs(p["prior_weight"] - BASE * (0.25 + 0.75 * info)) < 1e-9


def test_all_new_roster_keeps_own_value_at_minimum_weight():
    # Every minute is a new player (no last-season profile),
    # but the team itself was rated last season: the value
    # stays the own-team rating, the weight drops to the
    # 0.25 floor. Info 0 does not zero the value.
    last = [_profile(9, "B", 500)]
    this = [_profile(1, "A", 100), _profile(2, "A", 100)]
    prior = build_prior_noshrink(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["A"]
    assert p["returning_share"] == 0.0
    assert p["transfer_share"] == 0.0
    assert p["has_prior"] is True
    assert abs(p["prior_o"] - (LEAGUE_O + 0.85 * (120.0 - LEAGUE_O))) < 1e-9
    assert abs(p["prior_weight"] - BASE * 0.25) < 1e-9


def test_team_with_no_last_season_rating_is_league_average():
    last = [_profile(1, "B", 500)]
    this = [_profile(2, "A", 100)]
    ratings = {"B": {"adj_o": 115.0, "adj_d": 105.0, "adj_t": 66.0}}
    prior = build_prior_noshrink(ratings, last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["A"]
    assert p["has_prior"] is False
    assert p["prior_o"] == LEAGUE_O
    assert p["prior_d"] == LEAGUE_O
    assert p["prior_t"] == LEAGUE_T
    assert abs(p["prior_weight"] - BASE * 0.25) < 1e-9


def test_team_with_no_current_roster_is_league_average():
    last = [_profile(1, "B", 500)]
    this = [_profile(2, "A", 100)]
    prior = build_prior_noshrink(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["B"]
    assert p["has_prior"] is False
    assert p["prior_o"] == LEAGUE_O
    assert p["prior_weight"] == BASE * 0.5


def test_value_shrink_fades_deviation_with_info():
    # value_shrink=True multiplies the deviation by
    # 0.25 + 0.75 * info, mirroring the weight factor. At
    # info 2/3 the deviation keeps 0.75 of itself on top of
    # the 0.85 regression; at info 1.0 it is unchanged.
    last = [_profile(1, "A", 500), _profile(2, "B", 500)]
    this = [_profile(1, "A", 100), _profile(2, "A", 100),
            _profile(3, "A", 100)]
    prior = build_prior_noshrink(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T,
                                 value_shrink=True)
    p = prior["A"]
    info = 2 / 3
    shrink = 0.25 + 0.75 * info
    assert abs(p["prior_o"]
               - (LEAGUE_O + 0.85 * shrink * (120.0 - LEAGUE_O))) < 1e-9
    assert abs(p["prior_d"]
               - (LEAGUE_O + 0.85 * shrink * (100.0 - LEAGUE_O))) < 1e-9
    assert abs(p["prior_weight"] - BASE * (0.25 + 0.75 * info)) < 1e-9
    # Full info: shrink is 1.0, identical to no-shrink.
    this_full = [_profile(1, "A", 100), _profile(2, "A", 100)]
    last_full = [_profile(1, "A", 500), _profile(2, "A", 500)]
    p_full = build_prior_noshrink(_ratings(), last_full, this_full,
                                  league_o=LEAGUE_O, league_t=LEAGUE_T,
                                  value_shrink=True)["A"]
    p_noshrink = build_prior_noshrink(
        _ratings(), last_full, this_full,
        league_o=LEAGUE_O, league_t=LEAGUE_T)["A"]
    assert abs(p_full["prior_o"] - p_noshrink["prior_o"]) < 1e-9


def test_value_shrink_off_by_default():
    last = [_profile(1, "A", 500), _profile(2, "B", 500)]
    this = [_profile(1, "A", 100), _profile(2, "A", 100),
            _profile(3, "A", 100)]
    p = build_prior_noshrink(_ratings(), last, this,
                             league_o=LEAGUE_O, league_t=LEAGUE_T)["A"]
    assert abs(p["prior_o"] - (LEAGUE_O + 0.85 * (120.0 - LEAGUE_O))) < 1e-9


def test_live_illinois_and_duke_priors_reproduce():
    # Regression guard on the real builder inputs: the live
    # prior file's headline values must come out of
    # build_prior_noshrink unchanged.
    last = load_last_ratings("2025-26")
    prior = build_prior_noshrink(
        last, load_profiles("2025-26"), load_profiles("2026-27"))
    live = json.loads(
        (Path(__file__).parent / "data" / "prior_2026_27.json")
        .read_text())
    for team in ("Illinois Fighting Illini", "Duke Blue Devils"):
        assert abs(prior[team]["prior_o"] - live[team]["prior_o"]) < 1e-9
        assert abs(prior[team]["prior_d"] - live[team]["prior_d"]) < 1e-9
    ill = prior["Illinois Fighting Illini"]
    duke = prior["Duke Blue Devils"]
    assert abs((ill["prior_o"] - ill["prior_d"]) - 26.52) < 0.01
    assert abs((duke["prior_o"] - duke["prior_d"]) - 30.77) < 0.01


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_")]
    for t in tests:
        t()
        print(f"{t.__name__} passed")
    print("all no-shrink prior tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
