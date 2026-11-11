"""Tests for build_prior_2026.py's transfer-aware prior.

Synthetic profiles only, no files. Run as:
    python3 test_prior_2026.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_prior_2026 import build_transfer_prior  # noqa: E402

LEAGUE_O = 109.3
LEAGUE_T = 68.2


def _ratings():
    return {
        "A": {"adj_o": 120.0, "adj_d": 100.0, "adj_t": 70.0},
        "B": {"adj_o": 115.0, "adj_d": 105.0, "adj_t": 66.0},
    }


def _profile(aid, team, mins):
    return {"athlete_id": aid, "team": team,
            "totals": {"min": mins}}


def test_returning_transfer_and_new_blend():
    # Team A this season: 100 min returning (was on A), 100 min
    # transfer (was on B), 100 min new (no last-season profile).
    last = [_profile(1, "A", 500), _profile(2, "B", 500)]
    this = [_profile(1, "A", 100), _profile(2, "A", 100),
            _profile(3, "A", 100)]
    prior = build_transfer_prior(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["A"]
    assert abs(p["returning_share"] - 1 / 3) < 1e-4
    assert abs(p["transfer_share"] - 1 / 3) < 1e-4
    assert p["has_prior"] is True
    info = 2 / 3
    blended_o = (100 * 120.0 + 100 * 115.0 + 100 * LEAGUE_O) / 300
    assert abs(p["prior_o"] - (LEAGUE_O + info * 0.85 * (blended_o - LEAGUE_O))) < 1e-9
    assert abs(p["prior_weight"] - 300 * (0.25 + 0.75 * info)) < 1e-9


def test_all_transfer_team_gets_old_teams_prior():
    # LSU-like: no returners, 64% of minutes from transfers.
    last = [_profile(1, "B", 500), _profile(2, "B", 500)]
    this = [_profile(1, "A", 64), _profile(2, "A", 36),
            _profile(3, "A", 36)]
    # Player 2 was on B last season, so he is a transfer too
    # (both 1 and 2 came from B); player 3 is new.
    prior = build_transfer_prior(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["A"]
    assert p["returning_share"] == 0.0
    assert abs(p["transfer_share"] - 100 / 136) < 1e-4
    assert p["has_prior"] is True
    # Blended AdjO is B's 115 for the transfer minutes, league
    # average for the new minutes.
    blended_o = (100 * 115.0 + 36 * LEAGUE_O) / 136
    info = 100 / 136
    assert abs(p["prior_o"] - (LEAGUE_O + info * 0.85 * (blended_o - LEAGUE_O))) < 1e-9


def test_team_with_no_prior_season_players_is_league_average():
    last = [_profile(1, "B", 500)]
    this = [_profile(2, "A", 100)]
    prior = build_transfer_prior(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["A"]
    assert p["has_prior"] is False
    assert p["prior_o"] == LEAGUE_O
    assert p["prior_d"] == LEAGUE_O
    assert p["prior_weight"] == 300 * (0.25 + 0.75 * 0)


def test_team_with_no_current_roster_is_league_average():
    last = [_profile(1, "B", 500)]
    this = [_profile(2, "A", 100)]
    prior = build_transfer_prior(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["B"]
    assert p["has_prior"] is False
    assert p["prior_o"] == LEAGUE_O
    assert p["prior_weight"] == 300 * 0.5


def test_unrated_transfer_source_is_league_average():
    # Transfer from a team with no last-season rating counts as
    # league average, not a crash.
    last = [_profile(1, "Z", 500)]
    this = [_profile(1, "A", 100)]
    prior = build_transfer_prior(_ratings(), last, this,
                                 league_o=LEAGUE_O, league_t=LEAGUE_T)
    p = prior["A"]
    assert p["has_prior"] is True
    assert p["prior_o"] == LEAGUE_O


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_")]
    for t in tests:
        t()
        print(f"{t.__name__} passed")
    print("all transfer prior tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
