"""Tests for solver v2 (solver.py) and prior.py. Offline, no network.

Run: python3 test_solver.py

Covers:
  - prototype data (data/games.json, 57 games, 84 teams): shape,
    finiteness, convergence, Illinois, and the v1 flaws v2 fixes
  - synthetic full season: 8 teams, round-robin home/away, known
    true efficiencies, check the solver recovers the ordering
  - prior.py: exact formula, missing data degrades to league average
  - home court parameter, prior shrinkage, and the no-prior case
"""

import math
import random
import sys

from ratings import compute as v1_compute, load_games
from solver import solve, DEFAULT_PRIOR_WEIGHT
from prior import (
    build_prior, build_prior_from_rosters, compute_returning_share,
    league_average_prior,
)

STATS = {"fga": 60, "orb": 10, "tov": 10, "fta": 20}  # poss = 68.8


def _game(home, away, home_score, away_score, conf=False):
    g = {"home": home, "away": away,
         "home_score": home_score, "away_score": away_score,
         "home_stats": dict(STATS), "away_stats": dict(STATS)}
    if conf:
        g["home_conf_id"] = 1
        g["away_conf_id"] = 2
    return g


def _spearman(rank_a, rank_b):
    """Spearman rho from two dicts team -> rank. Stdlib only."""
    teams = list(rank_a)
    n = len(teams)
    d2 = sum((rank_a[t] - rank_b[t]) ** 2 for t in teams)
    return 1 - 6 * d2 / (n * (n * n - 1))


def _ranks(net):
    order = sorted(net, key=lambda t: net[t], reverse=True)
    return {t: i + 1 for i, t in enumerate(order)}


def _synthetic_season(seed=42):
    """8 teams, known true AdjO/AdjD, round-robin home/away.

    True Net ordering is A > B > C > D > E > F > G > H by
    construction. League average is 104.0 by design.
    Returns (games, true_o, true_d).
    """
    true_o = {"A": 118, "B": 114, "C": 110, "D": 106,
              "E": 102, "F": 98, "G": 94, "H": 90}
    true_d = {"A": 92, "B": 95, "C": 98, "D": 102,
              "E": 106, "F": 110, "G": 114, "H": 118}
    league = 104.0
    poss = 68.8
    rng = random.Random(seed)
    games = []
    teams = sorted(true_o)
    for i, home in enumerate(teams):
        for away in teams:
            if home == away:
                continue
            eff_home = true_o[home] + true_d[away] - league + rng.gauss(0, 2.5)
            eff_away = true_o[away] + true_d[home] - league + rng.gauss(0, 2.5)
            games.append(_game(home, away,
                               max(30, round(eff_home * poss / 100)),
                               max(30, round(eff_away * poss / 100))))
    return games, true_o, true_d


def test_prototype_shape_and_finiteness():
    games = load_games()
    assert len(games) == 57, len(games)
    teams, lo, lt, info = solve(games, return_info=True)
    assert len(teams) == 84, len(teams)
    assert info["converged"], info
    assert info["iterations"] < 500, info
    assert info["max_change"] < 1e-6, info
    for name, t in teams.items():
        assert t["games"] >= 1
        for k in ("adj_o", "adj_d", "adj_t", "net", "raw_o", "raw_d"):
            assert math.isfinite(t[k]), (name, k, t[k])
        assert 70 < t["adj_o"] < 160, (name, t["adj_o"])
        assert 70 < t["adj_d"] < 160, (name, t["adj_d"])
        assert 60 < t["adj_t"] < 85, (name, t["adj_t"])
        assert abs(t["net"] - (t["adj_o"] - t["adj_d"])) < 1e-9
    assert abs(lo - 104.2) < 0.2, lo
    assert abs(lt - 72.4) < 0.2, lt


def test_prototype_gp_matches_v1():
    games = load_games()
    v1, _, _ = v1_compute(games)
    v2, _, _ = solve(games)
    assert set(v1) == set(v2)
    for name in v1:
        assert v1[name]["games"] == v2[name]["games"], name


def test_illinois_v2():
    games = load_games()
    teams, _, _, info = solve(games, return_info=True)
    ill = teams["Illinois Fighting Illini"]
    assert ill["games"] == 2
    assert ill["adj_o"] > 110, ill
    assert ill["adj_d"] < 100, ill
    assert ill["net"] > 10, ill
    ranked = sorted(teams, key=lambda t: teams[t]["net"], reverse=True)
    assert ranked.index("Illinois Fighting Illini") + 1 <= 5, ranked[:5]
    # Tempo: raw tempo 80.7, shrunk toward league 72.4, still fast.
    assert 73 < ill["adj_t"] < 78, ill


