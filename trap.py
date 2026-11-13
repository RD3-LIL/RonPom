"""Trap game finder: flag favorites due for a letdown.

A trap game is a favorite that looks safe on the ratings but
carries several letdown signals at once, and where the market
likes the favorite even more than the model does. This is a
detector, not a pick: it flags what is weird, it does not
change the predicted spread or win probability.

Pre-registered rules, locked before the 2025-26 backtest
(comparisons/trap_backtest_2025_26.md). No threshold was
tuned on the test season.

Favorite: the team the model predicts to win. No clear
favorite when |margin| < 2.0 points, then no trap.

Flags, one point each:
  TOP25: favorite Net rank <= 25.
  BIG_WIN: favorite won its last game by 20+ points, or by
    10+ against a top-25 opponent.
  BUSY: favorite played 3+ games in the 7 days before this
    game.
  SHORT_REST: favorite has 1 or 0 days rest since its last
    game, and the underdog has at least 1 day more rest.
  ROAD_FAV: favorite is the away team.
  MARKET_GAP: market favors the favorite by at least 4
    points more than the model does. Market fav margin is
    the implied home margin when the favorite is home, and
    its negative when the favorite is away.

Trap when MARKET_GAP is present and total flags >= 3.
Market gap is required because the original idea was
"model likes the underdog way more than the market does".
Without a market line there is no gap to measure, so no
trap, even if the other flags are present.

What this does NOT claim:
  Travel distance is not in the data, so ROAD_FAV is the
  only travel proxy, a road game, not a miles number.
  "Rival" is not in the data, so BIG_WIN uses a top-25
  opponent instead of a rivalry label.
  Early season history is thin: a team with 2 games played
  cannot be BUSY in the same way as a team in February.
  The spread backtests already showed model-vs-market
  disagreements cover below the 52.4% breakeven, so a trap
  flag is a watch list, not a bet.

History comes only from games played before the game date,
never from the game itself or later games. Ratings rank
comes from the ratings used for the prediction, never from
a later ratings run.
"""

from bisect import bisect_left
from datetime import date, timedelta

MIN_FAV_MARGIN = 2.0
TOP_RANK = 25
BIG_WIN_MARGIN = 20
BIG_WIN_VS_TOP = 10
BUSY_GAMES = 3
BUSY_DAYS = 7
MARKET_GAP_MIN = 4.0
TRAP_MIN_FLAGS = 3


def parse_date(ds):
    """YYYYMMDD string to a date."""
    return date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))


def rank_map(ratings):
    """Team name -> Net rank (1 is best), from ratings net."""
    ordered = sorted(ratings.items(),
                     key=lambda kv: kv[1].get("net", 0),
                     reverse=True)
    return {team: i + 1 for i, (team, _) in enumerate(ordered)}


def rank_map_from_rows(rows):
    """Team name -> rank, from a ratings CSV row list."""
    return {r["team"]: int(r["rank"]) for r in rows}


def build_history(games, ranks):
    """Per-team prior-game index, sorted by date.

    games: played D1 games with date, home, away, home_score,
    away_score, neutral_site. ranks: team -> Net rank.
    Returns {team: [entry, ...]} sorted by (date, event_id),
    where entry is {date, opponent, opp_rank, margin, won,
    venue}. margin is points for minus points against for
    that team. Venue is H, A, or N.
    """
    index = {}
    for g in games:
        if g.get("home_score") == 0 and g.get("away_score") == 0:
            continue
        d = parse_date(g["date"])
        for team, opp, pts, opp_pts, venue in (
                (g["home"], g["away"], g["home_score"],
                 g["away_score"], "N" if g.get("neutral_site") else "H"),
                (g["away"], g["home"], g["away_score"],
                 g["home_score"], "N" if g.get("neutral_site") else "A")):
            index.setdefault(team, []).append({
                "date": d,
                "date_str": g["date"],
                "opponent": opp,
                "opp_rank": ranks.get(opp),
                "margin": pts - opp_pts,
                "won": pts > opp_pts,
                "venue": venue,
            })
    for lst in index.values():
        lst.sort(key=lambda e: (e["date"], e["date_str"]))
    return index


