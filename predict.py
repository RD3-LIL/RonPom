"""Predict the spread for upcoming college basketball matchups.

Reads the current 2026-27 solver ratings (real preseason prior),
fetches the ESPN scoreboard for the next few days, and prints a
predicted spread, home win probability, and market line (when
ESPN has one yet) for every scheduled D1-vs-D1 game.

The spread is quoted from the favorite: "Illinois -6.5" means
Illinois is favored by 6.5. The market line, when present, is
the home team's line in ESPN's convention: negative means the
home team is favored, positive means the home team is getting
points, so the market's implied home margin is the negative
of the line. The edge is the model home margin minus the
market's implied home margin (margin + market line): positive
means the model likes the home team more than the market does.

Constants are locked by the backtest
(comparisons/backtest_2025_26.md, fit 2024-25, predict 2025-26):
home court 4.69 pts/100 poss, cross-fitted logistic a=0.150,
b=0.148. If the backtest is re-run on a new fit season, update
them here. Neutral-site games get no home court; the backtest's
margin function does not make that distinction, this tool does.

Market lines usually appear on the scoreboard only close to
tip-off (the day before, 0 of 67 games had one), so the market
column is often empty for games two or three days out. That is
missing data, not a bug.

Usage:
    python3 predict.py [--days 3] [--date YYYYMMDD] [--out FILE.csv]
"""

import argparse
import csv
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
from backtest import margin_model, played_d1, win_prob  # noqa: E402
from solver import is_d1_game, solve  # noqa: E402
from trap import build_history, flags_for_game, rank_map  # noqa: E402
from write_ratings import load_prior  # noqa: E402

SEASON = "2026-27"
HOME_COURT = 4.69
LOGISTIC_A = 0.150
LOGISTIC_B = 0.148
SB_BASE = ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
           "mens-college-basketball/scoreboard")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/131.0.0.0 Safari/537.36"),
}
SCOREBOARD_SLEEP = 0.3
CHICAGO = ZoneInfo("America/Chicago")


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def market_spread(ev, comp):
    """Market home-team line from a scoreboard event, or None.

    ESPN's scoreboard odds carry a numeric spread when the line
    is out. It is the home team's line: negative means the home
    team is favored. No odds yet is the common case a day or
    more before tip-off, and returns None.
    """
    for odds in (ev.get("odds") or []) + (comp.get("odds") or []):
        spread = odds.get("spread")
        if isinstance(spread, (int, float)):
            return float(spread)
    return None


def parse_upcoming(payload, date_str):
    """Scheduled D1-vs-D1 games from one scoreboard payload."""
    out = []
    for ev in payload.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        if comp.get("status", {}).get("type", {}).get("state") != "pre":
            continue
        comps = comp.get("competitors", [])
        if len(comps) != 2:
            continue
        info = {}
        for c in comps:
            t = c.get("team", {})
            info[c.get("homeAway", "")] = {
                "name": t.get("displayName"),
                "short": t.get("shortDisplayName") or t.get("displayName"),
                "conf_id": t.get("conferenceId"),
            }
        home = info.get("home") or info[list(info)[0]]
        away = info.get("away") or info[list(info)[1]]
        game = {
            "home": home["name"], "away": away["name"],
            "home_short": home["short"], "away_short": away["short"],
            "home_conf_id": home["conf_id"],
            "away_conf_id": away["conf_id"],
            "neutral_site": bool(comp.get("neutralSite")),
        }
        if not is_d1_game(game):
            continue
        game["date"] = date_str
        game["event_id"] = ev.get("id")
        game["tipoff"] = ev.get("date")
        game["market_spread"] = market_spread(ev, comp)
        out.append(game)
    return out


def predict_margin(ratings, league_o, league_t, game):
    """Predicted home margin in points for an upcoming game.

    Model-consistent margin (same formula as the backtest),
    with home court applied only when the game is not on a
    neutral floor.
    """
    hc = 0.0 if game.get("neutral_site") else HOME_COURT
    return margin_model(ratings, league_o, league_t, game, hc)


def format_spread(margin, home_short, away_short):
    """'Illinois -6.5': the favorite, then the points."""
    if abs(margin) < 0.05:
        return "Pick'em"
    if margin >= 0:
        return f"{home_short} -{margin:.1f}"
    return f"{away_short} -{abs(margin):.1f}"


def load_ratings():
    """Current 2026-27 ratings, league OffEff, and tempo."""
    path = DATA / "games_2026_27.json"
    games = json.loads(path.read_text())
    prior, prior_desc = load_prior(SEASON)
    teams, league_o, league_t, info = solve(
        games, prior=prior, return_info=True)
    print(f"Ratings: {SEASON}, {info['n_games']} games, "
          f"{info['n_teams']} teams, league OffEff {league_o:.1f}, "
          f"tempo {league_t:.1f}, prior: {prior_desc}", flush=True)
    return teams, league_o, league_t