def test_v2_fixes_v1_chattanooga_and_ties():
    games = load_games()
    v1, _, _ = v1_compute(games)
    v2, _, _ = solve(games)
    # v1 ranks Chattanooga 1st with Net +25.9 even though it lost
    # its only game. v2 puts it near league average.
    assert v1["Chattanooga Mocs"]["net"] > 20, v1["Chattanooga Mocs"]
    assert abs(v2["Chattanooga Mocs"]["net"]) < 5, v2["Chattanooga Mocs"]
    # v1 ties 17 teams at exactly Net 0.0 (rounded). v2 has no
    # such tie block: almost no team sits exactly at zero.
    v1_zero = sum(1 for t in v1.values() if abs(round(t["net"], 1)) < 0.05)
    v2_zero = sum(1 for t in v2.values() if abs(t["net"]) < 0.05)
    assert v1_zero >= 10, v1_zero
    assert v2_zero < 5, v2_zero


def test_prior_shrinks_blowouts():
    games = load_games()
    narrow, _, _ = solve(games, prior_weight=1000.0)
    wide, _, _ = solve(games, prior_weight=100.0)
    narrow_range = max(t["adj_o"] for t in narrow.values()) - min(t["adj_o"] for t in narrow.values())
    wide_range = max(t["adj_o"] for t in wide.values()) - min(t["adj_o"] for t in wide.values())
    assert narrow_range < wide_range, (narrow_range, wide_range)
    assert narrow["Illinois Fighting Illini"]["net"] < wide["Illinois Fighting Illini"]["net"]


def test_no_prior_is_wilder():
    games = load_games()
    with_prior, _, _ = solve(games, prior_weight=300.0)
    without_prior, _, _ = solve(games, prior_weight=0.0)
    # Without any prior anchor, the sparse early-season solve
    # lets blowouts run further. The prior is what tames it.
    assert without_prior["Illinois Fighting Illini"]["net"] > with_prior["Illinois Fighting Illini"]["net"]
    for t in without_prior.values():
        assert math.isfinite(t["net"])


def test_home_court_parameter():
    games = load_games()
    base, _, _, info0 = solve(games, home_court=0.0, return_info=True)
    assert info0["home_court"] == 0.0
    with_hca, _, _, info1 = solve(games, home_court=3.0, return_info=True)
    assert info1["home_court"] == 3.0
    diff = max(abs(base[t]["net"] - with_hca[t]["net"]) for t in base)
    assert diff > 0.1, diff


def test_conf_fields_accepted_and_ignored():
    games = [_game("A", "B", 80, 70, conf=True),
             _game("B", "A", 75, 72, conf=True)]
    teams, _, _ = solve(games)
    assert set(teams) == {"A", "B"}
    for t in teams.values():
        assert math.isfinite(t["net"])


def test_single_game_component_does_not_explode():
    games = [_game("A", "B", 80, 60), _game("B", "A", 70, 75)]
    teams, _, _ = solve(games)
    assert teams["A"]["net"] > 0 > teams["B"]["net"]
    for t in teams.values():
        assert 80 < t["adj_o"] < 130, t
        assert 80 < t["adj_d"] < 130, t


def test_synthetic_recovery():
    games, true_o, true_d = _synthetic_season()
    assert len(games) == 56, len(games)
    teams, lo, lt, info = solve(games, return_info=True)
    assert info["converged"], info
    assert len(teams) == 8
    true_net = {t: true_o[t] - true_d[t] for t in true_o}
    solved_net = {t: teams[t]["net"] for t in teams}
    rho = _spearman(_ranks(true_net), _ranks(solved_net))
    assert rho >= 0.9, rho
    ranked = sorted(teams, key=lambda t: teams[t]["net"], reverse=True)
    assert ranked[0] == "A", ranked
    assert ranked[-1] == "H", ranked
    assert set(ranked[:3]) == {"A", "B", "C"}, ranked
    # Tempo is constant 68.8 in this synthetic set.
    for t in teams.values():
        assert abs(t["adj_t"] - 68.8) < 2.0, t["adj_t"]
    # Efficiencies recovered within about 5 points per 100.
    for name in true_o:
        assert abs(teams[name]["adj_o"] - true_o[name]) < 6, (name, teams[name]["adj_o"], true_o[name])
        assert abs(teams[name]["adj_d"] - true_d[name]) < 6, (name, teams[name]["adj_d"], true_d[name])


