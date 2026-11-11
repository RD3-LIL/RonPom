"""Build the College Ratings GitHub Pages site (index.html) from the CSVs.

Reads data/ratings_<season>.csv and data/players_<season>.csv, plus
W-L records and conference ids from data/games_<season>.json, and
writes a static index.html at the repo root. No network, no build
step, no dependencies beyond the standard library. Re-run after
regenerating the CSVs.

Format: a KenPom-style dense ratings table is the centerpiece of
each season section, all teams, rank / team / conference / W-L /
AdjO / AdjD / Net / AdjT, with click-to-sort columns and a team
filter. The look is our own (plain typography, no KenPom branding,
colors, logos, or text); only the table shape and column set are
in that spirit.

Where the columns come from:
- Conf: ESPN conference short names, read from the raw summary
  files on disk (header.competitions[0].groups). Conferences
  with no conference game in the data yet (the new Pac-12 in
  2026-27) fall back to a label derived from the ESPN slug
  (team.groups.slug, e.g. 'pac-12-conference' -> 'Pac-12').
- W-L: the record in the D1 games these ratings are built from,
  same filter as the solver (played, D1 vs D1, boxscore present).
  W+L equals GP for every team. Non-D1 games are excluded, and
  the table note says so.

Usage:
    python3 build_page.py
"""

import csv
import glob
import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
DATA = HERE / "data"
RAW_SUMMARY = DATA / "raw" / "summary"
SEASONS = ["2024-25", "2025-26", "2026-27"]
REPO = "https://github.com/RD3-LIL/RonPom"

# Fallback for the prototype games file, copied from solver.py.
# Full-season games files carry conference ids, so this never
# triggers there; it exists so the D1 filter matches the solver
# exactly if a file without conference fields is ever used.
NON_D1 = {
    "Framingham State Rams", "Regent Regent Royals",
    "Virginia Lynchburg Dragons", "Concordia Chicago Cougars",
    "Erskine Flying Fleet", "Christendom Crusaders",
    "Central College Dutch", "Blue Mountain Christian Toppers",
    "Webster Gorloks", "Bob Jones Bruins",
    "Champion Christian Tigers", "Saint Mary of the Woods Pomeroys",
    "West Coast Baptist Eagles", "Grace University Lancers",
    "Salish Kootenai Bison",
}

# Bound the conference scan so a bad day in the raw files cannot
# make the build hang. Coverage of the current data completes
# in under 1,000 files; 4,000 is headroom, not a target.
CONF_SCAN_CAP = 4000


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def is_d1_game(g):
    """Same D1 filter as solver.is_d1_game."""
    if "home_conf_id" in g or "away_conf_id" in g:
        return (g.get("home_conf_id") is not None
                and g.get("away_conf_id") is not None)
    return g["home"] not in NON_D1 and g["away"] not in NON_D1


def slug_label(slug):
    """ESPN conference slug -> short label.

    'pac-12-conference' -> 'Pac-12', 'patriot-league' ->
    'Patriot', 'conference-usa' -> 'CUSA'. Only used when a
    conference has no conference game in the raw summaries yet,
    so no display name is on disk.
    """
    if slug == "conference-usa":
        return "CUSA"
    for suffix in ("-conference", "-league"):
        if slug.endswith(suffix):
            slug = slug[: -len(suffix)]
            break
    # Title-case each word, but keep a numeric token attached
    # to the previous word with a hyphen: 'pac-12', not 'Pac 12'.
    parts = []
    for token in slug.split("-"):
        word = token.title()
        if token.isdigit() and parts:
            parts[-1] = parts[-1] + "-" + word
        else:
            parts.append(word)
    label = " ".join(parts)
    return (label.replace(" Usa", " USA").replace(" Acc", " ACC")
            .replace(" Sec", " SEC"))


