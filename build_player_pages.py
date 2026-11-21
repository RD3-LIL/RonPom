"""Build one player profile page per player for the top 25 teams
of the College Ratings site (RonPom), in the style of the NBA
ratings player profiles.

Reads data/ratings_2026_27.csv (top 25 teams by Net),
data/players_2026_27.json (all 8,015 profiles, 2026-27 only),
and the raw ESPN summaries under data/raw/summary/ for a
per-player game log.

Writes players/<slug>.html for every player on a top-25 team
(354 players on the Nov 20 run) plus players/index.html, a
filterable directory of those profiles. No network, stdlib
only. Re-run after regenerating the ratings files; stale
players/*.html files are deleted.

Why top 25 only: all 8,015 players would be about 8,000 pages
and over 100 MB of HTML, far past what the GitHub snapshot
push route can carry in reasonable batches, and almost all of
them are bench players on teams nobody is following yet. The
top 25 is the set a reader actually wants profiles for, and
it is the same cut KenPom's own front page uses. If the cut
ever moves, change TOP_N below and rebuild; the builder
re-derives the team set from the ratings CSV every run, so
a team falling out of the top 25 drops its pages (stale
deletion) and a team entering gains them.

What a profile shows, and where it differs from the NBA
version (same site shape, college data):
- Bio: headshot, team, position, jersey. No age, height,
  weight, or class year: the roster pull (fetch_rosters.py)
  has not run yet, so those fields do not exist in the data
  and are not invented. The page says so.
- At a glance: RPR, PPG, RPG, APG, ORtg (approx), TS%, SHARP, each
  with its rank among ALL 8,015 players with a value for
  that stat (denominator shown). Ranks are competition ranks
  (1, 2, 2, 4). A small-sample note appears when a player is
  under 40% of team minutes or has played 2 or fewer games:
  those ranks are among every player who appeared, so a hot
  few games can rank high. (College teams have only about
  5 games so far, so the GP bar is 2, not 5 as in the NBA.)
- Season line: totals, per game, and per 40 (college games
  are 40 minutes, not 48, so per 40 is the college standard;
  there is no per-36 in this data).
- Shooting (FG/3P/FT/eFG/TS, raw only, no shrunk versions
  exist in this data) with bars against the league average,
  and a stacked bar for where the points come from
  (2s / 3s / FTs).
- RPR: a single number with its formula and scale. There is
  NO component breakdown in this data: college RPR is the
  v1 formula, (ORtg - 100) * possessions used per game / 100
  + 0.5 * (AST - TO) per game + (STL + BLK) per game
  + 0.25 * REB per game, uncentered (a star is about +6 to
  +10, an average rotation player about +1 to +3, below
  average about 0 or negative). The NBA site's RPR v1.2
  recenters the counting terms so an average player scores
  about 0; that recentering has not been applied here, so
  the two sites' RPRs are not on the same scale. The page
  says so instead of pretending they are.
- Playmaking / defense / rebounding, consistency (points
  std dev, games with 20+ / 30+), and trending (last-7-days
  PPG vs season PPG), all from the game log.
- Game log: every game in the data, most recent first, with
  opponent, venue, result, minutes, and the counting line.
- Teammates: the rest of the player's team, by minutes, each
  linking to their own profile (every teammate is profiled,
  since the whole team is in the top 25).

The builder does NOT import build_page.py: that module
rebuilds the whole index and all 366 team pages on import.
It reads the site CSS out of build_page.py's source instead,
so the profiles look like part of the same site without
running the full build. Team slugs use the same formula as
build_page.team_slug (duplicated here for the same reason).

Usage:
    python3 build_player_pages.py
"""

import csv
import html
import json
import re
import statistics
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
DATA = HERE / "data"
SEASON = "2026-27"
TOP_N = 25
REPO = "https://github.com/RD3-LIL/RonPom"
BUILT = datetime.now(ZoneInfo("America/Chicago")).strftime("%B %-d, %Y")
STAT_NAMES = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO",
              "STL", "BLK", "OREB", "DREB", "PF"]


def team_slug(name):
    """Team name -> stable URL slug, same formula as
    build_page.team_slug (duplicated so this module does not
    import build_page, which rebuilds the whole site on import)."""
    norm = unicodedata.normalize("NFKD", name)
    ascii_name = norm.encode("ascii", "ignore").decode("ascii")
    s = ascii_name.lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def player_slug(name, athlete_id, team):
    """Player name -> stable, unique URL slug for players/<slug>.html.

    Name slug + athlete id + team slug. No two top-25 players
    share an athlete id in this data, but the team is in there
    anyway so a mid-season transfer would not collide, as it
    does in the NBA data.
    """
    norm = unicodedata.normalize("NFKD", name)
    ascii_name = norm.encode("ascii", "ignore").decode("ascii")
    s = ascii_name.lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return f"{s}-{athlete_id}-{team_slug(team)}"