def test_synthetic_recovery_no_prior():
    # A connected full-season graph is identified even with the
    # prior weight at 0 (centering fixes the shift degeneracy).
    games, true_o, true_d = _synthetic_season()
    teams, _, _ = solve(games, prior_weight=0.0)
    true_net = {t: true_o[t] - true_d[t] for t in true_o}
    solved_net = {t: teams[t]["net"] for t in teams}
    rho = _spearman(_ranks(true_net), _ranks(solved_net))
    assert rho >= 0.9, rho


def test_prior_exact_formula():
    last = {"X": {"adj_o": 115.0, "adj_d": 95.0, "adj_t": 72.0}}
    # r = 1, regression 0.85, league 104 / 70:
    #   prior_o = 104 + 0.85 * 11 = 113.35
    #   prior_d = 104 + 0.85 * (-9) = 96.35
    #   prior_t = 70 + 0.70 * 2 = 71.4
    p = build_prior(last, {"X": 1.0}, league_o=104.0, league_t=70.0)
    assert abs(p["X"]["prior_o"] - 113.35) < 1e-9, p["X"]
    assert abs(p["X"]["prior_d"] - 96.35) < 1e-9, p["X"]
    assert abs(p["X"]["prior_t"] - 71.4) < 1e-9, p["X"]
    assert p["X"]["has_prior"] is True
    assert abs(p["X"]["prior_weight"] - 300.0) < 1e-9
    # r = 0: exactly league average, weight scaled to 0.25 * base.
    p0 = build_prior(last, {"X": 0.0}, league_o=104.0, league_t=70.0)
    assert p0["X"]["prior_o"] == 104.0
    assert p0["X"]["prior_d"] == 104.0
    assert p0["X"]["has_prior"] is False
    assert abs(p0["X"]["prior_weight"] - 75.0) < 1e-9
    # r = 0.5: half the signal survives.
    p5 = build_prior(last, {"X": 0.5}, league_o=104.0, league_t=70.0)
    assert abs(p5["X"]["prior_o"] - (104 + 0.5 * 0.85 * 11)) < 1e-9


def test_prior_missing_data_degrades_to_league_average():
    last = {"X": {"adj_o": 115.0, "adj_d": 95.0, "adj_t": 72.0},
            "Y": {"adj_o": 90.0, "adj_d": 110.0, "adj_t": 68.0}}
    # No minutes data at all: both teams get league average.
    p = build_prior(last, None, league_o=104.0, league_t=70.0)
    assert p["X"]["prior_o"] == 104.0 and p["X"]["has_prior"] is False
    assert p["Y"]["prior_o"] == 104.0 and p["Y"]["has_prior"] is False
    assert "no returning-minutes data" in p["X"]["reason"]
    # Empty last season: empty prior, solver falls back itself.
    assert build_prior({}, {"X": 1.0}) == {}
    assert build_prior(None) == {}
    # Team with minutes but no last season rating: league average.
    p2 = build_prior(last, {"X": 1.0, "Z": 1.0},
                     league_o=104.0, league_t=70.0)
    assert p2["Z"]["prior_o"] == 104.0 and p2["Z"]["has_prior"] is False
    # Explicit placeholder shrink, labeled as such, not a measurement.
    p3 = build_prior(last, None, league_o=104.0, league_t=70.0,
                     minutes_unknown_shrink=0.5)
    assert abs(p3["X"]["prior_o"] - (104 + 0.5 * 0.85 * 11)) < 1e-9
    assert "not a measured value" in p3["X"]["reason"]


def test_prior_returning_share_helpers():
    players = [
        {"name": "A", "minutes": 1200, "returning": True},
        {"name": "B", "minutes": 800, "returning": False},
        {"name": "C", "minutes": 1000, "returning": True},
    ]
    assert abs(compute_returning_share(players) - 2200 / 3000) < 1e-9
    assert compute_returning_share([]) is None
    assert compute_returning_share([{"name": "A", "minutes": 0, "returning": True}]) is None
    last = {"X": {"adj_o": 115.0, "adj_d": 95.0, "adj_t": 72.0}}
    p = build_prior_from_rosters(last, {"X": players},
                                 league_o=104.0, league_t=70.0)
    assert abs(p["X"]["returning_share"] - 2200 / 3000) < 1e-9
    assert abs(p["X"]["prior_o"] - (104 + (2200 / 3000) * 0.85 * 11)) < 1e-9
    # League-average helper: every team gets the league, flagged.
    la = league_average_prior(["X", "Y"], league_o=104.0, league_t=70.0)
    assert la["X"]["prior_o"] == 104.0 and la["X"]["has_prior"] is False


