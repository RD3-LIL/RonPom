"""
KenPom-like ratings, solver v2: a proper linear-system solve.

Model
-----
For a game between offense team i and defense team j, with
possessions p and points per 100 possessions y_ij:

    y_ij = AdjO_i + AdjD_j - L + h * s_ij

where L is the league average efficiency, h is the home court
parameter (points per 100 possessions, see below), and s_ij is
+1 when i is at home, -1 when i is away. If the opponent defense
is league average (AdjD_j = L), team i is expected to score at
its own AdjO. If the opponent defense is better than average
(AdjD_j < L), team i is expected to score less.

Tempo uses the same shape, with no home court term:

    p_ij = AdjT_i + AdjT_j - L_t

where L_t is league average tempo (possessions per game).

Solve method
------------
Gauss-Seidel sweeps with damping, not a direct matrix inverse
and not the one-pass additive adjustment in ratings.py (v1).
Each sweep updates each team's AdjO, AdjD, and AdjT in place
from its opponents' current values, then damps the move:

    new = (1 - omega) * old + omega * target

with omega = damping (default 0.5). Damping is what keeps the
sweeps stable on 1-2 game samples: without it, a blowout can
whipsaw a team's rating from one sweep to the next.

Each target is a possession-weighted average of the game-implied
values, shrunk toward a prior:

    target_Oi = (sum_p p * (y_ij - AdjD_j + L - h*s_ij)
                 + w * prior_Oi) / (sum_p p + w)

where w is prior_weight, in possessions. A team with 2 games
has about 140 possessions of data, so the default w = 300
means the prior carries about two thirds of the weight early
in the season and fades as games accumulate (30 games is about
2100 possessions, so the prior is then about 12 percent of the
weight). That is the point of a prior: early-season ratings
should mostly say "we do not know yet", and the data should
take over as the season goes on.

The prior defaults to the league average for every team. Pass a
prior dict (see prior.py) to use last season's ratings instead.
Without any prior anchor the system is not identified: adding a
constant c to every AdjO and subtracting c from every AdjD
leaves every prediction unchanged, and on this sparse early
season data the game graph is disconnected (57 games, 84 teams,
so several components have no path between them). The prior is
what anchors each component. If prior_weight is 0, the solver
instead recenters mean AdjO and mean AdjD to L after each sweep,
which fixes the shift but does nothing for disconnected
components, so prior_weight 0 is not recommended on sparse data
and is only kept for full-season tests.

Home court
----------
home_court is a documented parameter, default 0.0 (off). It is
not estimated from the data here. If you enable it, a value
around 1.0 to 2.0 points per 100 possessions per side is the
usual range in the literature, meaning a home team is expected
to score about h more and allow about h less, per 100. The
default is 0.0 because the prototype data cannot identify it
(1-2 games per team, almost every team at home in its first
games) and a hidden nonzero value would silently tilt every
rating. Pass it explicitly if you want it on.

What v2 fixes vs v1, and what it does not fix
---------------------------------------------
v1 (ratings.py, one pass) treats each opponent's RAW efficiency
as truth. That breaks two ways on 1-2 games: a team that beats
a 1-game opponent by 40 gets its whole blowout discounted,
because that opponent's raw defense looks terrible; and a team
that loses to a 1-game opponent gets boosted to the top of the
table, because that opponent's raw offense looks great. On this
prototype, v1 ranks Chattanooga 1st (Net +25.9) even though it
lost its only game, and ties 17 teams at exactly Net 0. v2
solves the coupled system with a prior, so Chattanooga falls
to about league average and the Net 0 ties disappear.

v2 does NOT fix small samples. Two blowouts against weak teams
still look great, just shrunk toward the prior. Illinois is
rank 1 in v2 on this prototype, which says more about the
opponents (Fairleigh Dickinson, Penn) and the league-average
prior than about Illinois. A real preseason prior (prior.py)
would anchor Illinois to last season instead of to the league
average, and would pull that rank down.

One more small-sample quirk, found while testing: a prior on a
single team in a tiny component does not simply pull that team
toward the prior. Giving Illinois a prior of Net +8.5 raises
its solved Net from +20.9 to +26.9, because the prior also
moves its opponents (FDU and Penn AdjD fall), which feeds back
into Illinois AdjO. That is component feedback on 3 games, not
a solver bug, and it disappears on a connected full season,
where a true prior improves recovery (see test_solver.py).

Usage:
    python3 solver.py
    python3 solver.py Illinois
    python3 solver.py --home-court 1.5
"""