def conf_map(needed_ids):
    """conf id -> short label, from raw ESPN summaries on disk.

    Primary source is competitions[0].groups (id, shortName) on
    conference games. Scans newest summaries first and stops
    once every needed id has a name, or when no new name has
    appeared in 1,500 files (the remaining ids have no
    conference game in the data, e.g. the new Pac-12 in
    2026-27, and fall back to their slug label). Slugs alone
    must not satisfy the stop condition: they are collected
    from every game, so they would end the scan before the
    names had a chance to accumulate. Returns (map, unmapped
    ids). Unmapped ids get a blank Conf cell rather than a
    guessed label.
    """
    names = {}
    slugs = {}
    files = sorted(glob.glob(str(RAW_SUMMARY / "*.json")), reverse=True)
    last_new = -1
    for i, path in enumerate(files[:CONF_SCAN_CAP]):
        try:
            with open(path) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        comp = (d.get("header", {}).get("competitions") or [{}])[0]
        groups = comp.get("groups")
        if groups and groups.get("id") and groups["id"] not in names:
            names[groups["id"]] = (groups.get("shortName")
                                   or groups.get("name"))
            last_new = i
        for c in comp.get("competitors", []):
            tg = (c.get("team") or {}).get("groups") or {}
            if tg.get("id") and tg.get("slug"):
                slugs.setdefault(tg["id"], tg["slug"])
        if needed_ids <= set(names):
            break
        if last_new >= 0 and i - last_new > 1500:
            break
    out = {}
    for cid in needed_ids:
        if cid in names:
            out[cid] = names[cid]
        elif cid in slugs:
            out[cid] = slug_label(slugs[cid])
    unmapped = sorted(needed_ids - set(out))
    return out, unmapped


def season_games(season):
    path = DATA / f"games_{season.replace('-', '_')}.json"
    return json.loads(path.read_text())


def season_records(season):
    """(W-L records, team -> conf id) for one season.

    Records use the solver's game set exactly (played, D1 vs D1,
    boxscore present), so W+L equals the GP in the ratings CSV.
    Conference ids are read from every game, including games
    against non-D1 opponents, since a team's conference does
    not depend on the opponent.
    """
    records = {}
    team_conf = {}
    for g in season_games(season):
        if g.get("home_conf_id"):
            team_conf.setdefault(g["home"], g["home_conf_id"])
        if g.get("away_conf_id"):
            team_conf.setdefault(g["away"], g["away_conf_id"])
        if g["home_score"] == 0 and g["away_score"] == 0:
            continue  # not played yet
        if not is_d1_game(g):
            continue
        if g.get("stats_missing"):
            continue
        winner = g["home"] if g["home_score"] > g["away_score"] else g["away"]
        loser = g["away"] if winner == g["home"] else g["home"]
        records.setdefault(winner, [0, 0])[0] += 1
        records.setdefault(loser, [0, 0])[1] += 1
    return records, team_conf


def team_table(season, rows, records, conf_names):
    tid = season.replace("-", "_")
    out = [f"<input class=\"filter\" type=\"search\" "
           f"placeholder=\"Filter teams...\" data-table=\"teams-{tid}\">"]
    out.append(f"<table class=\"ratings\" id=\"teams-{tid}\">"
               "<thead><tr>"
               "<th data-t=\"num\">Rk</th>"
               "<th data-t=\"text\">Team</th>"
               "<th data-t=\"text\">Conf</th>"
               "<th data-t=\"wl\">W-L</th>"
               "<th data-t=\"num\">AdjO</th>"
               "<th data-t=\"num\">AdjD</th>"
               "<th data-t=\"num\">Net</th>"
               "<th data-t=\"num\">AdjT</th>"
               "</tr></thead><tbody>")
    for r in rows:
        w, l = records.get(r["team"], [0, 0])
        conf = conf_names.get(r["team"], "")
        cls = (" class=\"ill\""
               if r["team"] == "Illinois Fighting Illini" else "")
        out.append(
            f"<tr{cls}>"
            f"<td data-v=\"{r['rank']}\">{r['rank']}</td>"
            f"<td data-v=\"{html.escape(r['team'].lower())}\">"
            f"{html.escape(r['team'])}</td>"
            f"<td data-v=\"{html.escape(conf.lower())}\">"
            f"{html.escape(conf)}</td>"
            f"<td data-v=\"{w * 100 - l}\">{w}-{l}</td>"
            f"<td data-v=\"{r['adj_o']}\">{r['adj_o']}</td>"
            f"<td data-v=\"{r['adj_d']}\">{r['adj_d']}</td>"
            f"<td class=\"net\" data-v=\"{r['net']}\">{r['net']}</td>"
            f"<td data-v=\"{r['adj_t']}\">{r['adj_t']}</td></tr>")
    out.append("</tbody></table>")
    out.append(
        f"<p class=\"note\">Full table above ({len(rows)} teams). "
        f"Download the CSV: <a href=\"data/ratings_"
        f"{season.replace('-', '_')}.csv\">ratings_"
        f"{season.replace('-', '_')}.csv</a>. W-L is the record in "
        f"the D1 games these ratings are built from; non-D1 games "
        f"are excluded, same as the ratings.</p>")
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


