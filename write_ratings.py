"""Run solver v2 on each consolidated season and write team ratings.

For each data/games_<season>.json, runs solver.solve() with the
league-average prior (no prior season wired in yet) and writes
data/ratings_<season>.csv: rank, team, gp, adj_o, adj_d, net, adj_t.
The CSVs are what goes on GitHub; the games JSONs stay local.

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


def run_season(season):
    path = DATA / f"games_{season.replace('-', '_')}.json"
    games = json.loads(path.read_text())
    teams, league_o, league_t, info = solve(games, return_info=True)
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
          f"converged={info['converged']} -> {out_path.name}")
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
