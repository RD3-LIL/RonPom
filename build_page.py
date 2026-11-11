"""Build the College Ratings GitHub Pages site (index.html) from the CSVs.

Reads data/ratings_<season>.csv and data/players_<season>.csv, plus
W-L records and conference ids from data/games_<season>.json, and
writes a static index.html at the repo root. No network, no build
step, no dependencies beyond the standard library. Re-run after
regenerating the CSVs.

Format: a KenPom-style dense ratings table is the centerpiece of
each season section, all teams, rank / team / conference / W-L /
AdjO / AdjD / Net / AdjT / Luck / SOS / NCSOS, with click-to-sort
columns, a team
filter, and conference filter tabs. A sticky top nav links to
each season, the player leaders, the top players, and the
predictions. Clicking a team row expands that team's game log
and roster for the season; clicking a team name opens that
team's own page (teams/<slug>.html) with its ratings, game
logs, rosters, and upcoming games for every season it played
in. A separate top-players section lists the top 150 players
of 2026-27 by RPR, sortable and filterable. The look is our own
(plain typography, no KenPom branding, colors, logos, or text);
only the table shape and column set are in that spirit.

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
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
DATA = HERE / "data"
RAW_SUMMARY = DATA / "raw" / "summary"
SEASONS = ["2024-25", "2025-26", "2026-27"]
# Display order: current season first, then the full seasons.
DISPLAY_SEASONS = ["2026-27", "2025-26", "2024-25"]
PREDICTIONS_CSV = DATA / "predictions_2026_11_11.csv"
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


def team_slug(name):
    """Team name -> stable URL slug for teams/<slug>.html.

    Lowercase, accents stripped (Jose, not Jos), apostrophes
    dropped, every other non-alphanumeric run becomes one
    hyphen. All 366 rated teams map to unique slugs; the
    builder fails loudly on a collision rather than letting
    one team's page overwrite another's.
    """
    norm = unicodedata.normalize("NFKD", name)
    ascii_name = norm.encode("ascii", "ignore").decode("ascii")
    s = ascii_name.lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


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


def season_game_logs(season):
    """(team_names, logs) for the expandable game-log panels.

    Same game set as the ratings (played, D1 vs D1, boxscore
    present). team_names is the sorted list of team names in
    that set; logs maps a team's index in that list to a list
    of [date, opponent index, venue, points for, points
    against], in date order. Venue is H, A, or N (neutral).
    Opponents are indices, not names, to keep the embedded
    JSON compact: all three seasons together add about 650 KB.
    """
    games = [g for g in season_games(season)
             if not (g["home_score"] == 0 and g["away_score"] == 0)
             and is_d1_game(g) and not g.get("stats_missing")]
    names = sorted({g["home"] for g in games}
                   | {g["away"] for g in games})
    idx = {name: i for i, name in enumerate(names)}
    logs = {i: [] for i in range(len(names))}
    for g in sorted(games, key=lambda x: (x["date"], x["event_id"])):
        for side, (team, opp, pts, opp_pts) in enumerate((
                (g["home"], g["away"], g["home_score"], g["away_score"]),
                (g["away"], g["home"], g["away_score"], g["home_score"]))):
            if g.get("neutral_site"):
                venue = "N"
            else:
                venue = "H" if side == 0 else "A"
            logs[idx[team]].append(
                [g["date"], idx[opp], venue, pts, opp_pts])
    return names, logs


def season_rosters(season, rated_teams):
    """(team -> roster) for the expandable detail panels.

    One compact list per team: [name, position, gp, pts_pg, ortg,
    poss_pct, min_pct, rpr], sorted by minutes descending.
    2026-27 embeds every player who appeared, all teams in the
    CSV. Older seasons embed rotation players only (%Min >= 20)
    on rated (D1) teams: rosters are only reachable by clicking
    a team row, and only rated teams have rows, so players on
    unrated non-D1 opponents would be dead weight in the page.
    The full profiles stay in the linked players CSV either way.
    """
    players = read_csv(DATA / f"players_{season.replace('-', '_')}.csv")
    by_team = {}
    for p in players:
        if season != "2026-27":
            if p["team"] not in rated_teams:
                continue
            if not p["min_pct"] or float(p["min_pct"]) < 20:
                continue
        by_team.setdefault(p["team"], []).append(p)
    out = {}
    for team, lst in by_team.items():
        lst.sort(key=lambda p: float(p["min"]), reverse=True)
        out[team] = [[p["name"], p["position"], int(p["gp"]),
                      float(p["pts_pg"]),
                      float(p["ortg"]) if p["ortg"] else None,
                      float(p["poss_pct"]) if p["poss_pct"] else None,
                      float(p["min_pct"]) if p["min_pct"] else None,
                      float(p["rpr"]) if p["rpr"] else None]
                     for p in lst]
    return out


def top_players_section():
    """Full top-150 players table for 2026-27, by RPR.

    Same filters as the 2026-27 leader tables: min 2 GP, 40% of
    team minutes. Sortable and filterable like the team tables
    (same th[data-t] / td[data-v] pattern). Team names link to
    that team's row in the 2026-27 ratings table.
    """
    players = read_csv(DATA / "players_2026_27.csv")
    qualified = [p for p in players
                 if int(p["gp"]) >= 2 and p["rpr"]
                 and p["min_pct"] and float(p["min_pct"]) >= 40]
    top = sorted(qualified, key=lambda p: float(p["rpr"]),
                 reverse=True)[:150]

    def num(v, disp):
        return (f"<td data-v=\"{v}\">{disp}</td>" if v not in (None, "")
                else "<td data-v=\"0\">&mdash;</td>")

    out = ["<section id=\"top-players\"><h2>Top players</h2>",
           "<p>Top 150 players of 2026-27 by RPR. Minimum 2 games "
           "and 40% of team minutes, same as the leader tables. "
           "Click a column header to sort; the filter box searches "
           "player names. Click a team name to open that team's "
           "own page.</p>",
           "<input class=\"filter\" type=\"search\" "
           "placeholder=\"Filter players...\" data-table=\"top-players\">",
           "<table class=\"ratings\" id=\"top-players\">"
           "<thead><tr>"
           "<th data-t=\"num\">Rk</th>"
           "<th data-t=\"text\">Player</th>"
           "<th data-t=\"text\">Team</th>"
           "<th data-t=\"text\">Pos</th>"
           "<th data-t=\"num\">GP</th>"
           "<th data-t=\"num\">PPG</th>"
           "<th data-t=\"num\">ORtg</th>"
           "<th data-t=\"num\">%Poss</th>"
           "<th data-t=\"num\">%Min</th>"
           "<th data-t=\"num\">RPR</th>"
           "</tr></thead><tbody>"]
    for rank, p in enumerate(top, 1):
        pos = p["position"] if p["position"] not in ("", "NA") else ""
        out.append(
            f"<tr>"
            f"<td data-v=\"{rank}\">{rank}</td>"
            f"<td data-v=\"{html.escape(p['name'].lower())}\">"
            f"{html.escape(p['name'])}</td>"
            f"<td data-v=\"{html.escape(p['team'].lower())}\">"
            f"<a href=\"teams/{team_slug(p['team'])}.html\">"
            f"{html.escape(p['team'])}</a></td>"
            f"<td data-v=\"{html.escape(pos.lower())}\">"
            f"{html.escape(pos) if pos else '&mdash;'}</td>"
            f"<td data-v=\"{p['gp']}\">{p['gp']}</td>"
            f"{num(p['pts_pg'], p['pts_pg'])}"
            f"{num(p['ortg'], p['ortg'])}"
            f"{num(p['poss_pct'], p['poss_pct'])}"
            f"{num(p['min_pct'], p['min_pct'])}"
            f"{num(p['rpr'], p['rpr'])}"
            f"</tr>")
    out.append("</tbody></table>")
    out.append(
        "<p class=\"note\">ORtg is approximate (no assist credit); "
        "read it with %Poss. RPR is our own single-number rating, "
        "not KenPom's proprietary kPOY. Full profiles in "
        "<a href=\"data/players_2026_27.csv\">players_2026_27.csv</a>."
        "</p></section>")
    return "\n".join(out)


def team_table(season, rows, records, conf_names, log_idx):
    tid = season.replace("-", "_")
    confs = sorted({conf_names.get(r["team"], "") for r in rows} - {""})
    tabs = [f"<div class=\"conftabs\" data-table=\"teams-{tid}\">"
            "<button class=\"conf-tab active\" data-conf=\"\">All</button>"]
    for c in confs:
        tabs.append(f"<button class=\"conf-tab\" "
                    f"data-conf=\"{html.escape(c.lower())}\">"
                    f"{html.escape(c)}</button>")
    tabs.append("</div>")
    out = ["\n".join(tabs),
           f"<input class=\"filter\" type=\"search\" "
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
               "<th data-t=\"num\">Luck</th>"
               "<th data-t=\"num\">SOS</th>"
               "<th data-t=\"num\">NCSOS</th>"
               "</tr></thead><tbody>")
    for r in rows:
        w, l = records.get(r["team"], [0, 0])
        conf = conf_names.get(r["team"], "")
        cls = ("team ill" if r["team"] == "Illinois Fighting Illini"
               else "team")
        out.append(
            f"<tr class=\"{cls}\" data-conf=\"{html.escape(conf.lower())}\" "
            f"data-season=\"{season}\" data-tidx=\"{log_idx.get(r['team'], '')}\">"
            f"<td data-v=\"{r['rank']}\">{r['rank']}</td>"
            f"<td data-v=\"{html.escape(r['team'].lower())}\">"
            f"<a class=\"team-page-link\" "
            f"href=\"teams/{team_slug(r['team'])}.html\">"
            f"{html.escape(r['team'])}</a></td>"
            f"<td data-v=\"{html.escape(conf.lower())}\">"
            f"{html.escape(conf)}</td>"
            f"<td data-v=\"{w * 100 - l}\">{w}-{l}</td>"
            f"<td data-v=\"{r['adj_o']}\">{r['adj_o']}</td>"
            f"<td data-v=\"{r['adj_d']}\">{r['adj_d']}</td>"
            f"<td class=\"net\" data-v=\"{r['net']}\">{r['net']}</td>"
            f"<td data-v=\"{r['adj_t']}\">{r['adj_t']}</td>"
            f"<td data-v=\"{r['luck']}\">"
            f"{float(r['luck']):+.3f}</td>"
            f"<td data-v=\"{r['sos']}\">{r['sos']}</td>"
            f"<td data-v=\"{r['ncsos'] or '0'}\">"
            f"{r['ncsos'] or '-'}</td></tr>")
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
    log_names, log_entries = season_game_logs(season)
    LOGS[season] = {"teams": log_names, "logs": log_entries}
    ROSTERS[season] = season_rosters(
        season, {r["team"] for r in ratings})
    log_idx = {name: i for i, name in enumerate(log_names)}
    LOG_IDX[season] = log_idx
    for r in ratings:
        TEAM_SEASONS.setdefault(r["team"], {})[season] = {
            "row": r,
            "record": records.get(r["team"], [0, 0]),
            "conf": conf_names.get(r["team"], ""),
        }
    tid = season.replace("-", "_")
    warn = ""
    if season == "2026-27":
        warn = ("<p class=\"warn\">Early season: 2-3 games per team. "
                "The ratings start from last season's ratings faded by "
                "returning minutes, so the top of the table is still "
                "mostly blowout noise, not a real ranking.</p>")
    # 2026-27 has at most 2-3 games per player, so the usual
    # 20-game floor would leave the leaders tables empty.
    min_games = 2 if season == "2026-27" else 20
    leaders = player_leaders(season, players, min_games)
    if season == "2026-27":
        # The nav's Players link lands on the current season's
        # leaders; older seasons keep their own leaders inline.
        leaders = f"<div id=\"players\">{leaders}</div>"
    return (f"<section id=\"season-{tid}\"><h2>{season}</h2>{warn}"
            f"<p>{len(ratings)} teams rated, {len(players)} players. "
            f"Click a column header to sort. Click a team name for "
            f"that team's own page, or a team row to see its game "
            f"log and roster here.</p>"
            f"<h3>Team ratings</h3>"
            f"{team_table(season, ratings, records, conf_names, log_idx)}"
            f"<h3>Player leaders</h3>"
            f"{leaders}"
            f"</section>")


def fmt_tipoff(tipoff, date_str):
    """'Wed 06:00 PM' in Chicago time, or the date if unparsable."""
    try:
        dt = datetime.fromisoformat(tipoff.replace("Z", "+00:00"))
        return dt.astimezone(ZoneInfo("America/Chicago")).strftime(
            "%a %I:%M %p")
    except (ValueError, TypeError):
        return date_str


def predictions_section():
    """Upcoming-game spreads from predict.py, if the file exists.

    Reads data/predictions_2026_11_11.csv (71 games, Nov 11-13).
    If no predictions file has been generated yet, the section
    is a short note instead, so the nav link still lands.
    """
    if not PREDICTIONS_CSV.exists():
        return ("<section id=\"predictions\"><h2>Predictions</h2>"
                "<p>Upcoming-game spreads come from predict.py, which "
                "recomputes them from the current ratings. No "
                "predictions file has been generated yet.</p></section>")
    rows = read_csv(PREDICTIONS_CSV)
    rows.sort(key=lambda r: (r["date"], r["tipoff"] or ""))
    out = ["<section id=\"predictions\"><h2>Predictions</h2>",
           "<p>Predicted spreads for the next three days, generated "
           "Nov 11 by predict.py from the 2026-27 ratings: "
           "model-consistent margin plus 4.69 home court (none on "
           "neutral floors), win probability from the cross-fitted "
           "logistic. The market line is ESPN's when one is out yet; "
           "lines move, and some of these games may already have "
           "tipped. The win/loss picks behind these spreads are "
           "backtested; the spread magnitudes are not.</p>",
           "<table class=\"preds\"><thead><tr><th>Tip-off</th>"
           "<th>Matchup</th><th>Predicted spread</th>"
           "<th>Home win%</th><th>Market</th><th>Edge</th>"
           "</tr></thead><tbody>"]
    for r in rows:
        tip = fmt_tipoff(r["tipoff"], r["date"])
        matchup = f"{r['away_short']} @ {r['home_short']}"
        if r["neutral_site"] == "True":
            matchup += " (N)"
        market = (f"{float(r['market_spread']):+.1f}"
                  if r["market_spread"] else "-")
        edge = (f"{float(r['edge']):+.1f}" if r["edge"] else "-")
        out.append(f"<tr><td>{tip}</td><td>{html.escape(matchup)}</td>"
                   f"<td>{html.escape(r['spread'])}</td>"
                   f"<td>{float(r['home_win_prob']) * 100:.1f}%</td>"
                   f"<td>{market}</td><td>{edge}</td></tr>")
    out.append("</tbody></table>")
    out.append(f"<p class=\"note\">{len(rows)} games, Nov 11-13. "
               "Edge is the model home margin minus the market's "
               "implied home margin: positive means the model likes "
               "the home team more than the market does.</p></section>")
    return "\n".join(out)


def team_page_html(team, slug_by_team, upcoming):
    """One team's full page, as an HTML string.

    slug_by_team maps every rated team name to its slug, so
    game-log opponents link to their own pages too. upcoming
    is the list of predictions rows for this team (possibly
    empty). Uses the same CSS as the index page, so the team
    pages look like part of the same site.
    """
    seasons_data = TEAM_SEASONS[team]
    conf = ""
    for s in DISPLAY_SEASONS:
        if s in seasons_data and seasons_data[s]["conf"]:
            conf = seasons_data[s]["conf"]
            break
    parts = [f"<h1>{html.escape(team)}</h1>",
             f"<p class=\"subtitle\">"
             f"{html.escape(conf) if conf else 'College basketball'}"
             f" &middot; <a href=\"../index.html\">&larr; College "
             f"Ratings</a></p>"]
    for season in DISPLAY_SEASONS:
        if season not in seasons_data:
            continue
        d = seasons_data[season]
        r = d["row"]
        w, l = d["record"]
        parts.append(f"<section><h2>{season}</h2>")
        parts.append(
            f"<p>Net rank #{r['rank']} &middot; AdjO {r['adj_o']} "
            f"&middot; AdjD {r['adj_d']} &middot; Net {r['net']} "
            f"&middot; AdjT {r['adj_t']} &middot; Luck "
            f"{float(r['luck']):+.3f} &middot; SOS {r['sos']} "
            f"&middot; NCSOS {r['ncsos'] or '-'} &middot; {w}-{l} "
            f"(D1 games)</p>")
        entry = LOGS.get(season)
        tidx = LOG_IDX.get(season, {}).get(team)
        if entry is not None and tidx is not None:
            games = entry["logs"].get(tidx, [])
            names = entry["teams"]
            parts.append("<h3>Game log</h3>"
                         '<table class="gamelog"><thead><tr><th>Date</th>'
                         "<th>Opponent</th><th>Venue</th><th>Result</th>"
                         "<th>Score</th></tr></thead><tbody>")
            for g in games:
                opp = names[g[1]]
                opp_html = html.escape(opp)
                if opp in slug_by_team:
                    opp_html = (f"<a href=\"{slug_by_team[opp]}.html\">"
                                f"{opp_html}</a>")
                f_pts, a_pts = g[3], g[4]
                parts.append(
                    f"<tr><td>{g[0][4:6]}/{g[0][6:8]}</td>"
                    f"<td>{opp_html}</td><td>{g[2]}</td>"
                    f"<td>{'W' if f_pts > a_pts else 'L'}</td>"
                    f"<td>{f_pts}-{a_pts}</td></tr>")
            parts.append("</tbody></table>")
        else:
            parts.append("<p>No game log for this season.</p>")
        roster = (ROSTERS.get(season) or {}).get(team)
        parts.append("<h3>Roster</h3>")
        if roster:
            parts.append('<table class="roster"><thead><tr><th>Player</th>'
                         "<th>Pos</th><th>GP</th><th>PPG</th><th>ORtg</th>"
                         "<th>%Poss</th><th>%Min</th><th>RPR</th>"
                         "</tr></thead><tbody>")
            for p in roster:
                pos = (p[1] if p[1] not in ("", "NA", None)
                       else "&mdash;")
                cells = [html.escape(p[0]), pos, str(p[2])]
                for v in p[3:]:
                    cells.append("\u2014" if v is None else f"{v:.1f}")
                parts.append("<tr>" + "".join(
                    f"<td>{c}</td>" for c in cells) + "</tr>")
            parts.append("</tbody></table>")
            parts.append('<p class="note">Sorted by minutes. ORtg is '
                         "approximate (no assist credit); RPR is our own "
                         "rating, not KenPom\u2019s kPOY."
                         + ("" if season == "2026-27"
                            else " Rotation players only (%Min \u2265 20); "
                            "full profiles in the players CSV.")
                         + "</p>")
        else:
            parts.append("<p>No roster data for this season.</p>")
        parts.append("</section>")
    if upcoming:
        parts.append("<section><h2>Upcoming games</h2>"
                     "<p>Predicted spreads for this team from the "
                     "predictions file (Nov 11-13). Lines move, and "
                     "some of these games may already have tipped. "
                     "The win/loss picks behind these spreads are "
                     "backtested; the spread magnitudes are not.</p>"
                     '<table class="preds"><thead><tr><th>Tip-off</th>'
                     "<th>Opponent</th><th>Venue</th>"
                     "<th>Predicted spread</th><th>Team win%</th>"
                     "<th>Market</th><th>Edge</th>"
                     "</tr></thead><tbody>")
        for r in sorted(upcoming,
                        key=lambda x: (x["date"], x["tipoff"] or "")):
            is_home = r["home"] == team
            opp = r["away_short"] if is_home else r["home_short"]
            opp_full = r["away"] if is_home else r["home"]
            if r["neutral_site"] == "True":
                venue = "N"
            else:
                venue = "H" if is_home else "A"
            win_prob = float(r["home_win_prob"])
            team_win = win_prob if is_home else 1 - win_prob
            edge = float(r["edge"]) if r["edge"] else None
            edge_team = (edge if is_home else
                         (-edge if edge is not None else None))
            market = (f"{float(r['market_spread']):+.1f}"
                      if r["market_spread"] else "-")
            opp_html = html.escape(opp)
            if opp_full in slug_by_team:
                opp_html = (f"<a href=\"{slug_by_team[opp_full]}.html\">"
                            f"{opp_html}</a>")
            parts.append(
                f"<tr><td>{fmt_tipoff(r['tipoff'], r['date'])}</td>"
                f"<td>{opp_html}</td><td>{venue}</td>"
                f"<td>{html.escape(r['spread'])}</td>"
                f"<td>{team_win * 100:.1f}%</td>"
                f"<td>{market}</td>"
                f"<td>{f'{edge_team:+.1f}' if edge_team is not None else '-'}</td></tr>")
        parts.append("</tbody></table>"
                     '<p class="note">Market is the home team\u2019s line. '
                     "Edge is from this team\u2019s perspective: positive "
                     "means the model likes this team more than the "
                     "market does.</p></section>")
    body = "\n".join(parts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(team)} | College Ratings</title>
<style>{CSS}</style>
</head>
<body>
{body}
<footer>
<p>Data: ESPN public scoreboard and box scores. Code and full CSVs:
<a href="{REPO}">RD3-LIL/RonPom on GitHub</a>. Built {BUILT}.
Not affiliated with KenPom.</p>
</footer>
</body>
</html>
"""