import json, sys
from pathlib import Path

HERE = Path(__file__).parent
GAMES = HERE / "data" / "games.json"

NON_D1 = {
    "Framingham State Rams", "Regent Regent Royals", "Virginia Lynchburg Dragons",
    "Concordia Chicago Cougars", "Erskine Flying Fleet", "Christendom Crusaders",
    "Central College Dutch", "Blue Mountain Christian Toppers", "Webster Gorloks",
    "Bob Jones Bruins", "Champion Christian Tigers", "Saint Mary of the Woods Pomeroys",
    "West Coast Baptist Eagles", "Grace University Lancers", "Salish Kootenai Bison",
}

DEFAULT_PRIOR_WEIGHT = 300.0  # possessions, about 4.3 games at 70 poss/game
DEFAULT_DAMPING = 0.5
DEFAULT_HOME_COURT = 0.0
DEFAULT_MAX_ITER = 500
DEFAULT_TOL = 1e-6


def possessions(stats):
    return stats["fga"] - stats["orb"] + stats["tov"] + 0.44 * stats["fta"]


def load_games():
    """Same filter as ratings.py: played games only, no obvious non-D1."""
    games = json.loads(GAMES.read_text())
    out = []
    for g in games:
        if g["home_score"] == 0 and g["away_score"] == 0:
            continue  # not played yet
        if g["home"] in NON_D1 or g["away"] in NON_D1:
            continue
        out.append(g)
    return out


def _normalize_prior_entry(entry):
    """Accept a prior entry in any of the shapes prior.py produces.

    Returns (prior_o, prior_d, prior_t, prior_weight_or_None) with
    missing values as None. Accepts snake_case (prior_o, adj_o),
    the ratings.py keys (adj_o, adj_d, adj_t), and the CamelCase
    keys (AdjO, AdjD, AdjT).
    """
    if not isinstance(entry, dict):
        return None, None, None, None
    def pick(*keys):
        for k in keys:
            if k in entry and entry[k] is not None:
                return float(entry[k])
        return None
    prior_o = pick("prior_o", "adj_o", "AdjO", "off", "offense")
    prior_d = pick("prior_d", "adj_d", "AdjD", "def", "defense")
    prior_t = pick("prior_t", "adj_t", "AdjT", "tempo")
    weight = pick("prior_weight", "weight")
    return prior_o, prior_d, prior_t, weight


