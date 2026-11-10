"""
KenPom-like college basketball ratings (prototype, stdlib only).

Method, in plain English:
  Possessions (Dean Oliver / KenPom formula):
      Poss = FGA - ORB + TOV + 0.44 * FTA
  Game possessions = average of the two teams' possessions.
  Raw offensive efficiency = 100 * points / possessions
  Raw defensive efficiency = 100 * opponent points / possessions
  Tempo = possessions per game

  Adjusted efficiency: ONE pass, additive, using opponents' RAW
  efficiencies (not their adjusted ones).
      AdjO_i = RawO_i + (league_avg - avg opponent RawD)
      AdjD_i = RawD_i + (league_avg - avg opponent RawO)
      AdjT_i = RawT_i + (league_avg_tempo - avg opponent RawT)
  If you played good defenses, your raw offense is adjusted up.
  If you played good offenses, your raw defense is adjusted down.
  Why one pass: iterating to convergence on 1-2 game blowouts
  diverges, a bad team's adjusted defense explodes, which then
  collapses its opponents' adjusted offense, and so on. KenPom
  avoids this with a full season (30 games per team), a preseason
  prior, and a proper linear-system solve. This prototype does
  the honest small-sample version instead, and says so.
  Net rating = AdjO - AdjD. Rank by net.

This is NOT KenPom. His exact opponent adjustment, early-season
priors, and weighting are proprietary, and he excludes non-D1 games
and uses a full season. This prototype:
  - uses free ESPN box scores, Nov 2-9, 2026 only
  - excludes not-yet-played games (0-0 on Nov 9)
  - excludes obvious non-D1 opponents (KenPom excludes them too)
  - has NO preseason prior, so 1-2 games per team = very noisy.
    Illinois scoring 120 and 112 in its first two games will look
    absurdly good. That is the data, not a bug, and it is why
    KenPom leans on priors early in the season.

Usage:
    python3 ratings.py
    python3 ratings.py Illinois
"""

import json, sqlite3, sys
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE / "kenpom.db"
GAMES = HERE / "data" / "games.json"

NON_D1 = {
    "Framingham State Rams", "Regent Regent Royals", "Virginia Lynchburg Dragons",
    "Concordia Chicago Cougars", "Erskine Flying Fleet", "Christendom Crusaders",
    "Central College Dutch", "Blue Mountain Christian Toppers", "Webster Gorloks",
    "Bob Jones Bruins", "Champion Christian Tigers", "Saint Mary of the Woods Pomeroys",
    "West Coast Baptist Eagles", "Grace University Lancers", "Salish Kootenai Bison",
}

def possessions(stats):
    return stats["fga"] - stats["orb"] + stats["tov"] + 0.44 * stats["fta"]

def is_d1_game(g):
    """True if both teams are D1. Full-season files carry
    conferenceId (a team is D1 iff it has one); KenPom excludes
    non-D1 games entirely. Prototype games carry no conference
    fields, so they fall back to the NON_D1 name list."""
    if "home_conf_id" in g or "away_conf_id" in g:
        return g.get("home_conf_id") is not None and g.get("away_conf_id") is not None
    return g["home"] not in NON_D1 and g["away"] not in NON_D1


def load_games():
    games = json.loads((GAMES).read_text())
    out = []
    for g in games:
        if g["home_score"] == 0 and g["away_score"] == 0:
            continue  # not played yet
        if not is_d1_game(g):
            continue
        if g.get("stats_missing"):
            continue  # final score but empty boxscore, possessions would be 0
        out.append(g)
    return out