def build_team_pages():
    """Write teams/<slug>.html for every rated team.

    Returns (page count, total bytes). Fails loudly on a slug
    collision. Deletes stale teams/*.html files not written
    this run, so a renamed team cannot leave a dead page.
    """
    teams_dir = HERE / "teams"
    teams_dir.mkdir(exist_ok=True)
    upcoming = {}
    if PREDICTIONS_CSV.exists():
        for r in read_csv(PREDICTIONS_CSV):
            for key in (r["home"], r["away"]):
                upcoming.setdefault(key, []).append(r)
    seen = {}
    for team in TEAM_SEASONS:
        s = team_slug(team)
        if s in seen:
            raise SystemExit(f"slug collision: {team!r} and "
                             f"{seen[s]!r} both map to {s!r}")
        seen[s] = team
    slug_by_team = {team: s for s, team in seen.items()}
    written = set()
    total = 0
    for team in sorted(TEAM_SEASONS):
        text = team_page_html(team, slug_by_team,
                              upcoming.get(team, []))
        path = teams_dir / f"{slug_by_team[team]}.html"
        path.write_text(text)
        written.add(path.name)
        total += len(text.encode("utf-8"))
    for stale in teams_dir.glob("*.html"):
        if stale.name not in written:
            stale.unlink()
    return len(written), total


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
nav.topnav { position: sticky; top: 0; z-index: 20; background: #fff;
  border-bottom: 1px solid #d0d7de; padding: 8px 0; display: flex;
  gap: 4px; flex-wrap: wrap; }