def load_site_css():
    """The site CSS, read out of build_page.py's source.

    build_page.py cannot be imported (it rebuilds the whole
    site on import), so the CSS string is extracted from its
    text instead. Falls back to a minimal stylesheet if the
    parse fails, so a build never breaks on a CSS edit.
    """
    try:
        src = (HERE / "build_page.py").read_text()
        start = src.index('CSS = """') + len('CSS = """')
        end = src.index('"""', start)
        return src[start:end]
    except (OSError, ValueError):
        return ("body { font-family: sans-serif; max-width: 960px; "
                "margin: 0 auto; padding: 24px 16px 64px; "
                "line-height: 1.5; }")


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _fmt(v, nd=1):
    if v is None:
        return "-"
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return "-"


def _pct(v):
    if v is None:
        return "-"
    return f"{100 * float(v):.1f}%"


def _rank_map(players, getter):
    """Competition ranks (1, 2, 2, 4) for one metric.

    Returns ({(athlete_id, team): rank}, denominator). Players
    with a None value get no rank and do not count in the
    denominator.
    """
    vals = []
    for p in players:
        v = getter(p)
        if v is not None:
            vals.append(((p["athlete_id"], p["team"]), v))
    vals.sort(key=lambda kv: kv[1], reverse=True)
    out, prev_val, prev_rank = {}, None, 0
    for i, (key, v) in enumerate(vals):
        rank = prev_rank if v == prev_val else i + 1
        out[key] = rank
        prev_val, prev_rank = v, rank
    return out, len(vals)