def test_prior_plugs_into_solver():
    games = load_games()
    last = {"Illinois Fighting Illini": {"adj_o": 110.0, "adj_d": 100.0, "adj_t": 72.0}}
    prior = build_prior(last, {"Illinois Fighting Illini": 1.0},
                        league_o=104.0, league_t=70.0)
    teams, _, _ = solve(games, prior=prior)
    assert teams["Illinois Fighting Illini"]["prior_o"] == prior["Illinois Fighting Illini"]["prior_o"]
    assert teams["Illinois Fighting Illini"]["prior_d"] == prior["Illinois Fighting Illini"]["prior_d"]
    # The prior changes Illinois materially. Note the direction is
    # NOT simply toward the prior Net (+8.5): on the prototype the
    # Illinois prior also lowers FDU and Penn AdjD, which feeds
    # back into Illinois AdjO, so Illinois Net rises from +20.9
    # to +26.9. That is a small-component feedback effect (the
    # Illinois-FDU-Penn-Butler component has only 3 games), not a
    # solver bug, and it is why a prior on one team in a tiny
    # component cannot be read as a simple pull toward the prior.
    base, _, _ = solve(games)
    assert abs(teams["Illinois Fighting Illini"]["net"]
               - base["Illinois Fighting Illini"]["net"]) > 1.0
    # On a connected full season the prior behaves as expected:
    # a prior built from the true ratings improves recovery.
    s_games, true_o, true_d = _synthetic_season()
    s_base, _, _ = solve(s_games)
    s_last = {t: {"adj_o": true_o[t], "adj_d": true_d[t], "adj_t": 68.8}
              for t in true_o}
    s_prior = build_prior(s_last, {t: 1.0 for t in true_o},
                          league_o=104.0, league_t=68.8)
    s_with, _, _ = solve(s_games, prior=s_prior)
    def mae(ts):
        return sum(abs(ts[t]["adj_o"] - true_o[t])
                   + abs(ts[t]["adj_d"] - true_d[t]) for t in true_o) / 16
    assert mae(s_with) < mae(s_base), (mae(s_with), mae(s_base))


def _comparison_report():
    """Print the v1 vs v2 comparison on the prototype data."""
    games = load_games()
    v1, _, _ = v1_compute(games)
    v2, _, _, info = solve(games, return_info=True)
    r1 = _ranks({t: v["net"] for t, v in v1.items()})
    r2 = _ranks({t: v["net"] for t, v in v2.items()})
    rho = _spearman(r1, r2)
    mean_abs = sum(abs(r1[t] - r2[t]) for t in r1) / len(r1)
    print(f"\nv1 vs v2 on prototype ({len(games)} games, {len(v1)} teams):")
    print(f"  Spearman rho (Net rank): {rho:.3f}")
    print(f"  mean absolute rank change: {mean_abs:.1f}")
    print(f"  solver: {info['iterations']} iterations, converged={info['converged']}, "
          f"prior_weight={info['prior_weight']:.0f} poss, home_court={info['home_court']}")
    ill1, ill2 = v1["Illinois Fighting Illini"], v2["Illinois Fighting Illini"]
    print(f"  Illinois v1: AdjO {ill1['adj_o']:.1f}, AdjD {ill1['adj_d']:.1f}, "
          f"Net {ill1['net']:+.1f}, AdjT {ill1['adj_t']:.1f}, rank {r1['Illinois Fighting Illini']}/84")
    print(f"  Illinois v2: AdjO {ill2['adj_o']:.1f}, AdjD {ill2['adj_d']:.1f}, "
          f"Net {ill2['net']:+.1f}, AdjT {ill2['adj_t']:.1f}, rank {r2['Illinois Fighting Illini']}/84")
    print("  v2 top 10:")
    for i, name in enumerate(sorted(v2, key=lambda t: v2[t]["net"], reverse=True)[:10], 1):
        t = v2[name]
        print(f"    {i:2d} {name[:32]:32s} AdjO {t['adj_o']:.1f} AdjD {t['adj_d']:.1f} "
              f"Net {t['net']:+.1f} AdjT {t['adj_t']:.1f} (v1 rank {r1[name]})")
    print("  biggest rank moves v1 -> v2:")
    moves = sorted(v1, key=lambda t: abs(r1[t] - r2[t]), reverse=True)[:5]
    for name in moves:
        print(f"    {name[:32]:32s} v1 rank {r1[name]:>2d} (Net {v1[name]['net']:+.1f}) "
              f"-> v2 rank {r2[name]:>2d} (Net {v2[name]['net']:+.1f})")


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
    _comparison_report()
    if failed:
        print(f"{failed} test(s) failed")
        sys.exit(1)
    print("all solver tests passed")
