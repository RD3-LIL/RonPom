"""Run solver v2 on each consolidated season and write team ratings.

For each data/games_<season>.json, runs solver.solve() and writes
data/ratings_<season>.csv: rank, team, gp, adj_o, adj_d, net, adj_t.
The CSVs are what goes on GitHub; the games JSONs stay local.

Prior: 2026-27 uses the real preseason prior from
data/prior_2026_27.json (2025-26 final ratings faded by
returning minutes, built by build_prior_2026.py). 2024-25 and
2025-26 still use the league-average prior: no prior season is
wired in for them yet (2025-26 could use 2024-25 the same way,
not done yet). If the prior file is missing for 2026-27, the
run falls back to the league-average prior and says so.

Usage:
    python3 write_ratings.py
    python3 write_ratings.py 2024-25
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
from solver import solve  # noqa: E402

SEASONS = ["2024-25", "2025-26", "2026-27"]


PRIOR_FILES = {
    "2026-27": DATA / "prior_2026_27.json",
}


def load_prior(season):
    """Real preseason prior for this season, or None.

    Returns (prior_dict, description). Missing file for a season
    that has one configured is a loud fallback, not a silent
    one: the caller prints the description.
    """
    path = PRIOR_FILES.get(season)
    if path is None:
        return None, "league-average prior (no prior season wired in)"
    if not path.exists():
        return None, (f"league-average prior (prior file {path.name} "
                      "missing, run build_prior_2026.py)")
    prior = json.loads(path.read_text())
    n_real = sum(1 for v in prior.values() if v.get("has_prior"))
    return prior, (f"real prior from {path.name} "
                   f"({n_real} teams with a returning-minutes prior)")


def run_season(season):
    path = DATA / f"games_{season.replace('-', '_')}.json"
    games = json.loads(path.read_text())
    prior, prior_desc = load_prior(season)
    teams, league_o, league_t, info = solve(
        games, prior=prior, return_info=True)
    ranked = sorted(teams.items(), key=lambda kv: kv[1]["net"],
                    reverse=True)
    out_path = DATA / f"ratings_{season.replace('-', '_')}.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "team", "gp", "adj_o", "adj_d", "net",
                         "adj_t"])
        for rank, (name, t) in enumerate(ranked, 1):
            writer.writerow([rank, name, t["games"],
                             round(t["adj_o"], 1), round(t["adj_d"], 1),
                             round(t["net"], 1), round(t["adj_t"], 1)])
    print(f"{season}: {info['n_games']} games used, "
          f"{info['n_teams']} teams, league OffEff {league_o:.1f}, "
          f"tempo {league_t:.1f}, {info['iterations']} iterations, "
          f"converged={info['converged']}, prior: {prior_desc} "
          f"-> {out_path.name}")
    for rank, (name, t) in enumerate(ranked[:5], 1):
        print(f"  {rank} {name} Net {t['net']:.1f} "
              f"(AdjO {t['adj_o']:.1f}, AdjD {t['adj_d']:.1f})")
    for rank, (name, t) in enumerate(ranked, 1):
        if "Illinois Fighting Illini" in name:
            print(f"  Illinois: rank {rank}, Net {t['net']:.1f}, "
                  f"AdjO {t['adj_o']:.1f}, AdjD {t['adj_d']:.1f}, "
                  f"AdjT {t['adj_t']:.1f}, GP {t['games']}")
            break
    return out_path


def main():
    seasons = sys.argv[1:] or SEASONS
    for season in seasons:
        run_season(season)
    return 0


if __name__ == "__main__":
    sys.exit(main())
