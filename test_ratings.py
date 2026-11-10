"""Hand-checked tests for the KenPom-like ratings engine."""

from ratings import possessions, compute

def test_possessions_illinois_fdu():
    # Illinois vs Fairleigh Dickinson, Nov 2, 2026, real ESPN box score:
    # Illinois FGA 83, ORB 22, TOV 7, FTA 16
    poss = possessions({"fga": 83, "orb": 22, "tov": 7, "fta": 16})
    assert abs(poss - 75.04) < 0.01, poss
    # FDU: FGA 61, ORB ? use 7 as a stand-in, TOV 12, FTA 11
    # just check the formula shape, not a real FDU line
    assert abs(possessions({"fga": 61, "orb": 7, "tov": 12, "fta": 11}) - 70.84) < 0.01

def test_adjustment_direction():
    # Team A beats a great defensive team, Team B beats a terrible one.
    # A's AdjO should be higher than its raw, B's should be lower.
    games = [
        {"home": "A", "away": "StrongD", "home_score": 80, "away_score": 70,
         "home_stats": {"fga": 60, "orb": 10, "tov": 10, "fta": 20},
         "away_stats": {"fga": 60, "orb": 10, "tov": 10, "fta": 20}},
        {"home": "B", "away": "WeakD", "home_score": 80, "away_score": 70,
         "home_stats": {"fga": 60, "orb": 10, "tov": 10, "fta": 20},
         "away_stats": {"fga": 60, "orb": 10, "tov": 10, "fta": 20}},
        # StrongD / WeakD play each other to set their defensive levels
        # StrongD scores 90 and allows 50, so its defense is good
        {"home": "StrongD", "away": "WeakD", "home_score": 90, "away_score": 50,
         "home_stats": {"fga": 60, "orb": 10, "tov": 10, "fta": 20},
         "away_stats": {"fga": 60, "orb": 10, "tov": 10, "fta": 20}},
    ]
    teams, _, _ = compute(games)
    assert teams["A"]["adj_o"] > teams["A"]["raw_o"]
    assert teams["B"]["adj_o"] < teams["B"]["raw_o"]

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "passed")
    print("all ratings tests passed")
