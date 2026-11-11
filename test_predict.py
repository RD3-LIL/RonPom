"""Tests for predict.py. No network: all fixtures are synthetic.

Run as: python3 test_predict.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from predict import (  # noqa: E402
    format_spread, market_spread, parse_upcoming, predict_all,
    predict_margin,
)


def _ratings():
    # Two teams: A is much better than B. League OffEff 107.
    return {
        "Alpha Aces": {"adj_o": 120.0, "adj_d": 95.0, "adj_t": 70.0},
        "Beta Bears": {"adj_o": 100.0, "adj_d": 110.0, "adj_t": 66.0},
    }, 107.0, 68.0


def _game(home="Alpha Aces", away="Beta Bears", neutral=False):
    return {"home": home, "away": away, "neutral_site": neutral,
            "home_short": "Alpha", "away_short": "Beta"}


def test_predict_margin_home_favored():
    ratings, lo, lt = _ratings()
    m = predict_margin(ratings, lo, lt, _game())
    assert m > 0, f"home favorite should win by points, got {m}"
    # Per 100: (120+110-107) - (100+95-107) + 4.69 = 39.69,
    # times ~68 poss / 100 = ~27.0.
    assert 25.0 < m < 29.0, f"unexpected margin {m}"


def test_predict_margin_neutral_site_gets_no_home_court():
    ratings, lo, lt = _ratings()
    home_game = predict_margin(ratings, lo, lt, _game(neutral=False))
    neutral_game = predict_margin(ratings, lo, lt, _game(neutral=True))
    # Difference is exactly home court scaled by possessions.
    assert home_game - neutral_game > 3.0
    assert neutral_game > 0


def test_predict_margin_unknown_team_is_league_average():
    ratings, lo, lt = _ratings()
    m = predict_margin(ratings, lo, lt,
                       _game(home="Unknown Utes", away="Beta Bears"))
    # Unknown home team is league average: per 100 =
    # (107+110-107) - (100+107-107) + 4.69 = 14.69, ~68 poss.
    assert 8.0 < m < 12.0, f"unexpected margin {m}"


def test_format_spread_names_the_favorite():
    assert format_spread(6.5, "Illinois", "Duke") == "Illinois -6.5"
    assert format_spread(-3.5, "Illinois", "Duke") == "Duke -3.5"


def test_parse_upcoming_filters_and_keeps_odds():
    payload = {"events": [
        # D1 vs D1, scheduled, with a market line.
        {"id": "1", "date": "2026-11-11T16:30Z", "odds": [
            {"spread": -6.5}],
         "competitions": [{"neutralSite": False,
                           "status": {"type": {"state": "pre"}},
                           "competitors": [
                               {"homeAway": "home", "team": {
                                   "displayName": "Alpha Aces",
                                   "shortDisplayName": "Alpha",
                                   "conferenceId": 1}},
                               {"homeAway": "away", "team": {
                                   "displayName": "Beta Bears",
                                   "shortDisplayName": "Beta",
                                   "conferenceId": 2}}]}]},
        # Non-D1 opponent: dropped.
        {"id": "2", "date": "2026-11-11T18:00Z",
         "competitions": [{"neutralSite": False,
                           "status": {"type": {"state": "pre"}},
                           "competitors": [
                               {"homeAway": "home", "team": {
                                   "displayName": "Alpha Aces",
                                   "shortDisplayName": "Alpha",
                                   "conferenceId": 1}},
                               {"homeAway": "away", "team": {
                                   "displayName": "Gamma College",
                                   "shortDisplayName": "Gamma",
                                   "conferenceId": None}}]}]},
        # Already played: dropped.
        {"id": "3", "date": "2026-11-11T19:00Z",
         "competitions": [{"neutralSite": False,
                           "status": {"type": {"state": "post"}},
                           "competitors": [
                               {"homeAway": "home", "team": {
                                   "displayName": "Alpha Aces",
                                   "shortDisplayName": "Alpha",
                                   "conferenceId": 1}},
                               {"homeAway": "away", "team": {
                                   "displayName": "Beta Bears",
                                   "shortDisplayName": "Beta",
                                   "conferenceId": 2}}]}]},
        # Neutral site, no market line yet.
        {"id": "4", "date": "2026-11-11T20:00Z",
         "competitions": [{"neutralSite": True,
                           "status": {"type": {"state": "pre"}},
                           "competitors": [
                               {"homeAway": "home", "team": {
                                   "displayName": "Beta Bears",
                                   "shortDisplayName": "Beta",
                                   "conferenceId": 2}},
                               {"homeAway": "away", "team": {
                                   "displayName": "Alpha Aces",
                                   "shortDisplayName": "Alpha",
                                   "conferenceId": 1}}]}]},
    ]}
    games = parse_upcoming(payload, "20261111")
    assert [g["event_id"] for g in games] == ["1", "4"]
    assert games[0]["market_spread"] == -6.5
    assert games[0]["neutral_site"] is False
    assert games[1]["market_spread"] is None
    assert games[1]["neutral_site"] is True


def test_market_spread_missing_is_none():
    assert market_spread({}, {}) is None
    assert market_spread({"odds": [{"details": "ALPHA -6.5"}]}, {}) is None


def test_predict_all_edge_is_model_minus_implied_market():
    ratings, lo, lt = _ratings()
    games = [_game()]
    games[0]["date"] = "20261111"
    games[0]["market_spread"] = -6.5
    rows = predict_all(ratings, lo, lt, games)
    assert len(rows) == 1
    r = rows[0]
    assert r["margin"] > 0
    assert 0.0 < r["home_win_prob"] < 1.0
    # Market -6.5 means the home team is favored by 6.5, so the
    # implied home margin is +6.5 and the edge is margin - 6.5.
    assert r["edge"] == r["margin"] + r["market_spread"]
    assert r["edge"] == r["margin"] - 6.5
    assert r["spread"].startswith("Alpha -")


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_")]
    for t in tests:
        t()
        print(f"{t.__name__} passed")
    print("all predict tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