def compute(games):
    # per-team raw totals
    teams = {}
    for g in games:
        if not is_d1_game(g):
            # KenPom rates D1 teams only; non-D1 games are excluded.
            continue
        poss = (possessions(g["home_stats"]) + possessions(g["away_stats"])) / 2
        if poss <= 0:
            # Final score but empty boxscore (stats_missing): no
            # possessions to divide by, so the game carries no
            # efficiency information. Skip it, never crash on it.
            continue
        for side, opp in (("home", "away"), ("away", "home")):
            name = g[side]
            opp_name = g[opp]
            pts = g[f"{side}_score"]
            opp_pts = g[f"{opp}_score"]
            t = teams.setdefault(name, {"games": 0, "poss": 0.0, "pts": 0, "opp_pts": 0, "opponents": []})
            t["games"] += 1
            t["poss"] += poss
            t["pts"] += pts
            t["opp_pts"] += opp_pts
            t["opponents"].append(opp_name)
    for t in teams.values():
        t["raw_o"] = 100 * t["pts"] / t["poss"]
        t["raw_d"] = 100 * t["opp_pts"] / t["poss"]
        t["raw_t"] = t["poss"] / t["games"]
        t["adj_o"] = t["raw_o"]
        t["adj_d"] = t["raw_d"]
        t["adj_t"] = t["raw_t"]
    league_o = sum(t["raw_o"] for t in teams.values()) / len(teams)
    league_t = sum(t["raw_t"] for t in teams.values()) / len(teams)
    for name, t in teams.items():
        opp_d = sum(teams[o]["raw_d"] for o in t["opponents"]) / len(t["opponents"])
        opp_o = sum(teams[o]["raw_o"] for o in t["opponents"]) / len(t["opponents"])
        opp_t = sum(teams[o]["raw_t"] for o in t["opponents"]) / len(t["opponents"])
        t["adj_o"] = t["raw_o"] + (league_o - opp_d)
        t["adj_d"] = t["raw_d"] + (league_o - opp_o)
        t["adj_t"] = t["raw_t"] + (league_t - opp_t)
    for t in teams.values():
        t["net"] = t["adj_o"] - t["adj_d"]
    return teams, league_o, league_t

def save_db(games, teams):
    conn = sqlite3.connect(DB)
    conn.executescript((HERE / "schema.sql").read_text())
    for g in games:
        conn.execute("INSERT OR IGNORE INTO games VALUES (?,?,?,?,?,?)",
                     (g["event_id"], g["date"], g["home"], g["away"], g["home_score"], g["away_score"]))
    for name, t in teams.items():
        conn.execute("INSERT OR REPLACE INTO ratings VALUES (?,?,?,?,?,?,?,?,?)",
                     (name, t["games"], round(t["raw_o"],1), round(t["raw_d"],1),
                      round(t["adj_o"],1), round(t["adj_d"],1), round(t["net"],1),
                      round(t["adj_t"],1), round(t["raw_t"],1)))
    conn.commit()
    conn.close()

def main():
    games = load_games()
    teams, league_o, league_t = compute(games)
    save_db(games, teams)
    ranked = sorted(teams.items(), key=lambda kv: kv[1]["net"], reverse=True)
    print(f"{len(games)} games, {len(teams)} teams, league avg OffEff {league_o:.1f}, tempo {league_t:.1f}")
    print("Early season only, 1-2 games per team, no preseason prior, so take the order with a grain of salt.")
    print(f"{'Rk':>3} {'Team':<32} {'GP':>2} {'AdjO':>6} {'AdjD':>6} {'Net':>6} {'AdjT':>5}")
    for i, (name, t) in enumerate(ranked, 1):
        if len(sys.argv) > 1 and sys.argv[1].lower() not in name.lower():
            continue
        print(f"{i:>3} {name:<32} {t['games']:>2} {t['adj_o']:>6.1f} {t['adj_d']:>6.1f} {t['net']:>6.1f} {t['adj_t']:>5.1f}")
    if len(sys.argv) <= 1:
        print("\nIllinois check:")
        for name, t in teams.items():
            if "Illinois" in name:
                print(f"  {name}: AdjO {t['adj_o']:.1f}, AdjD {t['adj_d']:.1f}, Net {t['net']:.1f}, AdjT {t['adj_t']:.1f}")

if __name__ == "__main__":
    main()
