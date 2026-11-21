"""SHARP rating v1 for College Ratings (RonPom), ESPN box-score only.

SHARP is a pure shooter rating, like a sharp shooter. It counts
threes and free throws only, not midrange, layups, or dunks.

Why not just TS%?
  TS% is total shooting efficiency, points per scoring attempt.
  It lumps dunks and layups in with jump shots, so the TS% list
  is topped by finishers. A pure shooter rank needs the shots
  that are actually shooting: threes and free throws, with volume.

Formula (points per game added by shooting, above league average):
  sharp = (3P% shrunk - league 3P%) * 3 * 3PA per game
        + (FT% shrunk - league FT%) * FTA per game

  3P% is shrunk with m = 100 attempts, FT% with m = 50, toward
  the league rate. That tames early-season small samples without
  killing the signal. League rates are computed from the current
  totals, not hardcoded.

Floor: GP >= 5 and MPG >= 20. Players below the floor get no
  SHARP value.

Stdlib only. Reads data/players_2026_27.json, writes
data/sharp_2026_27.json and data/sharp_2026_27.csv.

Usage:
    python3 sharp_rating.py
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
SEASON = "2026-27"
M_3P = 100
M_FT = 50
MIN_GP = 5
MIN_MPG = 20.0


def _shrink(makes, attempts, league_rate, m):
    if attempts is None or attempts == 0:
        return league_rate
    return (makes + m * league_rate) / (attempts + m)


def main():
    payload = json.loads((DATA / "players_2026_27.json").read_text())
    players = payload["players"]

    tot_fga = sum(p["totals"]["fga"] for p in players)
    tot_fta = sum(p["totals"]["fta"] for p in players)
    tot_pts = sum(p["totals"]["pts"] for p in players)
    tot_3a = sum(p["totals"]["fg3a"] for p in players)
    tot_3m = sum(p["totals"]["fg3m"] for p in players)
    tot_ftm = sum(p["totals"]["ftm"] for p in players)
    league_ts = tot_pts / (2 * (tot_fga + 0.44 * tot_fta))
    league_3p = tot_3m / tot_3a if tot_3a else 0.326
    league_ft = tot_ftm / tot_fta if tot_fta else 0.699

    out = []
    for p in players:
        tot = p["totals"]
        gp = tot["gp"]
        mpg = p["per_game"]["min"]
        if gp < MIN_GP or mpg < MIN_MPG:
            continue
        sh = p["shooting"]
        p3_shrunk = _shrink(tot["fg3m"], tot["fg3a"], league_3p, M_3P)
        ft_shrunk = _shrink(tot["ftm"], tot["fta"], league_ft, M_FT)
        pa3_pg = tot["fg3a"] / gp
        fta_pg = tot["fta"] / gp
        p3_add = (p3_shrunk - league_3p) * 3 * pa3_pg
        ft_add = (ft_shrunk - league_ft) * fta_pg
        sharp = p3_add + ft_add
        out.append({
            "athlete_id": p["athlete_id"],
            "name": p["name"],
            "team": p["team"],
            "position": p["position"],
            "gp": gp,
            "mpg": round(mpg, 1),
            "min_pct": p["ratings"].get("min_pct"),
            "sharp": round(sharp, 3),
            "p3_add_pg": round(p3_add, 3),
            "ft_add_pg": round(ft_add, 3),
            "fg3_pct": sh.get("fg3_pct"),
            "fg3_pct_shrunk": round(p3_shrunk, 4),
            "fg3a_pg": round(pa3_pg, 2),
            "fg3m_pg": round(tot["fg3m"] / gp, 2),
            "ft_pct": sh.get("ft_pct"),
            "ft_pct_shrunk": round(ft_shrunk, 4),
            "fta_pg": round(fta_pg, 2),
            "ts_pct": sh.get("ts_pct"),
            "efg_pct": sh.get("efg_pct"),
            "rpr": p["ratings"].get("rpr"),
        })
    out.sort(key=lambda x: x["sharp"], reverse=True)
    for i, row in enumerate(out, 1):
        row["rank"] = i

    result = {
        "season": SEASON,
        "games_included": payload.get("games_included"),
        "player_count": len(out),
        "method": (
            "SHARP = (3P% shrunk m=100 - league 3P%) * 3 * 3PA/g "
            "+ (FT% shrunk m=50 - league FT%) * FTA/g, in points per "
            "game added above league average. Floor GP >= 5 and "
            "MPG >= 20. TS% is total shooting efficiency and is "
            "shown for context only, it is not part of the score."
        ),
        "league": {
            "ts_pct": round(league_ts, 4),
            "fg3_pct": round(league_3p, 4),
            "ft_pct": round(league_ft, 4),
        },
        "players": out,
    }
    (DATA / "sharp_2026_27.json").write_text(json.dumps(result, indent=2))
    fields = ["rank", "athlete_id", "name", "team", "position", "gp",
              "mpg", "sharp", "p3_add_pg", "ft_add_pg",
              "fg3_pct", "fg3_pct_shrunk", "fg3a_pg",
              "fg3m_pg", "ft_pct", "ft_pct_shrunk", "fta_pg",
              "ts_pct", "efg_pct", "rpr"]
    with open(DATA / "sharp_2026_27.csv", "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        for row in out:
            w.writerow({k: ("" if row.get(k) is None else row.get(k))
                        for k in fields})
    print(f"Wrote data/sharp_2026_27.json + .csv: {len(out)} players")
    print(f"League TS {league_ts:.3f}, 3P {league_3p:.3f}, FT {league_ft:.3f}")
    print("Top 25 SHARP:")
    for row in out[:25]:
        print(f"  {row['rank']:2}. {row['name']} ({row['team']}) "
              f"{row['sharp']:+.2f}  "
              f"3P {row['fg3_pct'] * 100 if row['fg3_pct'] is not None else 0:.1f}% "
              f"on {row['fg3a_pg']:.1f}/g  "
              f"FT {row['ft_pct'] * 100 if row['ft_pct'] is not None else 0:.1f}%  "
              f"TS {row['ts_pct'] * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
