"""Build the RonPom GitHub Pages site (index.html) from the CSVs.

Reads data/ratings_<season>.csv and data/players_<season>.csv and
writes a static index.html at the repo root. No network, no build
step. Re-run after regenerating the CSVs.

Usage:
    python3 build_page.py
"""

import csv
import html
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
SEASONS = ["2024-25", "2025-26", "2026-27"]
REPO = "https://github.com/RD3-LIL/RonPom"


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def team_table(season, rows, limit=25):
    top = rows[:limit]
    ill = next((r for r in rows if "Illinois Fighting Illini" in r["team"]),
               None)
    out = ["<table><thead><tr><th>Rk</th><th>Team</th><th>GP</th>"
           "<th>AdjO</th><th>AdjD</th><th>Net</th><th>AdjT</th>"
           "</tr></thead><tbody>"]
    for r in top:
        cls = " class=\"ill\"" if "Illinois" in r["team"] else ""
        out.append(
            f"<tr{cls}><td>{r['rank']}</td><td>{html.escape(r['team'])}</td>"
            f"<td>{r['gp']}</td><td>{r['adj_o']}</td><td>{r['adj_d']}</td>"
            f"<td>{r['net']}</td><td>{r['adj_t']}</td></tr>")
    if ill and ill not in top:
        out.append(
            f"<tr class=\"ill\"><td>{ill['rank']}</td>"
            f"<td>{html.escape(ill['team'])}</td><td>{ill['gp']}</td>"
            f"<td>{ill['adj_o']}</td><td>{ill['adj_d']}</td>"
            f"<td>{ill['net']}</td><td>{ill['adj_t']}</td></tr>")
    out.append("</tbody></table>")
    out.append(
        f"<p class=\"note\">Full ranking ({len(rows)} teams) in "
        f"<a href=\"data/ratings_{season.replace('-', '_')}.csv\">"
        f"ratings_{season.replace('-', '_')}.csv</a>.</p>")
    return "\n".join(out)


def player_leaders(season, players, min_games=20):
    qualified = [p for p in players
                 if int(p["gp"]) >= min_games and p["rpr"]
                 and float(p["min_pct"]) >= 40]
    by_rpr = sorted(qualified, key=lambda p: float(p["rpr"]),
                    reverse=True)[:5]
    by_ortg = sorted(qualified, key=lambda p: float(p["ortg"] or 0),
                     reverse=True)[:5]
    out = ["<div class=\"leaders\">"]
    out.append("<div><h3>Top players by RPR</h3><table><thead><tr>"
               "<th>Player</th><th>Team</th><th>RPR</th><th>ORtg</th>"
               "<th>PPG</th></tr></thead><tbody>")
    for p in by_rpr:
        out.append(f"<tr><td>{html.escape(p['name'])}</td>"
                   f"<td>{html.escape(p['team'])}</td>"
                   f"<td>{p['rpr']}</td><td>{p['ortg']}</td>"
                   f"<td>{p['pts_pg']}</td></tr>")
    out.append("</tbody></table></div>")
    out.append("<div><h3>Top players by ORtg</h3><table><thead><tr>"
               "<th>Player</th><th>Team</th><th>ORtg</th><th>%Poss</th>"
               "<th>PPG</th></tr></thead><tbody>")
    for p in by_ortg:
        out.append(f"<tr><td>{html.escape(p['name'])}</td>"
                   f"<td>{html.escape(p['team'])}</td>"
                   f"<td>{p['ortg']}</td><td>{p['poss_pct']}</td>"
                   f"<td>{p['pts_pg']}</td></tr>")
    out.append("</tbody></table></div></div>")
    out.append(
        f"<p class=\"note\">Min {min_games} games and 40% of team minutes. "
        f"Full profiles in <a href=\"data/players_"
        f"{season.replace('-', '_')}.csv\">players_"
        f"{season.replace('-', '_')}.csv</a>.</p>")
    return "\n".join(out)