nav.topnav a { padding: 4px 10px; border-radius: 6px; color: #0969da;
  text-decoration: none; font-weight: 600; font-size: 14px; }
nav.topnav a:hover { background: #eaeef2; }
section, div[id] { scroll-margin-top: 54px; }
table.ratings { font-size: 13px; }
table.ratings th, table.ratings td { padding: 3px 8px; }
table.ratings thead th { position: sticky; top: 40px; cursor: pointer;
  user-select: none; }
table.ratings thead th:hover { background: #eaeef2; }
table.ratings thead th.sorted-asc::after { content: " \\25B2"; }
table.ratings thead th.sorted-desc::after { content: " \\25BC"; }
table.ratings tbody tr:nth-child(even) td { background: #f6f8fa; }
table.ratings tbody tr.team { cursor: pointer; }
table.ratings tbody tr.team:hover td { background: #eef4ff; }
table.ratings td:nth-child(n+4) { text-align: right; font-variant-numeric: tabular-nums; }
table.ratings td.net { font-weight: 700; }
tr.ill td { background: #fff8e6 !important; font-weight: 600; }
tr.detail td { background: #fff; padding: 10px 14px; cursor: default; }
.detail-box { margin-bottom: 8px; }
table.gamelog { font-size: 13px; width: auto; margin: 0; }
table.gamelog th, table.gamelog td { padding: 2px 10px; }
table.gamelog td:nth-child(n+3) { text-align: right; }
.detail-box h4 { margin: 14px 0 4px; }
table.roster { font-size: 13px; width: auto; margin: 0; }
table.roster th, table.roster td { padding: 2px 10px; }
table.roster td:nth-child(n+3) { text-align: right; }
a.team-link, a.team-page-link { color: #0969da; text-decoration: none; }
a.team-link:hover, a.team-page-link:hover { text-decoration: underline; }
.conftabs { display: flex; flex-wrap: wrap; gap: 4px; margin: 8px 0 4px; }
button.conf-tab { padding: 3px 9px; font-size: 12px;
  border: 1px solid #d0d7de; border-radius: 999px; background: #fff;
  cursor: pointer; }
button.conf-tab.active { background: #1f2328; color: #fff;
  border-color: #1f2328; }
table.preds { font-size: 14px; }
table.preds td:nth-child(n+3) { text-align: right;
  font-variant-numeric: tabular-nums; }
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
// Ratings tables: click-to-sort, text filter, conference tabs,
// and click a team row to expand its game log (GAME_LOGS is
// embedded in the page by the builder). Plain script, no
// network, no dependencies. Numeric columns sort on the
// data-v value; team and conference sort as text; W-L sorts on
// wins first (data-v is wins*100 - losses).
function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function fmt1(v) {
  return (v === null || v === undefined) ? "\u2014" : v.toFixed(1);
}
function closeDetails(table) {
  table.querySelectorAll("tbody tr.detail").forEach(function (d) {
    d.remove();
  });
}
function applyFilter(table) {
  var q = table._q || "";
  var conf = table._conf || "";
  table.querySelectorAll("tbody tr:not(.detail)").forEach(function (r) {
    var team = r.cells[1].textContent.toLowerCase();
    var ok = (q === "" || team.indexOf(q) !== -1)
      && (conf === "" || r.dataset.conf === conf);
    r.style.display = ok ? "" : "none";
  });
}
function openDetail(table, row) {
  var next = row.nextElementSibling;
  if (next && next.classList.contains("detail")) {
    next.remove();
    return;
  }
  closeDetails(table);
  var entry = GAME_LOGS[row.dataset.season];
  if (!entry || row.dataset.tidx === "") return;
  var games = entry.logs[row.dataset.tidx] || [];
  var teams = entry.teams;
  var c = row.cells;
  var html = '<div class="detail-box"><strong>' + esc(c[1].textContent)
    + '</strong> &mdash; AdjO ' + c[4].textContent + ' &middot; AdjD '
    + c[5].textContent + ' &middot; Net ' + c[6].textContent
    + ' &middot; AdjT ' + c[7].textContent + ' &middot; '
    + c[3].textContent + ' (D1 games)</div>'
    + '<table class="gamelog"><thead><tr><th>Date</th><th>Opponent</th>'
    + '<th>Venue</th><th>Result</th><th>Score</th></tr></thead><tbody>';
  games.forEach(function (g) {
    var f = g[3], a = g[4];
    html += "<tr><td>" + g[0].slice(4, 6) + "/" + g[0].slice(6, 8)
      + "</td><td>" + esc(teams[g[1]]) + "</td><td>" + g[2]
      + "</td><td>" + (f > a ? "W" : "L") + "</td><td>"
      + f + "-" + a + "</td></tr>";
  });
  html += "</tbody></table>";
  var roster = (ROSTERS[row.dataset.season] || {})[c[1].textContent];
  if (roster && roster.length) {
    html += "<h4>Roster</h4>"
      + '<table class="roster"><thead><tr><th>Player</th><th>Pos</th>'
      + "<th>GP</th><th>PPG</th><th>ORtg</th><th>%Poss</th>"
      + "<th>%Min</th><th>RPR</th></tr></thead><tbody>";
    roster.forEach(function (p) {
      html += "<tr><td>" + esc(p[0]) + "</td><td>"
        + ((p[1] && p[1] !== "NA") ? esc(p[1]) : "\u2014")
        + "</td><td>" + p[2] + "</td><td>" + fmt1(p[3]) + "</td><td>"
        + fmt1(p[4]) + "</td><td>" + fmt1(p[5]) + "</td><td>"
        + fmt1(p[6]) + "</td><td>" + fmt1(p[7]) + "</td></tr>";
    });
    html += "</tbody></table>"
      + '<p class="note">Sorted by minutes. ORtg is approximate '
      + "(no assist credit); RPR is our own rating, not KenPom\u2019s "
      + "kPOY."
      + (row.dataset.season === "2026-27"
        ? ""
        : " Rotation players only (%Min \u2265 20); full profiles "
        + "in the players CSV.")
      + "</p>";
  }
  var tr = document.createElement("tr");
  tr.className = "detail";
  var td = document.createElement("td");
  td.colSpan = 8;
  td.innerHTML = html;
  tr.appendChild(td);
  row.after(tr);
}
document.querySelectorAll("table.ratings").forEach(function (table) {
  var headers = table.querySelectorAll("thead th");
  headers.forEach(function (th, i) {
    th.addEventListener("click", function () {
      closeDetails(table);
      var asc = !th.classList.contains("sorted-asc");
      headers.forEach(function (h) {
        h.classList.remove("sorted-asc", "sorted-desc");
      });
      th.classList.add(asc ? "sorted-asc" : "sorted-desc");
      var rows = Array.from(table.querySelectorAll("tbody tr:not(.detail)"));
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
  table.querySelectorAll("tbody tr.team").forEach(function (row) {
    row.addEventListener("click", function (e) {
      // The team name is a link to the team page; let it go
      // there instead of toggling the detail panel.
      if (e.target.closest("a")) return;
      openDetail(table, row);
    });
  });
});
document.querySelectorAll("input.filter").forEach(function (input) {
  input.addEventListener("input", function () {
    var table = document.getElementById(input.dataset.table);
    closeDetails(table);
    table._q = input.value.trim().toLowerCase();
    applyFilter(table);
  });
});
document.querySelectorAll(".conftabs").forEach(function (bar) {
  bar.addEventListener("click", function (e) {
    var btn = e.target.closest("button.conf-tab");
    if (!btn) return;
    bar.querySelectorAll("button").forEach(function (b) {
      b.classList.remove("active");
    });
    btn.classList.add("active");
    var table = document.getElementById(bar.dataset.table);
    closeDetails(table);
    table._conf = btn.dataset.conf;
    applyFilter(table);
  });
});
// Team names in the ratings tables and the top-players table
// are plain links to teams/<slug>.html, so they need no
// handler here. Clicking a team row anywhere else still opens
// the inline detail panel (see the guard in the row handler
// above, which lets link clicks through).
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

# Game logs, rosters, and per-season team data, filled in by
# season_section as each section is built. TEAM_SEASONS maps a
# team name to {season: {"row": ratings CSV row, "record":
# (wins, losses), "conf": conference label}}; LOG_IDX maps a
# season to {team name: index into that season's log teams}.
LOGS = {}
ROSTERS = {}
LOG_IDX = {}
TEAM_SEASONS = {}

SECTIONS = "\n".join(season_section(s, CONF_BY_ID)
                     for s in DISPLAY_SEASONS)
LOGS_JSON = json.dumps(LOGS, separators=(",", ":"))
ROSTERS_JSON = json.dumps(ROSTERS, separators=(",", ":"))
TOP_PLAYERS = top_players_section()
PREDICTIONS = predictions_section()
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

<nav class="topnav">
<a href="#season-2026_27">2026-27</a>
<a href="#season-2025_26">2025-26</a>
<a href="#season-2024_25">2024-25</a>
<a href="#players">Players</a>
<a href="#top-players">Top players</a>
<a href="#predictions">Predictions</a>
<a href="#how-to-read">How to read this</a>
</nav>

{SECTIONS}

{TOP_PLAYERS}

{PREDICTIONS}

<section id="how-to-read"><h2>How to read this</h2>
<p><strong>Getting around</strong>: the bar at the top jumps to any
season, the player leaders, the top 150 players, or the
predictions. Conference tabs above each table filter to one
conference; the filter box searches team names. Click a team
name anywhere to open that team's own page, with its ratings,
game log, roster, and upcoming games for every season it
played in. Click a team row to see its game log and roster
for the season right here.</p>
<p><strong>AdjO / AdjD</strong>: points scored and allowed per 100
possessions, adjusted for opponent. <strong>Net</strong> is AdjO minus
AdjD, the same idea as KenPom's AdjEM. <strong>AdjT</strong> is
adjusted tempo, possessions per 40 minutes.
<strong>Conf</strong> is the ESPN conference abbreviation.
<strong>W-L</strong> is the record in the D1 games these ratings
are built from, so W+L equals GP; non-D1 games are excluded.</p>
<p><strong>Luck</strong>: actual winning percentage minus the
Pythagorean expected winning percentage from AdjO and AdjD
(exponent 11.5). Positive Luck means the record is better than
the play, usually close wins and blowout losses; negative means
the reverse. Ours is the Pythagorean version; KenPom's own Luck
uses a correlated-Gaussian method on per-game margins.
<strong>SOS</strong> is the average Net rating of a team's
opponents, positive means a harder schedule than average.
<strong>NCSOS</strong> is the same average over non-conference
games only, where a team chooses its difficulty.</p>
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
<script>var GAME_LOGS = {LOGS_JSON};</script>
<script>var ROSTERS = {ROSTERS_JSON};</script>
<script>{JS}</script>
</body>
</html>
"""

out = HERE / "index.html"
out.write_text(PAGE)
print(f"Wrote {out}: {len(PAGE)} bytes")

N_TEAM_PAGES, TEAM_PAGES_BYTES = build_team_pages()
print(f"Wrote {N_TEAM_PAGES} team pages in teams/: "
      f"{TEAM_PAGES_BYTES} bytes")