def _prior(history, team, game_date):
    """Games for team played strictly before game_date."""
    lst = history.get(team, [])
    dates = [e["date"] for e in lst]
    cut = bisect_left(dates, game_date)
    return lst[:cut]


def _days_rest(prior, game_date):
    if not prior:
        return None
    return (game_date - prior[-1]["date"]).days


def flags_for_game(game, margin, market_spread, ranks, history):
    """Trap flags for one game.

    game: dict with home, away, date (YYYYMMDD), neutral_site.
    margin: predicted home margin in points.
    market_spread: ESPN home-team line, or None.
    ranks: team -> Net rank.
    history: per-team index from build_history.
    Returns a dict with favorite, underdog, score, flags,
    trap, and a reasons list.
    """
    result = {"favorite": None, "underdog": None, "score": 0,
              "flags": [], "reasons": [], "trap": False,
              "market_gap": None}
    if margin is None or abs(margin) < MIN_FAV_MARGIN:
        return result
    home = game["home"]
    away = game["away"]
    fav = home if margin > 0 else away
    dog = away if margin > 0 else home
    result["favorite"] = fav
    result["underdog"] = dog
    game_date = parse_date(game["date"])
    flags = []
    reasons = []

    fav_rank = ranks.get(fav)
    if fav_rank is not None and fav_rank <= TOP_RANK:
        flags.append("TOP25")
        reasons.append(f"Favorite is ranked #{fav_rank}")

    fav_prior = _prior(history, fav, game_date)
    dog_prior = _prior(history, dog, game_date)

    if fav_prior:
        last = fav_prior[-1]
        if (last["won"] and
                (last["margin"] >= BIG_WIN_MARGIN or
                 (last["margin"] >= BIG_WIN_VS_TOP and
                  last["opp_rank"] is not None and
                  last["opp_rank"] <= TOP_RANK))):
            flags.append("BIG_WIN")
            reasons.append(
                f"Won last game by {last['margin']} vs "
                f"{last['opponent']}")
        window_start = game_date - timedelta(days=BUSY_DAYS)
        busy = sum(1 for e in fav_prior if e["date"] >= window_start)
        if busy >= BUSY_GAMES:
            flags.append("BUSY")
            reasons.append(f"{busy} games in the last 7 days")
        fav_rest = _days_rest(fav_prior, game_date)
        dog_rest = _days_rest(dog_prior, game_date)
        dog_rest_eff = dog_rest if dog_rest is not None else 99
        if (fav_rest is not None and fav_rest <= 1 and
                dog_rest_eff - fav_rest >= 1):
            flags.append("SHORT_REST")
            reasons.append(
                f"Favorite has {fav_rest} day(s) rest, "
                f"underdog has "
                f"{dog_rest if dog_rest is not None else 'no game yet'}")

    if not game.get("neutral_site") and fav == away:
        flags.append("ROAD_FAV")
        reasons.append("Favorite is on the road")

    if market_spread is not None:
        model_fav = abs(margin)
        implied_home = -float(market_spread)
        market_fav = implied_home if fav == home else -implied_home
        gap = market_fav - model_fav
        result["market_gap"] = gap
        if gap >= MARKET_GAP_MIN:
            flags.append("MARKET_GAP")
            reasons.append(
                f"Market favors favorite by {market_fav:.1f}, "
                f"model says {model_fav:.1f} (gap {gap:+.1f})")

    result["flags"] = flags
    result["reasons"] = reasons
    result["score"] = len(flags)
    result["trap"] = ("MARKET_GAP" in flags and
                      len(flags) >= TRAP_MIN_FLAGS)
    return result