def season_section(season):
    ratings = read_csv(DATA / f"ratings_{season.replace('-', '_')}.csv")
    players = read_csv(DATA / f"players_{season.replace('-', '_')}.csv")
    n_teams = len(ratings)
    n_players = len(players)
    warn = ""
    if season == "2026-27":
        warn = ("<p class=\"warn\">Early season: 2 games per team at most, "
                "league-average prior. Illinois at No. 1 is noise from two "
                "blowouts, not a real claim.</p>")
    # 2026-27 has at most 2-3 games per player, so the usual
    # 20-game floor would leave the leaders tables empty.
    min_games = 2 if season == "2026-27" else 20
    return (f"<section><h2>{season}</h2>{warn}"
            f"<p>{len(ratings)} teams rated, {n_players} players.</p>"
            f"<h3>Team ratings</h3>{team_table(season, ratings)}"
            f"<h3>Player leaders</h3>"
            f"{player_leaders(season, players, min_games)}"
            f"</section>")


CSS = """
body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  max-width: 900px; margin: 0 auto; padding: 24px 16px 64px; color: #1f2328;
  line-height: 1.5; }
h1 { font-size: 2em; margin-bottom: 0; }
h2 { border-bottom: 1px solid #d0d7de; padding-bottom: 6px; margin-top: 40px; }
h3 { margin-top: 28px; }
.subtitle { color: #656d76; margin-top: 4px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 15px; }
th, td { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; }
th { background: #f6f8fa; }
td:nth-child(n+3) { text-align: right; }
tr.ill td { background: #fff8e6; font-weight: 600; }
.leaders { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
@media (max-width: 700px) { .leaders { grid-template-columns: 1fr; } }
.note { color: #656d76; font-size: 14px; }
.warn { background: #fff8e6; border: 1px solid #e3b341; padding: 10px 14px;
  border-radius: 6px; }
footer { margin-top: 48px; color: #656d76; font-size: 14px;
  border-top: 1px solid #d0d7de; padding-top: 16px; }
"""

SECTIONS = "\n".join(season_section(s) for s in SEASONS)

PAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RonPom: college basketball ratings</title>
<style>{CSS}</style>
</head>
<body>
<h1>RonPom</h1>
<p class="subtitle">College basketball ratings in the style of KenPom,
built from free ESPN data. Adjusted offense and defense per 100
possessions, solved properly (damped Gauss-Seidel), with a
league-average prior until last season's ratings are wired in.</p>

{SECTIONS}

<section><h2>How to read this</h2>
<p><strong>AdjO / AdjD</strong>: points scored and allowed per 100
possessions, adjusted for opponent. <strong>Net</strong> is AdjO minus
AdjD. <strong>AdjT</strong> is adjusted tempo, possessions per 40
minutes.</p>
<p><strong>ORtg</strong> (players) is a simplified approximation:
points per 100 possessions used, with no assist credit, so it
underrates playmakers. Read it with %Poss. <strong>RPR</strong> is
RonPom's own single-number player rating, not KenPom's proprietary
kPOY. Leaderboards only include players with at least 40% of their
team's minutes, so a two-minute cameo cannot top the list.</p>
<p><strong>Honest limits</strong>: 2026-27 is two games per team, so
its order is mostly noise. The 2024-25 and 2025-26 seasons are full
seasons. No KenPom data was used or scraped; his published rankings
are only a benchmark to compare against.</p></section>

<footer>
<p>Data: ESPN public scoreboard and box scores. Code and full CSVs:
<a href="{REPO}">RD3-LIL/RonPom on GitHub</a>. Built Nov 10, 2026.
Not affiliated with KenPom.</p>
</footer>
</body>
</html>
"""

out = HERE / "index.html"
out.write_text(PAGE)
print(f"Wrote {out}: {len(PAGE)} bytes")