def top_teams(n=TOP_N):
    """Top n teams by Net from the 2026-27 ratings CSV.

    Returns (ordered [(team, rank, net)], {team: rank}).
    """
    with open(DATA / "ratings_2026_27.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: float(r["net"]), reverse=True)
    top = [(r["team"], int(r["rank"]), float(r["net"])) for r in rows[:n]]
    return top, {team: rank for team, rank, _ in top}


def load_game_logs():
    """Per (athlete_id, team_id) game logs from raw summaries.

    Each entry: {date, opponent, venue, result, score_for,
    score_against, min, pts, fg, reb, ast, to, stl, blk}.
    Date, teams, and scores come from the parsed games file,
    never the raw header date (UTC, can be a day off).
    """
    games = json.loads((DATA / "games_2026_27.json").read_text())
    game_map = {str(g["event_id"]): g for g in games}
    logs = defaultdict(list)
    raw_dir = DATA / "raw" / "summary"
    for raw_path in sorted(raw_dir.glob("*.json")) if raw_dir.is_dir() else []:
        game = game_map.get(raw_path.stem)
        if game is None:
            continue
        try:
            summary = json.loads(raw_path.read_text())
        except ValueError:
            continue
        entries = summary.get("boxscore", {}).get("players", []) or []
        for team_entry in entries:
            team = team_entry.get("team", {}) or {}
            team_name = team.get("displayName", "")
            team_id = str(team.get("id", ""))
            opp_name = ""
            for other in entries:
                if other is not team_entry:
                    opp_name = ((other.get("team", {}) or {})
                                .get("displayName", ""))
                    break
            if game.get("neutral_site"):
                venue = "N"
            else:
                venue = "H" if team_name == game.get("home") else "A"
            is_home = team_name == game.get("home")
            pts_for = game["home_score"] if is_home else game["away_score"]
            pts_against = game["away_score"] if is_home else game["home_score"]
            result = "W" if pts_for > pts_against else "L"
            for group in team_entry.get("statistics", []) or []:
                names = group.get("names", []) or STAT_NAMES
                idx = {n: i for i, n in enumerate(names)}
                for row in group.get("athletes", []) or []:
                    if row.get("didNotPlay") or not row.get("stats"):
                        continue
                    athlete = row.get("athlete", {}) or {}
                    aid = str(athlete.get("id", ""))
                    if not aid:
                        continue
                    stats = row.get("stats") or []

                    def get(name):
                        i = idx.get(name)
                        return stats[i] if i is not None and i < len(stats) else None

                    logs[(aid, team_id)].append({
                        "date": game["date"],
                        "opponent": opp_name,
                        "venue": venue,
                        "result": result,
                        "score_for": pts_for,
                        "score_against": pts_against,
                        "min": _parse_int(get("MIN")) or 0,
                        "pts": _parse_int(get("PTS")) or 0,
                        "fg": get("FG") or "",
                        "reb": _parse_int(get("REB")) or 0,
                        "ast": _parse_int(get("AST")) or 0,
                        "to": _parse_int(get("TO")) or 0,
                        "stl": _parse_int(get("STL")) or 0,
                        "blk": _parse_int(get("BLK")) or 0,
                    })
    for key in logs:
        logs[key].sort(key=lambda g: g["date"], reverse=True)
    return logs


def data_through():
    """(display date, n_played_games) from the games file."""
    games = json.loads((DATA / "games_2026_27.json").read_text())
    played = [g for g in games
              if (g.get("home_score") or g.get("away_score"))
              and not g.get("stats_missing")]
    last = max(g["date"] for g in played) if played else None
    disp = datetime.strptime(last, "%Y%m%d").strftime("%B %-d, %Y") \
        if last else "unknown"
    return disp, len(played), last


EXTRA_CSS = """
.profile-head { display: flex; gap: 16px; align-items: flex-start; margin: 12px 0; }
.profile-head img { width: 96px; height: 96px; object-fit: cover; border-radius: 8px; border: 1px solid #d0d7de; background: #f6f8fa; }
.profile-head .bio { color: #656d76; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #eaeef2; font-size: 12px; font-weight: 600; margin-right: 4px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 12px 0; }
.stat-card { border: 1px solid #d0d7de; border-radius: 8px; padding: 10px 12px; }
.stat-card .label { font-size: 12px; color: #656d76; text-transform: uppercase; letter-spacing: 0.04em; }
.tip { cursor: help; border-bottom: 1px dotted #656d76; position: relative; }
.tip::after { content: attr(data-tip); display: none; position: absolute; bottom: 125%; left: 0; width: 220px; background: #1f2328; color: #fff; padding: 8px; border-radius: 6px; font-size: 13px; line-height: 1.4; text-transform: none; letter-spacing: normal; font-weight: 400; z-index: 10; white-space: normal; }
.tip:hover::after, .tip:focus::after, .tip:active::after { display: block; }
.shoot-row .tip { border-bottom: 1px dotted #656d76; }
.stat-card .value { font-size: 26px; font-weight: 700; line-height: 1.2; }
.stat-card .rank { font-size: 13px; color: #656d76; }
.rank-bar { height: 6px; background: #eaeef2; border-radius: 999px; overflow: hidden; margin-top: 6px; }
.rank-bar span { display: block; height: 100%; background: #38bdf8; }
.comp-chart { max-width: 640px; margin: 8px 0; }
.comp-row { display: grid; grid-template-columns: 110px 1fr 56px; align-items: center; gap: 10px; margin: 8px 0; }
.comp-track { position: relative; height: 16px; background: #eaeef2; border-radius: 999px; }
.comp-center { position: absolute; left: 50%; top: -3px; bottom: -3px; width: 2px; background: #656d76; }
.comp-fill { position: absolute; top: 0; bottom: 0; border-radius: 999px; }
.comp-fill.pos { background: #38bdf8; left: 50%; }
.comp-fill.neg { background: #f59e0b; right: 50%; }
.comp-value { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
.shoot-row { display: grid; grid-template-columns: 90px 1fr 110px; align-items: center; gap: 10px; margin: 8px 0; max-width: 640px; }
.shoot-track { position: relative; height: 16px; background: #eaeef2; border-radius: 999px; }
.shoot-fill { display: block; height: 100%; background: #38bdf8; border-radius: 999px; }
.shoot-league { position: absolute; top: -3px; bottom: -3px; width: 2px; background: #656d76; }
.stacked { display: flex; height: 22px; border-radius: 999px; overflow: hidden; max-width: 640px; margin: 8px 0; }
.stacked span { display: block; height: 100%; }
.stack-2s { background: #38bdf8; }
.stack-3s { background: #1d4ed8; }
.stack-ft { background: #93c5fd; }
.legend { font-size: 13px; color: #656d76; }
.legend b { color: #1f2328; }
table.profile { font-size: 14px; width: auto; }
table.profile th, table.profile td { padding: 4px 12px; }
table.profile td:nth-child(n+2) { text-align: right; font-variant-numeric: tabular-nums; }
table.gamelog { font-size: 13px; }
"""


TIPS = {
    "RPR": "Our single-number rating for how much a player helps his team, where a star scores about +6 to +10 and an average rotation player scores about +1 to +3.",
    "PPG": "Points scored per game.",
    "RPG": "Rebounds grabbed per game.",
    "APG": "Assists per game.",
    "ORtg": "Points the player produces per 100 possessions he uses, using the simplified formula with no assist credit.",
    "TS%": "Points scored per shooting attempt, counting twos, threes, and free throws together.",
    "SHARP": "Extra points per game from threes and free throws above league average.",
    "FG%": "Share of all field goal attempts made.",
    "3P%": "Share of three point attempts made.",
    "FT%": "Share of free throw attempts made.",
    "eFG%": "Field goal percentage adjusted so a three counts more than a two, since it is worth more points.",
}


def rank_rows(p, ranks):
    """(label, value, rank, denominator, decimals) for at-a-glance."""
    key = (p["athlete_id"], p["team"])
    r = p.get("ratings") or {}
    s = p["shooting"]
    defs = [
        ("RPR", r.get("rpr"), "rpr", 2),
        ("PPG", p["per_game"]["pts"], "pts_pg", 1),
        ("RPG", p["per_game"]["reb"], "reb_pg", 1),
        ("APG", p["per_game"]["ast"], "ast_pg", 1),
        ("ORtg", r.get("ortg"), "ortg", 1),
        ("TS%", s.get("ts_pct"), "ts_pct", 1),
        ("SHARP", p.get("sharp"), "sharp", 2),
    ]
    out = []
    for label, value, rank_key, nd in defs:
        rank_map, denom = ranks[rank_key]
        out.append((label, value, rank_map.get(key), denom, nd))
    return out


def profile_html(p, ranks, league, logs, teammates, team_net_rank,
                 through, n_games, last_date, css):
    """One player's full profile page, as an HTML string."""
    t = p["totals"]
    pg = p["per_game"]
    p40 = p["per_40"]
    s = p["shooting"]
    r = p.get("ratings") or {}
    gp = t["gp"]
    min_pct = r.get("min_pct")
    small_sample = (gp <= 2 or (min_pct is not None and min_pct < 40))
    tslug = team_slug(p["team"])

    headshot = ""
    if p.get("headshot"):
        headshot = (f'<img src="{html.escape(p["headshot"])}" '
                    f'alt="{html.escape(p["name"])} headshot">')
    bio = (f"{html.escape(p['position'] or '-')} &middot; "
           f"#{html.escape(str(p.get('jersey') or '-'))} &middot; "
           f"{gp} GP, {t['gs']} GS")

    cards = []
    for label, value, rank, denom, nd in rank_rows(p, ranks):
        tip = html.escape(TIPS.get(label, ""), quote=True)
        label_html = (f'<span class="tip" tabindex="0" data-tip="{tip}">{label}</span>'
                      if tip else label)
        if value is None:
            cards.append(
                f'<div class="stat-card"><div class="label">{label_html}</div>'
                f'<div class="value">-</div>'
                f'<div class="rank">No value in this data</div></div>')
            continue
        if rank is None:
            rank_s = "Unranked"
            bar = ""
        else:
            pct_top = 100 * (1 - (rank - 1) / denom) if denom else 0
            rank_s = f"#{rank} of {denom} in the NCAA"
            bar = (f'<div class="rank-bar"><span style="width:'
                   f'{pct_top:.0f}%"></span></div>')
        val = _pct(value) if label == "TS%" else _fmt(value, nd)
        cards.append(
            f'<div class="stat-card"><div class="label">{label_html}</div>'
            f'<div class="value">{val}</div>'
            f'<div class="rank">{rank_s}</div>{bar}</div>')

    shoot_rows = []
    for label, value, league_v in [
            ("FG%", s.get("fg_pct"), league["fg_pct"]),
            ("3P%", s.get("fg3_pct"), league["fg3_pct"]),
            ("FT%", s.get("ft_pct"), league["ft_pct"]),
            ("eFG%", s.get("efg_pct"), league["efg_pct"]),
            ("TS%", s.get("ts_pct"), league["ts_pct"])]:
        tip = html.escape(TIPS.get(label, ""), quote=True)
        label_html = (f'<span class="tip" tabindex="0" data-tip="{tip}">{label}</span>'
                      if tip else label)
        if value is None:
            shoot_rows.append(
                f'<div class="shoot-row"><span>{label_html}</span>'
                f'<span class="shoot-track"></span>'
                f'<span>- (no attempts)</span></div>')
            continue
        width = max(0.0, min(100.0, 100 * float(value)))
        league_x = max(0.0, min(100.0, 100 * float(league_v)))
        shoot_rows.append(
            f'<div class="shoot-row"><span>{label_html}</span>'
            f'<span class="shoot-track"><span class="shoot-fill" '
            f'style="width:{width:.1f}%"></span>'
            f'<span class="shoot-league" style="left:{league_x:.1f}%"></span>'
            f'</span><span>{_pct(value)} (league {_pct(league_v)})</span></div>')

    pts_2s = 2 * (t["fgm"] - t["fg3m"])
    pts_3s = 3 * t["fg3m"]
    pts_ft = t["ftm"]
    shares = [(pts_2s / t["pts"] if t["pts"] else 0, "stack-2s", "2s"),
              (pts_3s / t["pts"] if t["pts"] else 0, "stack-3s", "3s"),
              (pts_ft / t["pts"] if t["pts"] else 0, "stack-ft", "FTs")]
    stack = "".join(
        f'<span class="{cls}" style="width:{share * 100:.1f}%"></span>'
        for share, cls, _ in shares)
    legend = " &middot; ".join(
        f"<b>{label}</b> {_pct(share)}" for share, _, label in shares)

    # Consistency and trending, from the game log.
    pts_list = [g["pts"] for g in logs]
    pts_std = (statistics.stdev(pts_list) if len(pts_list) > 1 else 0.0)
    games_20 = sum(1 for x in pts_list if x >= 20)
    games_30 = sum(1 for x in pts_list if x >= 30)
    window_start = None
    last7_ppg, last7_gp, trend = None, 0, None
    if last_date:
        last_d = datetime.strptime(last_date, "%Y%m%d").date()
        window_start = (last_d - timedelta(days=6)).strftime("%Y%m%d")
        last7 = [g for g in logs if g["date"] >= window_start]
        last7_gp = len(last7)
        if last7:
            last7_ppg = sum(g["pts"] for g in last7) / len(last7)
            trend = last7_ppg - pg["pts"]

    log_rows = []
    for g in logs:
        opp = html.escape(g["opponent"])
        log_rows.append(
            f"<tr><td>{g['date'][4:6]}/{g['date'][6:8]}</td>"
            f"<td>{opp}</td><td>{g['venue']}</td><td>{g['result']}</td>"
            f"<td>{g['score_for']}-{g['score_against']}</td>"
            f"<td>{g['min']}</td><td>{g['fg']}</td><td>{g['pts']}</td>"
            f"<td>{g['reb']}</td><td>{g['ast']}</td><td>{g['to']}</td>"
            f"<td>{g['stl']}</td><td>{g['blk']}</td></tr>")
    log_html = ("<p>No game log in this data.</p>" if not log_rows else
                '<div class="table-scroll"><table class="gamelog"><thead><tr>'
                "<th>Date</th><th>Opponent</th><th>Venue</th><th>Result</th>"
                "<th>Score</th><th>MIN</th><th>FG</th><th>PTS</th><th>REB</th>"
                "<th>AST</th><th>TO</th><th>STL</th><th>BLK</th>"
                "</tr></thead><tbody>" + "".join(log_rows) +
                "</tbody></table></div>")

    team_rows = []
    for mate in teammates:
        mslug = player_slug(mate["name"], mate["athlete_id"], mate["team"])
        team_rows.append(
            f'<li><a href="{mslug}.html">{html.escape(mate["name"])}</a> '
            f'({html.escape(mate["position"] or "-")}, '
            f'{_fmt(mate["per_game"]["pts"], 1)} PPG, '
            f'RPR {_fmt(mate.get("ratings", {}).get("rpr"), 2)})</li>')

    small = ""
    if small_sample:
        small = (f'<p class="warn">Small sample: {gp} games, '
                 f'{_fmt(min_pct, 1)}% of team minutes. Ranks on this '
                 f'page are among every player who appeared this '
                 f'season, so a hot few games can rank high. The '
                 f'leaderboards on the main page use a 40% minutes '
                 f'floor for exactly this reason.</p>')

    rpr = r.get("rpr")
    poss_pg = (t["fga"] + 0.44 * t["fta"] + t["to"]) / gp if gp else 0.0
    sharp = p.get("sharp")
    sharp_tip = html.escape(TIPS["SHARP"], quote=True)
    sharp_label = (f'<span class="tip" tabindex="0" '
                   f'data-tip="{sharp_tip}">SHARP</span>')
    if sharp is not None:
        sharp_width = min(50.0, abs(float(sharp)) / 2.5 * 50.0)
        sharp_cls = "pos" if sharp >= 0 else "neg"
        sharp_bar = (
            f'<div class="comp-chart"><div class="comp-row">'
            f"<span>{sharp_label}</span>"
            f'<span class="comp-track"><span class="comp-center"></span>'
            f'<span class="comp-fill {sharp_cls}" '
            f'style="width:{sharp_width:.1f}%"></span></span>'
            f'<span class="comp-value">{sharp:+.2f}</span></div></div>')
    else:
        sharp_bar = (
            f'<div class="comp-chart"><div class="comp-row">'
            f"<span>{sharp_label}</span>"
            f'<span class="comp-track"><span class="comp-center"></span></span>'
            f'<span class="comp-value">-</span></div></div>')
    if sharp is not None:
        fg3a_pg = t["fg3a"] / gp if gp else 0.0
        sharp_para = (
            f"<p>SHARP <strong>{sharp:+.2f}</strong>. SHARP counts "
            f"threes and free throws only, not midrange or layups, "
            f"and it is points per game added above league average "
            f"by shooting. {html.escape(p['name'])} shoots "
            f"{_pct(s.get('fg3_pct'))} from three on "
            f"{fg3a_pg:.1f} attempts per game and "
            f"{_pct(s.get('ft_pct'))} from the line, against league "
            f"averages of {_pct(league['fg3_pct'])} from three and "
            f"{_pct(league['ft_pct'])} from the line.</p>")
    else:
        sharp_para = (
            "<p>SHARP has no value here because the player is below "
            "the floor of 5 games and 20 minutes per game, so a "
            "small sample would move the number too much.</p>")
    body = f"""<h1>{html.escape(p["name"])}</h1>
<p class="subtitle"><a href="../teams/{tslug}.html">{html.escape(p["team"])}</a>
&middot; Data through {through} ({n_games} games)
&middot; <a href="../index.html">&larr; College Ratings</a>
&middot; <a href="index.html">Top-25 players</a></p>
<div class="profile-head">{headshot}<div><div class="bio">{bio}</div>
<p>Team Net rank #{team_net_rank} &middot; {_fmt(pg["min"], 1)} MPG, {_fmt(min_pct, 1)}% of team minutes</p>
<p class="note">Height, weight, and class year are not in this data yet (the roster pull has not run), so they are not shown here.</p></div></div>
{small}
<h2>At a glance</h2>
<div class="stat-grid">{''.join(cards)}</div>
<p class="note">RPR is our own single-number rating (a star is about +6 to +10, an average rotation player about +1 to +3), not KenPom's proprietary kPOY. ORtg is the simplified approximation (points per 100 possessions used, no assist credit), so it underrates playmakers; read it with %Poss. Ranks are among all players with a value for that stat; the bar shows the percentile (100% is best in the country).</p>

<h2>Season line</h2>
<table class="profile"><thead><tr><th></th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TO</th><th>PF</th></tr></thead><tbody>
<tr><td>Totals</td><td>{t["pts"]}</td><td>{t["reb"]}</td><td>{t["ast"]}</td><td>{t["stl"]}</td><td>{t["blk"]}</td><td>{t["to"]}</td><td>{t["pf"]}</td></tr>
<tr><td>Per game</td><td>{_fmt(pg["pts"])}</td><td>{_fmt(pg["reb"])}</td><td>{_fmt(pg["ast"])}</td><td>{_fmt(pg["stl"])}</td><td>{_fmt(pg["blk"])}</td><td>{_fmt(pg["to"])}</td><td>{_fmt(pg["pf"])}</td></tr>
<tr><td>Per 40</td><td>{_fmt(p40["pts"])}</td><td>{_fmt(p40["reb"])}</td><td>{_fmt(p40["ast"])}</td><td>{_fmt(p40["stl"])}</td><td>{_fmt(p40["blk"])}</td><td>{_fmt(p40["to"])}</td><td>{_fmt(p40["pf"])}</td></tr>
</tbody></table>
<p class="note">{t["fgm"]}-{t["fga"]} FG, {t["fg3m"]}-{t["fg3a"]} 3P, {t["ftm"]}-{t["fta"]} FT. {t["min"]} minutes in {gp} games. College games are 40 minutes, so per 40 is the standard rate here, not per 36.</p>

<h2>Shooting</h2>
{''.join(shoot_rows)}
<p class="note">Bars are the player's rate; the grey tick is the league average.</p>
{sharp_bar}
{sharp_para}

<h2>Where the points come from</h2>
<div class="stacked">{stack}</div>
<p class="legend">{legend}</p>

<h2>RPR</h2>
<p>RPR <strong>{_fmt(rpr, 2)}</strong>. Formula: (ORtg - 100) &times; possessions used per game / 100 + 0.5 &times; (AST - TO) per game + (STL + BLK) per game + 0.25 &times; REB per game. That is {_fmt(r.get("ortg"))} ORtg, {poss_pg:.1f} possessions used per game, {_fmt(pg["ast"])} AST, {_fmt(pg["to"])} TO, {_fmt(pg["stl"] + pg["blk"])} STL+BLK, {_fmt(pg["reb"])} REB per game.</p>
<p class="note">This is the v1 RPR, uncentered: an average rotation player scores about +1 to +3, so almost everyone gets some credit just for playing. The NBA site's RPR v1.2 recenters the counting terms on league averages so an average player scores about 0; that recentering has not been applied here, so the two sites' RPRs are not on the same scale. There is no component breakdown in this data. Usage {_fmt(r.get("poss_pct"))}% of team possessions.</p>

<h2>Playmaking, defense, rebounding</h2>
<p>AST/TO ratio {_fmt(pg["ast"] / pg["to"], 2) if pg["to"] else "-"} &middot; STL+BLK per game {_fmt(pg["stl"] + pg["blk"])}, per 40 {_fmt(p40["stl"] + p40["blk"])} &middot; REB per 40 {_fmt(p40["reb"])} (OREB {_fmt(p40["oreb"])}, DREB {_fmt(p40["dreb"])}) &middot; PF per 40 {_fmt(p40["pf"])}.</p>

<h2>Consistency and trending</h2>
<p>Points per game std dev {_fmt(pts_std)} (CV {_fmt(pts_std / pg["pts"], 2) if pg["pts"] else "-"}) &middot; {games_20} games with 20+ points, {games_30} with 30+ &middot; Last 7 days: {_fmt(last7_ppg)} PPG in {last7_gp} games, trend {_fmt(trend, 1)} PPG vs season ({_fmt(pg["pts"])} PPG).</p>

<h2>Game log</h2>
{log_html}
<p class="note">Most recent first. FG is made-attempted.</p>

<h2>Teammates on the {html.escape(p["team"])}</h2>
<ul>{''.join(team_rows)}</ul>
"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(p["name"])} | College Ratings</title>
<style>{css}{EXTRA_CSS}</style>
</head>
<body>
{body}
<footer>
<p>Data: ESPN public scoreboard and box scores. Code and full CSVs:
<a href="{REPO}">RD3-LIL/RonPom on GitHub</a>. Data through {through}
({n_games} games). Built {BUILT}. Not affiliated with KenPom.</p>
</footer>
</body>
</html>
"""



def players_index_html(players, top_list, through, n_games, css):
    """Filterable directory of the top-25 profiles, sorted by RPR."""
    rows = []
    for p in sorted(players, key=lambda x: (x.get("ratings") or {}).get("rpr") if (x.get("ratings") or {}).get("rpr") is not None else -99, reverse=True):
        slug = player_slug(p["name"], p["athlete_id"], p["team"])
        rpr = (p.get("ratings") or {}).get("rpr")
        rows.append(
            f'<tr><td><a href="{slug}.html">{html.escape(p["name"])}</a></td>'
            f'<td><a href="../teams/{team_slug(p["team"])}.html">{html.escape(p["team"])}</a></td>'
            f'<td>{html.escape(p["position"] or "-")}</td>'
            f'<td>{p["totals"]["gp"]}</td>'
            f'<td>{_fmt(p["per_game"]["pts"])}</td>'
            f'<td>{_fmt(p["per_game"]["reb"])}</td>'
            f'<td>{_fmt(p["per_game"]["ast"])}</td>'
            f'<td>{_fmt(rpr, 2) if rpr is not None else "-"}</td></tr>')
    top_names = ", ".join(team for team, _, _ in top_list)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Top-25 players | College Ratings</title>
<style>{css}{EXTRA_CSS}</style>
</head>
<body>
<h1>Top-25 players</h1>
<p class="subtitle">Data through {through} ({n_games} games) &middot; <a href="../index.html">&larr; College Ratings</a></p>
<p>{len(players)} profiles, one per player on a top-25 team, sorted by RPR. Type to filter by player or team name. Click a player for their full profile: season line, shooting, RPR, game log, and NCAA ranks.</p>
<p class="note">Top 25 teams by Net: {html.escape(top_names)}. Only these teams have profile pages; the other 341 teams' players are in the CSVs, not as pages.</p>
<input class="filter" type="search" placeholder="Filter players..." id="q" style="width: 280px;">
<div class="table-scroll"><table class="ratings" id="players"><thead><tr><th>Player</th><th>Team</th><th>Pos</th><th>GP</th><th>PPG</th><th>RPG</th><th>APG</th><th>RPR</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table></div>
<footer><p>Data: ESPN public scoreboard and box scores. Code and full CSVs: <a href="{REPO}">RD3-LIL/RonPom on GitHub</a>. Data through {through} ({n_games} games). Built {BUILT}. Not affiliated with KenPom.</p></footer>
<script>
document.getElementById("q").addEventListener("input", function (e) {{
  var q = e.target.value.trim().toLowerCase();
  document.querySelectorAll("#players tbody tr").forEach(function (r) {{
    r.style.display = (!q || r.textContent.toLowerCase().indexOf(q) !== -1) ? "" : "none";
  }});
}});
</script>
</body>
</html>
"""


def main():
    through, n_games, last_date = data_through()
    top_list, team_net_rank = top_teams()
    top_set = {team for team, _, _ in top_list}
    all_players = json.loads((DATA / "players_2026_27.json").read_text())["players"]
    sharp_path = DATA / "sharp_2026_27.json"
    sharp_map = {}
    if sharp_path.exists():
        sharp_data = json.loads(sharp_path.read_text())
        sharp_map = {(str(row["athlete_id"]), row["team"]): row["sharp"]
                     for row in sharp_data["players"]}
    for p in all_players:
        p["sharp"] = sharp_map.get((str(p["athlete_id"]), p["team"]))
    players = [p for p in all_players if p["team"] in top_set]
    if len(players) != sum(1 for p in all_players if p["team"] in top_set):
        raise SystemExit("top-25 filter mismatch")
    css = load_site_css()

    # League shooting averages, from every player's totals.
    tot = {k: sum(p["totals"][k] for p in all_players)
           for k in ("fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "pts")}
    league = {
        "fg_pct": tot["fgm"] / tot["fga"] if tot["fga"] else None,
        "fg3_pct": tot["fg3m"] / tot["fg3a"] if tot["fg3a"] else None,
        "ft_pct": tot["ftm"] / tot["fta"] if tot["fta"] else None,
        "efg_pct": ((tot["fgm"] + 0.5 * tot["fg3m"]) / tot["fga"]
                    if tot["fga"] else None),
        "ts_pct": (tot["pts"] / (2 * (tot["fga"] + 0.44 * tot["fta"]))
                   if tot["fga"] + tot["fta"] else None),
    }

    # NCAA ranks, among ALL players with a value for that stat.
    ranks = {
        "rpr": _rank_map(all_players, lambda p: (p.get("ratings") or {}).get("rpr")),
        "pts_pg": _rank_map(all_players, lambda p: p["per_game"]["pts"]),
        "reb_pg": _rank_map(all_players, lambda p: p["per_game"]["reb"]),
        "ast_pg": _rank_map(all_players, lambda p: p["per_game"]["ast"]),
        "ortg": _rank_map(all_players, lambda p: (p.get("ratings") or {}).get("ortg")),
        "ts_pct": _rank_map(all_players, lambda p: p["shooting"].get("ts_pct")),
        "sharp": _rank_map(all_players, lambda p: p.get("sharp")),
    }

    logs = load_game_logs()
    by_team = defaultdict(list)
    for p in players:
        by_team[p["team"]].append(p)
    for team in by_team:
        by_team[team].sort(key=lambda p: p["totals"]["min"], reverse=True)

    out_dir = HERE / "players"
    out_dir.mkdir(exist_ok=True)
    written = set()
    total = 0
    for p in players:
        slug = player_slug(p["name"], p["athlete_id"], p["team"])
        mates = [m for m in by_team[p["team"]] if m is not p]
        text = profile_html(
            p, ranks, league,
            logs.get((p["athlete_id"], p["team_id"]), []),
            mates, team_net_rank.get(p["team"], 0),
            through, n_games, last_date, css)
        path = out_dir / f"{slug}.html"
        path.write_text(text)
        written.add(path.name)
        total += len(text.encode("utf-8"))
    index_text = players_index_html(players, top_list, through, n_games, css)
    (out_dir / "index.html").write_text(index_text)
    written.add("index.html")
    total += len(index_text.encode("utf-8"))
    for stale in out_dir.glob("*.html"):
        if stale.name not in written:
            stale.unlink()
    print(f"Wrote {len(written)} player pages in players/: {total} bytes")
    print(f"Top-25 players: {len(players)}, all players: {len(all_players)}, "
          f"game-log entries: {sum(len(v) for v in logs.values())}, "
          f"league FG% {league['fg_pct']:.3f} 3P% {league['fg3_pct']:.3f} "
          f"TS% {league['ts_pct']:.3f}")
    top = sorted(players, key=lambda x: (x.get("ratings") or {}).get("rpr") or -99,
                 reverse=True)[:3]
    for p in top:
        print(f"  {p['name']} ({p['team']}) RPR "
              f"{(p.get('ratings') or {}).get('rpr'):.2f} "
              f"rank #{ranks['rpr'][0][(p['athlete_id'], p['team'])]} "
              f"PPG {p['per_game']['pts']:.1f} "
              f"rank #{ranks['pts_pg'][0][(p['athlete_id'], p['team'])]}")


if __name__ == "__main__":
    main()