def solve(games, prior=None, prior_weight=DEFAULT_PRIOR_WEIGHT,
          home_court=DEFAULT_HOME_COURT, damping=DEFAULT_DAMPING,
          max_iter=DEFAULT_MAX_ITER, tol=DEFAULT_TOL,
          return_info=False):
    """Solve AdjO/AdjD/AdjT by damped Gauss-Seidel with a prior.

    games: records with home/away, home_score/away_score,
        home_stats/away_stats (fga/fta/orb/tov). The conf fields
        home_conf_id/away_conf_id are accepted when present and
        ignored otherwise; the prototype games.json has none.
    prior: optional dict team -> prior entry (see
        _normalize_prior_entry). Teams missing from it use the
        league average as their prior. Pass None for a pure
        league-average prior for every team.
    prior_weight: global prior strength, in possessions.
        A per-team "prior_weight" in a prior entry overrides it
        for that team.
    home_court: points per 100 possessions, default 0.0 (off).
    damping: relaxation factor, 0 < damping <= 1. 0.5 is the
        default; 1.0 is plain Gauss-Seidel and can oscillate
        on sparse blowout data.
    return_info: when True, return a 4-tuple
        (teams, league_o, league_t, info) with iterations,
        convergence, and settings. When False (default), return
        the same 3-tuple shape as ratings.compute():
        (teams, league_o, league_t).

    teams values carry: games, poss, pts, opp_pts, opponents,
        raw_o, raw_d, raw_t, adj_o, adj_d, adj_t, net, plus the
        prior_o/prior_d/prior_t and prior_weight actually used.
    """
    if prior_weight < 0:
        raise ValueError("prior_weight must be >= 0")
    if not 0 < damping <= 1:
        raise ValueError("damping must be in (0, 1]")

    # Per-team raw totals, same definitions as ratings.py.
    teams = {}
    off_obs = {}    # team -> [(opp, eff, poss, home_sign)]
    def_obs = {}    # team -> [(opp, eff, poss, home_sign_of_opp)]
    tempo_obs = {}  # team -> [(opp, game_poss)]
    for g in games:
        poss = (possessions(g["home_stats"]) + possessions(g["away_stats"])) / 2
        for side, opp_side, s in (("home", "away", 1), ("away", "home", -1)):
            name = g[side]
            opp_name = g[opp_side]
            pts = g[f"{side}_score"]
            opp_pts = g[f"{opp_side}_score"]
            eff = 100 * pts / poss
            t = teams.setdefault(name, {
                "games": 0, "poss": 0.0, "pts": 0, "opp_pts": 0,
                "opponents": [],
            })
            t["games"] += 1
            t["poss"] += poss
            t["pts"] += pts
            t["opp_pts"] += opp_pts
            t["opponents"].append(opp_name)
            off_obs.setdefault(name, []).append((opp_name, eff, poss, s))
            def_obs.setdefault(opp_name, []).append((name, eff, poss, s))
            tempo_obs.setdefault(name, []).append((opp_name, poss))
            tempo_obs.setdefault(opp_name, []).append((name, poss))

    if not teams:
        info = {"iterations": 0, "converged": True, "max_change": 0.0,
                "prior_weight": prior_weight, "home_court": home_court,
                "damping": damping, "n_games": 0, "n_teams": 0}
        if return_info:
            return teams, 0.0, 0.0, info
        return teams, 0.0, 0.0

    for t in teams.values():
        t["raw_o"] = 100 * t["pts"] / t["poss"]
        t["raw_d"] = 100 * t["opp_pts"] / t["poss"]
        t["raw_t"] = t["poss"] / t["games"]
    league_o = sum(t["raw_o"] for t in teams.values()) / len(teams)
    league_t = sum(t["raw_t"] for t in teams.values()) / len(teams)

    # Priors: explicit entry wins, otherwise league average.
    prior_o, prior_d, prior_t, prior_w = {}, {}, {}, {}
    for name in teams:
        po, pd, pt, pw = None, None, None, None
        if prior is not None and name in prior:
            po, pd, pt, pw = _normalize_prior_entry(prior[name])
        prior_o[name] = league_o if po is None else po
        prior_d[name] = league_o if pd is None else pd
        prior_t[name] = league_t if pt is None else pt
        prior_w[name] = prior_weight if pw is None else pw

    adj_o = dict(prior_o)
    adj_d = dict(prior_d)
    adj_t = dict(prior_t)

    names = sorted(teams)
    iterations = 0
    max_change = 0.0
    converged = False
    for it in range(1, max_iter + 1):
        iterations = it
        max_change = 0.0
        for name in names:
            w = prior_w[name]
            # Offense: implied AdjO from each game, shrunk to prior.
            num = w * prior_o[name]
            den = w
            for opp, eff, poss, s in off_obs.get(name, []):
                num += poss * (eff - adj_d[opp] + league_o - home_court * s)
                den += poss
            target = num / den
            new = (1 - damping) * adj_o[name] + damping * target
            max_change = max(max_change, abs(new - adj_o[name]))
            adj_o[name] = new
            # Defense: implied AdjD from opponents' scoring vs us.
            num = w * prior_d[name]
            den = w
            for opp, eff, poss, s in def_obs.get(name, []):
                num += poss * (eff - adj_o[opp] + league_o - home_court * s)
                den += poss
            target = num / den
            new = (1 - damping) * adj_d[name] + damping * target
            max_change = max(max_change, abs(new - adj_d[name]))
            adj_d[name] = new
            # Tempo: one observation per game, prior in games.
            w_games = w / league_t if league_t else 0.0
            num = w_games * prior_t[name]
            den = w_games
            for opp, p in tempo_obs.get(name, []):
                num += 1.0 * (p - adj_t[opp] + league_t)
                den += 1.0
            target = num / den
            new = (1 - damping) * adj_t[name] + damping * target
            max_change = max(max_change, abs(new - adj_t[name]))
            adj_t[name] = new
        if prior_weight == 0:
            # No prior anchor: remove the global shift degeneracy
            # by recentering both means on the league average.
            mean_o = sum(adj_o.values()) / len(adj_o)
            mean_d = sum(adj_d.values()) / len(adj_d)
            for name in names:
                adj_o[name] += league_o - mean_o
                adj_d[name] += league_o - mean_d
        if max_change < tol:
            converged = True
            break

    for name, t in teams.items():
        t["adj_o"] = adj_o[name]
        t["adj_d"] = adj_d[name]
        t["adj_t"] = adj_t[name]
        t["net"] = adj_o[name] - adj_d[name]
        t["prior_o"] = prior_o[name]
        t["prior_d"] = prior_d[name]
        t["prior_t"] = prior_t[name]
        t["prior_weight"] = prior_w[name]

    info = {"iterations": iterations, "converged": converged,
            "max_change": max_change, "prior_weight": prior_weight,
            "home_court": home_court, "damping": damping,
            "league_o": league_o, "league_t": league_t,
            "n_games": len(games), "n_teams": len(teams)}
    if return_info:
        return teams, league_o, league_t, info
    return teams, league_o, league_t


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    home_court = DEFAULT_HOME_COURT
    filt = None
    i = 0
    while i < len(argv):
        if argv[i] == "--home-court" and i + 1 < len(argv):
            home_court = float(argv[i + 1])
            i += 2
        else:
            filt = argv[i]
            i += 1
    games = load_games()
    teams, league_o, league_t, info = solve(
        games, home_court=home_court, return_info=True)
    ranked = sorted(teams.items(), key=lambda kv: kv[1]["net"], reverse=True)
    print(f"{info['n_games']} games, {info['n_teams']} teams, "
          f"league avg OffEff {league_o:.1f}, tempo {league_t:.1f}")
    print(f"solver v2: damped Gauss-Seidel, prior_weight "
          f"{info['prior_weight']:.0f} poss, home_court {home_court}, "
          f"damping {info['damping']}, {info['iterations']} iterations, "
          f"converged={info['converged']}")
    print("Early season only, 1-2 games per team, league-average prior, "
          "so take the order with a grain of salt.")
    print(f"{'Rk':>3} {'Team':<32} {'GP':>2} {'AdjO':>6} {'AdjD':>6} {'Net':>6} {'AdjT':>5}")
    for rank, (name, t) in enumerate(ranked, 1):
        if filt and filt.lower() not in name.lower():
            continue
        print(f"{rank:>3} {name:<32} {t['games']:>2} {t['adj_o']:>6.1f} "
              f"{t['adj_d']:>6.1f} {t['net']:>6.1f} {t['adj_t']:>5.1f}")
    if not filt:
        print("\nIllinois check:")
        for name, t in teams.items():
            if "Illinois" in name:
                rank = [n for n, _ in ranked].index(name) + 1
                print(f"  {name}: AdjO {t['adj_o']:.1f}, AdjD {t['adj_d']:.1f}, "
                      f"Net {t['net']:.1f}, AdjT {t['adj_t']:.1f}, rank {rank}")


if __name__ == "__main__":
    main()
