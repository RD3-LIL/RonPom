"""Build the real 2026-27 preseason prior from 2025-26 ratings.

The returning-minutes share comes from the player profiles we
already have, no new data pull: a player counts as returning
for a team when the same athlete id appears for the same team
in both seasons' profiles. Transfers count for neither team,
which is correct: returning minutes are minutes from players
who were on that team last year and are back.

Known limit: DNP players are excluded from the profiles, so a
returning player who has not appeared yet in 2026-27 is missed
and the share reads low. With 2 games played that is mostly
deep-bench players, but it is a real undercount, not a guess.
The full roster pull (fetch_rosters.py) would fix it; until
then this is the measured value from the profiles on disk.

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
sys.path.insert(0, str(HERE))
from prior import build_prior_from_rosters  # noqa: E402

LEAGUE_O_2025_26 = 109.3
LEAGUE_T_2025_26 = 68.2


def load_profiles(season):
    path = DATA / f"players_{season.replace('-', '_')}.json"
    return json.loads(path.read_text())["players"]


def build_rosters_from_profiles(profiles_last, profiles_this):
    """Rosters for prior.build_prior_from_rosters, from profiles.

    profiles_last / profiles_this: player profile dicts with
    athlete_id, team, and totals.min. Returns dict team -> list
    of {"name", "minutes", "returning"} where minutes are last
    season's minutes and returning is True when the same athlete
    id appears for the same team this season.
    """
    this_keys = {(p["athlete_id"], p["team"]) for p in profiles_this}
    rosters = {}
    for p in profiles_last:
        key = (p["athlete_id"], p["team"])
        rosters.setdefault(p["team"], []).append({
            "name": p["name"],
            "minutes": p["totals"]["min"],
            "returning": key in this_keys,
        })
    return rosters


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
    rosters = build_rosters_from_profiles(profiles_last, profiles_this)
    last_ratings = load_last_ratings("2025-26")
    prior = build_prior_from_rosters(
        last_ratings, rosters,
        league_o=LEAGUE_O_2025_26, league_t=LEAGUE_T_2025_26)
    out = DATA / "prior_2026_27.json"
    out.write_text(json.dumps(prior, indent=1))
    with_prior = [v for v in prior.values() if v["has_prior"]]
    shares = [v["returning_share"] for v in with_prior
              if v["returning_share"] is not None]
    print(f"Wrote {out.name}: {len(prior)} teams, "
          f"{len(with_prior)} with a real prior, "
          f"mean returning share {sum(shares) / len(shares):.2f}, "
          f"min {min(shares):.2f}, max {max(shares):.2f}")
    for team in ["Illinois Fighting Illini", "Duke Blue Devils",
                 "Arizona Wildcats", "Iowa State Cyclones",
                 "Florida Gators", "Houston Cougars"]:
        p = prior.get(team)
        if p:
            print(f"  {team}: share {p['returning_share']}, "
                  f"prior AdjO {p['prior_o']:.1f}, "
                  f"AdjD {p['prior_d']:.1f}, weight {p['prior_weight']:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
