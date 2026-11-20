"""Extra KenPom-style stats from the free ESPN data: Luck, SOS, NCSOS.

All three are computed from the solver ratings and the game
logs we already have. No new data pull is needed.

- Luck: actual winning percentage minus the Pythagorean
  expected winning percentage, exponent 11.5 (the standard
  college-basketball exponent). Positive Luck means the team's
  record is better than its play suggests (close wins, blowout
  losses); negative means the reverse. KenPom's own Luck uses
  a correlated-Gaussian method on per-game margins; ours is
  the Pythagorean approximation of the same idea, and it is
  labelled as ours, not his.
- SOS (strength of schedule): the games-weighted average Net
  rating of a team's opponents. Positive means a harder
  schedule than average.
- NCSOS (non-conference SOS): the same average, restricted
  to non-conference games (conference_game False). KenPom
  publishes this because conference schedules are mostly
  fixed, so the non-conference slate is where a team chooses
  its difficulty.

Rules:
- D1-vs-D1 games only (solver.is_d1_game), matching the
  ratings and the site's W-L.
- Games with no stats (stats_missing) are excluded: the
  solver skips them too (zero possessions), so counting them
  here inflated GP and, for a 0-0 postponed game, counted the
  away team as a winner. Unplayed 0-0 games are skipped
  outright for the same reason.
- A game whose opponent has no rating is skipped outright
  for both teams (the ratings dict has no entry to average),
  so it contributes nothing to Luck or SOS. The mean-Net
  fallback only applies to a team with no counted D1 games
  at all, whose SOS defaults to the mean Net.
- A team with no non-conference games yet gets NCSOS None.

Usage:
    python3 extra_stats.py   # prints a spot check
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
from solver import is_d1_game  # noqa: E402

PYTHAGOREAN_EXPONENT = 11.5


def pythagorean_wpct(adj_o, adj_d, exponent=PYTHAGOREAN_EXPONENT):
    """Expected winning percentage from efficiencies.

    AdjO and AdjD are points per 100 possessions, both
    positive, so the power is well defined.
    """
    o = adj_o ** exponent
    d = adj_d ** exponent
    return o / (o + d)


def _mean_net(ratings):
    nets = [t["net"] for t in ratings.values()]
    return sum(nets) / len(nets) if nets else 0.0


def compute_extra(ratings, games):
    """Luck, expected W%, SOS, NCSOS per team.

    ratings: solver output, team name -> values with adj_o,
    adj_d, net. games: consolidated season game records.
    Returns team -> {"luck", "exp_wpct", "sos", "ncsos", "gp",
    "wins"}. gp is the number of games counted here; it must
    equal the solver's games for the same team, since both
    count the same D1-vs-D1 games with real stats.
    """
    mean_net = _mean_net(ratings)
    wins = {name: 0 for name in ratings}
    gp = {name: 0 for name in ratings}
    sos_sum = {name: 0.0 for name in ratings}
    sos_n = {name: 0 for name in ratings}
    nc_sum = {name: 0.0 for name in ratings}
    nc_n = {name: 0 for name in ratings}
    for g in games:
        if not is_d1_game(g):
            continue
        # Stats-missing games are not in the solver either
        # (zero possessions), so they must not count here.
        # That also covers the postponed 0-0 games, which
        # would otherwise count the away team as a winner.
        if g.get("stats_missing"):
            continue
        if g.get("home_score") == 0 and g.get("away_score") == 0:
            continue
        home, away = g["home"], g["away"]
        if home not in ratings or away not in ratings:
            continue
        home_won = g["home_score"] > g["away_score"]
        for team, opp, won in ((home, away, home_won),
                               (away, home, not home_won)):
            gp[team] += 1
            if won:
                wins[team] += 1
            sos_sum[team] += ratings[opp]["net"]
            sos_n[team] += 1
            if not g.get("conference_game"):
                nc_sum[team] += ratings[opp]["net"]
                nc_n[team] += 1
    out = {}
    for name, t in ratings.items():
        exp = pythagorean_wpct(t["adj_o"], t["adj_d"])
        actual = wins[name] / gp[name] if gp[name] else 0.0
        out[name] = {
            "luck": actual - exp,
            "exp_wpct": exp,
            "sos": (sos_sum[name] / sos_n[name]
                    if sos_n[name] else mean_net),
            "ncsos": (nc_sum[name] / nc_n[name]
                      if nc_n[name] else None),
            "gp": gp[name],
            "wins": wins[name],
        }
    return out


def main():
    season = sys.argv[1] if len(sys.argv) > 1 else "2026-27"
    games = json.loads(
        (DATA / f"games_{season.replace('-', '_')}.json").read_text())
    from solver import solve
    ratings, league_o, league_t, _ = solve(games, return_info=True)
    extra = compute_extra(ratings, games)
    top_luck = sorted(extra.items(), key=lambda kv: kv[1]["luck"],
                      reverse=True)[:5]
    print(f"{season}: Luck leaders (actual - expected W%)")
    for name, e in top_luck:
        ncsos = f"{e['ncsos']:+.1f}" if e["ncsos"] is not None else "-"
        print(f"  {name}: Luck {e['luck']:+.3f}, "
              f"SOS {e['sos']:+.1f}, NCSOS {ncsos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