def season_section(season, conf_by_id):
    ratings = read_csv(DATA / f"ratings_{season.replace('-', '_')}.csv")
    players = read_csv(DATA / f"players_{season.replace('-', '_')}.csv")
    records, team_conf = season_records(season)
    conf_names = {team: conf_by_id.get(cid, "")
                  for team, cid in team_conf.items()}
    warn = ""
    if season == "2026-27":
        warn = ("<p class=\"warn\">Early season: 2-3 games per team. "
                "The ratings start from last season's ratings faded by "
                "returning minutes, so the top of the table is still "
                "mostly blowout noise, not a real ranking.</p>")
    # 2026-27 has at most 2-3 games per player, so the usual
    # 20-game floor would leave the leaders tables empty.
    min_games = 2 if season == "2026-27" else 20
    return (f"<section><h2>{season}</h2>{warn}"
            f"<p>{len(ratings)} teams rated, {len(players)} players. "
            f"Click a column header to sort.</p>"
            f"<h3>Team ratings</h3>"
            f"{team_table(season, ratings, records, conf_names)}"
            f"<h3>Player leaders</h3>"
            f"{player_leaders(season, players, min_games)}"
            f"</section>")


CSS = """
body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  max-width: 960px; margin: 0 auto; padding: 24px 16px 64px; color: #1f2328;
  line-height: 1.5; }
h1 { font-size: 2em; margin-bottom: 0; }
h2 { border-bottom: 1px solid #d0d7de; padding-bottom: 6px; margin-top: 40px; }
h3 { margin-top: 28px; }
.subtitle { color: #656d76; margin-top: 4px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; }
th { background: #f6f8fa; }
table.ratings { font-size: 13px; }
table.ratings th, table.ratings td { padding: 3px 8px; }
table.ratings thead th { position: sticky; top: 0; cursor: pointer;
  user-select: none; }
table.ratings thead th:hover { background: #eaeef2; }
table.ratings thead th.sorted-asc::after { content: " \\25B2"; }
table.ratings thead th.sorted-desc::after { content: " \\25BC"; }
table.ratings tbody tr:nth-child(even) td { background: #f6f8fa; }
table.ratings tbody tr:hover td { background: #eef4ff; }
table.ratings td:nth-child(n+4) { text-align: right; font-variant-numeric: tabular-nums; }
table.ratings td.net { font-weight: 700; }
tr.ill td { background: #fff8e6 !important; font-weight: 600; }
input.filter { padding: 6px 10px; font-size: 14px; width: 240px;
  border: 1px solid #d0d7de; border-radius: 6px; margin: 4px 0; }
.leaders { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.leaders table { font-size: 15px; }
.leaders td:nth-child(n+3) { text-align: right; }
@media (max-width: 700px) { .leaders { grid-template-columns: 1fr; } }
.note { color: #656d76; font-size: 14px; }
.warn { background: #fff8e6; border: 1px solid #e3b341; padding: 10px 14px;
  border-radius: 6px; }
footer { margin-top: 48px; color: #656d76; font-size: 14px;
  border-top: 1px solid #d0d7de; padding-top: 16px; }
"""