def fetch_upcoming(start_date, days):
    """Scheduled games for the next `days` days from `start_date`."""
    games = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        ds = d.strftime("%Y%m%d")
        try:
            payload = get_json(
                f"{SB_BASE}?dates={ds}&limit=500&groups=50")
        except Exception as e:
            print(f"{ds}: scoreboard failed: {e}", flush=True)
            continue
        games.extend(parse_upcoming(payload, ds))
        time.sleep(SCOREBOARD_SLEEP)
    return games


def load_history(ranks):
    """Per-team prior-game index for the trap detector.

    Played D1 games from the current season only, so every
    trap flag uses games played before the upcoming game's
    date, never future games.
    """
    path = DATA / "games_2026_27.json"
    games = json.loads(path.read_text())
    return build_history(played_d1(games), ranks)


def predict_all(ratings, league_o, league_t, games,
                ranks=None, history=None):
    """One prediction row per upcoming game.

    Each row also carries the trap detector output from
    trap.py: trap (bool), trap_score, trap_flags, and
    trap_reasons. The trap flag never changes the spread
    or win probability.
    """
    if ranks is None:
        ranks = rank_map(ratings)
    if history is None:
        history = {}
    rows = []
    for g in games:
        margin = predict_margin(ratings, league_o, league_t, g)
        prob = win_prob(margin, LOGISTIC_A, LOGISTIC_B)
        market = g.get("market_spread")
        trap = flags_for_game(g, margin, market, ranks, history)
        rows.append({
            "date": g["date"],
            "tipoff": g.get("tipoff"),
            "home": g["home"], "away": g["away"],
            "home_short": g["home_short"],
            "away_short": g["away_short"],
            "neutral_site": g.get("neutral_site", False),
            "margin": margin,
            "spread": format_spread(margin, g["home_short"],
                                     g["away_short"]),
            "home_win_prob": prob,
            "market_spread": market,
            # Market line is the home team's line, so the implied
            # home margin is -market. Edge = model margin minus
            # implied market margin = margin + market.
            "edge": (margin + market) if market is not None else None,
            "trap": trap["trap"],
            "trap_score": trap["score"],
            "trap_flags": ";".join(trap["flags"]),
            "trap_reasons": "; ".join(trap["reasons"]),
            "trap_favorite": trap["favorite"] or "",
        })
    return rows


def tipoff_chicago(row):
    """Tip-off time in Chicago time, or the date if unparsable."""
    raw = row.get("tipoff")
    if not raw:
        return row["date"]
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(CHICAGO).strftime("%a %I:%M %p")
    except ValueError:
        return row["date"]


def print_table(rows):
    with_market = sum(1 for r in rows if r["market_spread"] is not None)
    n_trap = sum(1 for r in rows if r.get("trap"))
    print(f"{len(rows)} upcoming D1 games, {with_market} with a "
          f"market line so far, {n_trap} trap games")
    print(f"{'Tip-off':<14} {'Matchup':<44} {'Spread':<20} "
          f"{'Home win%':<9} {'Market':<9} {'Edge':<6} {'Trap':<5}")
    for r in rows:
        market = (f"{r['market_spread']:+.1f}"
                  if r["market_spread"] is not None else "-")
        edge = (f"{r['edge']:+.1f}"
                if r["edge"] is not None else "-")
        trap = (f"{r.get('trap_score', 0)}*"
                if r.get("trap") else str(r.get("trap_score", 0)))
        matchup = f"{r['away_short']} @ {r['home_short']}"
        if r["neutral_site"]:
            matchup += " (N)"
        print(f"{tipoff_chicago(r):<14} {matchup:<44} "
              f"{r['spread']:<20} {r['home_win_prob'] * 100:>7.1f}% "
              f"{market:<9} {edge:<6} {trap:<5}")
        if r.get("trap"):
            print(f"  TRAP: {r.get('trap_favorite')} - "
                  f"{r.get('trap_reasons')}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3,
                        help="days ahead to fetch (default 3)")
    parser.add_argument("--date", default=None,
                        help="start date YYYYMMDD (default today, "
                             "Chicago time)")
    parser.add_argument("--out", default=None,
                        help="also write predictions to this CSV")
    args = parser.parse_args()
    if args.date:
        start = datetime.strptime(args.date, "%Y%m%d").date()
    else:
        start = datetime.now(CHICAGO).date()
    ratings, league_o, league_t = load_ratings()
    ranks = rank_map(ratings)
    history = load_history(ranks)
    games = fetch_upcoming(start, args.days)
    rows = predict_all(ratings, league_o, league_t, games,
                       ranks=ranks, history=history)
    rows.sort(key=lambda r: (r["date"], r["tipoff"] or ""))
    print_table(rows)
    if args.out:
        with open(args.out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "date", "tipoff", "home", "away", "home_short",
                "away_short", "neutral_site", "margin", "spread",
                "home_win_prob", "market_spread", "edge",
                "trap", "trap_score", "trap_flags",
                "trap_reasons", "trap_favorite"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
