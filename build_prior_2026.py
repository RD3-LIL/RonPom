"""Build the real 2026-27 preseason prior from 2025-26 ratings.

The prior is built from where this season's players played
last season, using the player profiles we already have, no new
data pull. For each team, this season's minutes split into:
  returning: same athlete id on the same team last season,
  transfer: same athlete id on a different D1 team last season,
  new: no D1 profile last season (freshmen, DNPs, walk-ons).
The prior rating is the minutes-weighted average of the source
teams' 2025-26 ratings (returning players contribute their own
team's rating, transfers contribute their old team's rating,
new players contribute the league average), faded toward the
league average by the informed share (returning + transfer)
times the 0.85 regression, exactly as prior.build_prior fades
a returning-only prior. The prior weight is
300 * (0.25 + 0.75 * informed_share). A transfer counts for
the NEW team, not the old one: a team that rebuilt through the
portal (LSU: 64% of minutes from transfers in Nov 2026) gets
a real prior instead of the league average.

Known limit: DNP players are excluded from the profiles, so a
returning or transfer player who has not appeared yet in
2026-27 is missed and the shares read low. With 2-3 games
played that is mostly deep-bench players, but it is a real
undercount, not a guess. The full roster pull
(fetch_rosters.py) would fix it; until then this is the
measured value from the profiles on disk. Minutes weights
are this season's minutes, the best measure of who is
actually on the floor now.

League averages are the 2025-26 solver run's values (league
OffEff 109.3, tempo 68.2), not the mean of the ratings CSV.

Usage:
    python3 build_prior_2026.py
        Writes data/prior_2026_27.json and prints a summary.
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"

LEAGUE_O_2025_26 = 109.3
LEAGUE_T_2025_26 = 68.2
REGRESSION = 0.85
TEMPO_REGRESSION = 0.70
BASE_PRIOR_WEIGHT = 300.0


def load_profiles(season):
    path = DATA / f"players_{season.replace('-', '_')}.json"
    return json.loads(path.read_text())["players"]


def build_transfer_prior(last_ratings, profiles_last, profiles_this,
                         league_o=LEAGUE_O_2025_26,
                         league_t=LEAGUE_T_2025_26):
    """Transfer-aware prior, same shape as prior.build_prior output.

    last_ratings: team -> {"adj_o", "adj_d", "adj_t"} from the
    prior season. profiles_last / profiles_this: player profile
    dicts with athlete_id, team, and totals.min. A player
    contributes this season's minutes, weighted by the
    last-season rating of the team he played for (own team for
    a returner, old team for a transfer, league average for a
    player with no prior-season profile). Teams with no current
    roster get the league average with has_prior False.
    """
    last_team = {}
    for p in profiles_last:
        last_team[p["athlete_id"]] = p["team"]
    # This season's minutes by team, split by source.
    teams = {}
    for p in profiles_this:
        team = p["team"]
        mins = float(p["totals"]["min"])
        entry = teams.setdefault(team, {"total": 0.0, "ret": 0.0,
                                        "tr": 0.0, "o": 0.0,
                                        "d": 0.0, "t": 0.0})
        entry["total"] += mins
        src = last_team.get(p["athlete_id"])
        if src is None:
            src_o, src_d, src_t = league_o, league_o, league_t
        elif src == team:
            entry["ret"] += mins
            src_o, src_d, src_t = _rating(last_ratings, team,
                                          league_o, league_t)
        else:
            entry["tr"] += mins
            src_o, src_d, src_t = _rating(last_ratings, src,
                                          league_o, league_t)
        entry["o"] += mins * src_o
        entry["d"] += mins * src_d
        entry["t"] += mins * src_t
    prior = {}
    for team in set(last_ratings) | set(teams):
        entry = teams.get(team)
        if entry is None or entry["total"] <= 0:
            prior[team] = {
                "prior_o": league_o, "prior_d": league_o,
                "prior_t": league_t, "returning_share": None,
                "transfer_share": None, "has_prior": False,
                "prior_weight": BASE_PRIOR_WEIGHT * 0.5,
                "reason": "no current roster in profiles, "
                          "league average",
            }
            continue
        total = entry["total"]
        ret_share = entry["ret"] / total
        tr_share = entry["tr"] / total
        info = ret_share + tr_share
        blended_o = entry["o"] / total
        blended_d = entry["d"] / total
        blended_t = entry["t"] / total
        prior[team] = {
            "prior_o": league_o + info * REGRESSION * (blended_o - league_o),
            "prior_d": league_o + info * REGRESSION * (blended_d - league_o),
            "prior_t": league_t + info * TEMPO_REGRESSION * (blended_t - league_t),
            "returning_share": round(ret_share, 4),
            "transfer_share": round(tr_share, 4),
            "has_prior": info > 0,
            "prior_weight": BASE_PRIOR_WEIGHT * (0.25 + 0.75 * info),
            "reason": (f"returning share {ret_share:.2f}, "
                       f"transfer share {tr_share:.2f}"),
        }
    return prior


def _rating(last_ratings, team, league_o, league_t):
    """A team's last-season rating, or league average if unrated."""
    r = last_ratings.get(team)
    if r is None:
        return league_o, league_o, league_t
    return float(r["adj_o"]), float(r["adj_d"]), float(r["adj_t"])


def load_last_ratings(season="2025-26"):
    path = DATA / f"ratings_{season.replace('-', '_')}.csv"
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return {r["team"]: {"adj_o": float(r["adj_o"]),
                        "adj_d": float(r["adj_d"]),
                        "adj_t": float(r["adj_t"])} for r in rows}


def main():
    profiles_last = load_profiles("2025-26")
    profiles_this = load_profiles("2026-27")
    last_ratings = load_last_ratings("2025-26")
    prior = build_transfer_prior(
        last_ratings, profiles_last, profiles_this,
        league_o=LEAGUE_O_2025_26, league_t=LEAGUE_T_2025_26)
    out = DATA / "prior_2026_27.json"
    out.write_text(json.dumps(prior, indent=1))
    with_prior = [v for v in prior.values() if v["has_prior"]]
    shares = [v["returning_share"] + v["transfer_share"]
              for v in with_prior
              if v["returning_share"] is not None]
    print(f"Wrote {out.name}: {len(prior)} teams, "
          f"{len(with_prior)} with a real prior, "
          f"mean informed share {sum(shares) / len(shares):.2f}, "
          f"min {min(shares):.2f}, max {max(shares):.2f}")
    for team in ["Illinois Fighting Illini", "Duke Blue Devils",
                 "Arizona Wildcats", "Iowa State Cyclones",
                 "Florida Gators", "Houston Cougars",
                 "LSU Tigers", "Texas Longhorns"]:
        p = prior.get(team)
        if p:
            print(f"  {team}: returning {p['returning_share']}, "
                  f"transfer {p['transfer_share']}, "
                  f"prior AdjO {p['prior_o']:.1f}, "
                  f"AdjD {p['prior_d']:.1f}, weight {p['prior_weight']:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