JS = """
// Click-to-sort on the ratings tables, and a team filter box.
// Plain script, no network, no dependencies. Numeric columns
// sort on the data-v value; team and conference sort as text;
// W-L sorts on wins first (data-v is wins*100 - losses).
document.querySelectorAll("table.ratings").forEach(function (table) {
  var headers = table.querySelectorAll("thead th");
  headers.forEach(function (th, i) {
    th.addEventListener("click", function () {
      var asc = !th.classList.contains("sorted-asc");
      headers.forEach(function (h) {
        h.classList.remove("sorted-asc", "sorted-desc");
      });
      th.classList.add(asc ? "sorted-asc" : "sorted-desc");
      var rows = Array.from(table.querySelectorAll("tbody tr"));
      var numeric = th.dataset.t === "num" || th.dataset.t === "wl";
      rows.sort(function (a, b) {
        var va = a.cells[i].dataset.v, vb = b.cells[i].dataset.v;
        var cmp = numeric ? (parseFloat(va) - parseFloat(vb))
          : (va < vb ? -1 : va > vb ? 1 : 0);
        return asc ? cmp : -cmp;
      });
      var body = table.querySelector("tbody");
      rows.forEach(function (r) { body.appendChild(r); });
    });
  });
});
document.querySelectorAll("input.filter").forEach(function (input) {
  input.addEventListener("input", function () {
    var q = input.value.trim().toLowerCase();
    var rows = document.getElementById(input.dataset.table)
      .querySelectorAll("tbody tr");
    rows.forEach(function (r) {
      var team = r.cells[1].textContent.toLowerCase();
      r.style.display = team.indexOf(q) === -1 ? "none" : "";
    });
  });
});
"""

# Conference ids needed across all three seasons, mapped once
# and shared by the sections.
needed_conf_ids = set()
for _s in SEASONS:
    for _g in season_games(_s):
        for _k in ("home_conf_id", "away_conf_id"):
            if _g.get(_k):
                needed_conf_ids.add(_g[_k])
CONF_BY_ID, CONF_UNMAPPED = conf_map(needed_conf_ids)
if CONF_UNMAPPED:
    print(f"WARNING: no label for conference ids {CONF_UNMAPPED}; "
          "those Conf cells are blank")
print(f"Conference map: {len(CONF_BY_ID)} ids "
      f"({', '.join(sorted(CONF_BY_ID.values()))})")

SECTIONS = "\n".join(season_section(s, CONF_BY_ID) for s in SEASONS)
BUILT = datetime.now(ZoneInfo("America/Chicago")).strftime("%B %-d, %Y")

PAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>College Ratings</title>
<style>{CSS}</style>
</head>
<body>
<h1>College Ratings</h1>
<p class="subtitle">College basketball ratings in the style of KenPom,
built from free ESPN data. Adjusted offense and defense per 100
possessions, solved properly (damped Gauss-Seidel), starting from
last season's ratings faded by returning minutes.</p>

{SECTIONS}

<section><h2>How to read this</h2>
<p><strong>AdjO / AdjD</strong>: points scored and allowed per 100
possessions, adjusted for opponent. <strong>Net</strong> is AdjO minus
AdjD, the same idea as KenPom's AdjEM. <strong>AdjT</strong> is
adjusted tempo, possessions per 40 minutes.
<strong>Conf</strong> is the ESPN conference abbreviation.
<strong>W-L</strong> is the record in the D1 games these ratings
are built from, so W+L equals GP; non-D1 games are excluded.</p>
<p><strong>ORtg</strong> (players) is a simplified approximation:
points per 100 possessions used, with no assist credit, so it
underrates playmakers. Read it with %Poss. <strong>RPR</strong> is
our own single-number player rating, not KenPom's proprietary
kPOY. Leaderboards only include players with at least 40% of their
team's minutes, so a two-minute cameo cannot top the list.</p>
<p><strong>Honest limits</strong>: 2026-27 is two to three games
per team, so its order is mostly noise. The 2024-25 and 2025-26
seasons are full seasons. No KenPom data was used or scraped; his
published rankings are only a benchmark to compare against.</p></section>

<footer>
<p>Data: ESPN public scoreboard and box scores. Code and full CSVs:
<a href="{REPO}">RD3-LIL/RonPom on GitHub</a>. Built {BUILT}.
Not affiliated with KenPom.</p>
</footer>
<script>{JS}</script>
</body>
</html>
"""

out = HERE / "index.html"
out.write_text(PAGE)
print(f"Wrote {out}: {len(PAGE)} bytes")
