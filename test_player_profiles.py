"""Tests for player_profiles.py. Run: python3 test_player_profiles.py

Uses only synthetic raw summaries in a temp dir, never the real
data on disk and never the network.
"""

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from player_profiles import (aggregate_players, compute_ortg,  # noqa: E402
                             compute_rpr, compute_usage,
                             load_game_map, main, possessions_used,
                             rank_players)


def _athlete(athlete_id, name, minutes, pts, fg, fg3, ft, reb, ast, to,
             stl, blk, oreb, dreb, pf, starter=False, dnp=False,
             jersey="0", position="G"):
    return {
        "athlete": {
            "id": athlete_id,
            "displayName": name,
            "shortName": name,
            "jersey": jersey,
            "position": {"abbreviation": position},
            "headshot": {"href": f"https://example.com/{athlete_id}.png"},
        },
        "starter": starter,
        "didNotPlay": dnp,
        "stats": [] if dnp else [str(minutes), str(pts), fg, fg3, ft,
                                 str(reb), str(ast), str(to), str(stl),
                                 str(blk), str(oreb), str(dreb), str(pf)],
    }


def _summary(event_id, home_team, away_team, home_athletes, away_athletes):
    def team_entry(team_id, team_name, athletes):
        return {
            "team": {"id": team_id, "displayName": team_name},
            "statistics": [{
                "names": ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST",
                          "TO", "STL", "BLK", "OREB", "DREB", "PF"],
                "athletes": athletes,
            }],
        }
    return {
        "boxscore": {
            "players": [
                team_entry("1", home_team, home_athletes),
                team_entry("2", away_team, away_athletes),
            ]
        }
    }


def _setup(tmp, games, summaries):
    """Write parsed games + raw summaries into a temp data dir."""
    data = Path(tmp) / "data"
    (data / "raw" / "summary").mkdir(parents=True)
    (data / "parsed" / "2026-27").mkdir(parents=True)
    (data / "parsed" / "2025-26").mkdir(parents=True)
    by_season = {}
    for game in games:
        by_season.setdefault(game["season"], []).append(game)
    for season, season_games in by_season.items():
        (data / "parsed" / season / "20260101.json").write_text(
            json.dumps(season_games))
    for event_id, summary in summaries.items():
        (data / "raw" / "summary" / f"{event_id}.json").write_text(
            json.dumps(summary))
    return data


def _game(event_id, season, home, away):
    return {
        "event_id": event_id, "season": season, "date": "20260101",
        "home": home, "away": away, "home_id": "1", "away_id": "2",
        "home_score": 80, "away_score": 70,
    }


def test_aggregation_two_games():
    """Totals, per game, per 40, and shooting math across 2 games."""
    with tempfile.TemporaryDirectory() as tmp:
        games = [_game("100", "2026-27", "Alpha", "Beta"),
                 _game("101", "2026-27", "Alpha", "Beta")]
        summaries = {
            "100": _summary("100", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 20, 10, "4-8",
                                      "2-4", "0-0", 5, 2, 1, 1, 0, 2, 3,
                                      1, starter=True)],
                            [_athlete("8", "Ben Bench", 10, 2, "1-3",
                                      "0-1", "0-0", 1, 0, 0, 0, 0, 0, 1,
                                      0)]),
            "101": _summary("101", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 30, 20, "8-12",
                                      "2-5", "2-2", 7, 4, 2, 0, 1, 3, 4,
                                      2, starter=True)],
                            [_athlete("8", "Ben Bench", 5, 0, "0-1",
                                      "0-0", "0-0", 0, 1, 1, 0, 0, 0, 0,
                                      0)]),
        }
        data = _setup(tmp, games, summaries)
        profiles, report = aggregate_players(data)
        assert report["games_included"] == {"2026-27": 2}, report
        assert report["failed_json"] == 0, report
        assert report["unmapped_events"] == 0, report
        assert len(profiles["2026-27"]) == 2, profiles
        sam = [p for p in profiles["2026-27"] if p["name"] == "Sam Star"][0]
        t = sam["totals"]
        assert (t["gp"], t["gs"], t["min"], t["pts"]) == (2, 2, 50, 30), t
        assert (t["fgm"], t["fga"]) == (12, 20), t
        assert (t["fg3m"], t["fg3a"]) == (4, 9), t
        assert (t["ftm"], t["fta"]) == (2, 2), t
        assert (t["reb"], t["oreb"], t["dreb"]) == (12, 5, 7), t
        assert (t["ast"], t["to"], t["stl"], t["blk"], t["pf"]) == (
            6, 3, 1, 1, 3), t
        assert sam["per_game"]["pts"] == 15.0, sam["per_game"]
        assert sam["per_game"]["reb"] == 6.0, sam["per_game"]
        assert sam["per_40"]["pts"] == 24.0, sam["per_40"]
        s = sam["shooting"]
        assert abs(s["fg_pct"] - 0.6) < 1e-9, s
        assert abs(s["fg3_pct"] - 4 / 9) < 1e-9, s
        assert abs(s["ft_pct"] - 1.0) < 1e-9, s
        # eFG = (12 + 0.5*4) / 20 = 0.7
        assert abs(s["efg_pct"] - 0.7) < 1e-9, s
        # TS = 30 / (2 * (20 + 0.44*2)) = 30 / 41.76
        assert abs(s["ts_pct"] - 30 / 41.76) < 1e-9, s
        assert sam["jersey"] == "0" and sam["position"] == "G", sam
        assert sam["headshot"] == "https://example.com/7.png", sam


def test_dnp_does_not_count():
    """A DNP row in game 2 is not a game played and adds nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        games = [_game("100", "2026-27", "Alpha", "Beta"),
                 _game("101", "2026-27", "Alpha", "Beta")]
        summaries = {
            "100": _summary("100", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 20, 10, "4-8",
                                      "2-4", "0-0", 5, 2, 1, 1, 0, 2, 3,
                                      1, starter=True)],
                            []),
            "101": _summary("101", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 0, 0, "0-0",
                                      "0-0", "0-0", 0, 0, 0, 0, 0, 0, 0,
                                      0, dnp=True)],
                            []),
        }
        data = _setup(tmp, games, summaries)
        profiles, report = aggregate_players(data)
        sam = profiles["2026-27"][0]
        assert sam["totals"]["gp"] == 1, sam["totals"]
        assert sam["totals"]["pts"] == 10, sam["totals"]
        assert report["players_skipped_dnp"] == 1, report


def test_seasons_stay_separate():
    """The same athlete id in two seasons gets two profiles."""
    with tempfile.TemporaryDirectory() as tmp:
        games = [_game("100", "2026-27", "Alpha", "Beta"),
                 _game("200", "2025-26", "Alpha", "Beta")]
        summaries = {
            "100": _summary("100", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 20, 10, "4-8",
                                      "2-4", "0-0", 5, 2, 1, 1, 0, 2, 3,
                                      1)],
                            []),
            "200": _summary("200", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 25, 15, "6-10",
                                      "1-3", "2-2", 6, 3, 1, 0, 0, 2, 4,
                                      1)],
                            []),
        }
        data = _setup(tmp, games, summaries)
        profiles, _ = aggregate_players(data)
        assert set(profiles) == {"2026-27", "2025-26"}, profiles
        assert profiles["2026-27"][0]["totals"]["pts"] == 10
        assert profiles["2025-26"][0]["totals"]["pts"] == 15


def test_multi_team_flagged():
    """One athlete id on two teams in a season: two profiles, flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        games = [_game("100", "2026-27", "Alpha", "Beta"),
                 _game("101", "2026-27", "Gamma", "Beta")]
        summaries = {
            "100": _summary("100", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 20, 10, "4-8",
                                      "2-4", "0-0", 5, 2, 1, 1, 0, 2, 3,
                                      1)],
                            []),
            "101": _summary("101", "Gamma", "Beta",
                            [_athlete("7", "Sam Star", 20, 12, "5-9",
                                      "1-2", "1-1", 4, 1, 0, 0, 0, 1, 3,
                                      1)],
                            []),
        }
        # Second game uses team id 1 for Gamma in the synthetic helper,
        # so rebuild it with a distinct team id to simulate a transfer.
        summaries["101"]["boxscore"]["players"][0]["team"]["id"] = "3"
        summaries["101"]["boxscore"]["players"][0]["team"]["displayName"] = "Gamma"
        data = _setup(tmp, games, summaries)
        profiles, report = aggregate_players(data)
        assert len(profiles["2026-27"]) == 2, profiles
        assert len(report["multi_team_athlete_ids"]) == 1, report
        assert report["multi_team_athlete_ids"][0]["athlete_id"] == "7"


def test_bad_and_unmapped_files_skipped():
    """A corrupt JSON file and an unmapped event are skipped, not fatal."""
    with tempfile.TemporaryDirectory() as tmp:
        games = [_game("100", "2026-27", "Alpha", "Beta")]
        summaries = {
            "100": _summary("100", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 20, 10, "4-8",
                                      "2-4", "0-0", 5, 2, 1, 1, 0, 2, 3,
                                      1)],
                            []),
            # Event 999 has no parsed game, so it is unmapped.
            "999": _summary("999", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 20, 99, "4-8",
                                      "2-4", "0-0", 5, 2, 1, 1, 0, 2, 3,
                                      1)],
                            []),
        }
        data = _setup(tmp, games, summaries)
        (data / "raw" / "summary" / "888.json").write_text("{not json")
        profiles, report = aggregate_players(data)
        assert report["failed_json"] == 1, report
        assert report["unmapped_events"] == 1, report
        # The 99-point unmapped game did not leak into the profile.
        assert profiles["2026-27"][0]["totals"]["pts"] == 10
        game_map = load_game_map(data)
        assert "100" in game_map and "999" not in game_map


def test_ratings_formulas():
    """ORtg, usage, and RPR math on hand-computed numbers."""
    totals = {"pts": 30, "fga": 20, "fta": 2, "to": 3, "min": 50}
    assert abs(possessions_used(totals) - 23.88) < 1e-9
    # ORtg = 100 * 30 / 23.88
    assert abs(compute_ortg(totals) - 125.628) < 0.01
    assert compute_ortg({"pts": 0, "fga": 0, "fta": 0, "to": 0}) is None
    team = {"fga": 125, "fta": 38, "to": 23, "min": 65}
    # usage = 100 * (23.88 * 13) / (50 * 164.72)
    assert abs(compute_usage(totals, team) - 3.769) < 0.01
    assert compute_usage(totals, {"fga": 0, "fta": 0, "to": 0,
                                  "min": 0}) is None
    per_game = {"ast": 3.0, "to": 1.5, "stl": 0.5, "blk": 0.5, "reb": 6.0}
    # RPR = 25.628 * 11.94 / 100 + 0.5 * 1.5 + 1.0 + 1.5
    assert abs(compute_rpr(125.628, 11.94, per_game) - 6.31) < 0.01
    assert compute_rpr(None, 11.94, per_game) is None


def test_ratings_on_real_aggregation():
    """Sam Star's ORtg, %Poss, %Min, and RPR from the two-game set."""
    with tempfile.TemporaryDirectory() as tmp:
        games = [_game("100", "2026-27", "Alpha", "Beta"),
                 _game("101", "2026-27", "Alpha", "Beta")]
        games[0]["home_stats"] = {"fga": 60, "fta": 20, "tov": 12}
        games[0]["away_stats"] = {"fga": 55, "fta": 15, "tov": 10}
        games[1]["home_stats"] = {"fga": 65, "fta": 18, "tov": 11}
        games[1]["away_stats"] = {"fga": 58, "fta": 22, "tov": 13}
        summaries = {
            "100": _summary("100", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 20, 10, "4-8",
                                      "2-4", "0-0", 5, 2, 1, 1, 0, 2, 3,
                                      1, starter=True)],
                            [_athlete("8", "Ben Bench", 10, 2, "1-3",
                                      "0-1", "0-0", 1, 0, 0, 0, 0, 0, 1,
                                      0)]),
            "101": _summary("101", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 30, 20, "8-12",
                                      "2-5", "2-2", 7, 4, 2, 0, 1, 3, 4,
                                      2, starter=True)],
                            [_athlete("8", "Ben Bench", 5, 0, "0-1",
                                      "0-0", "0-0", 0, 1, 1, 0, 0, 0, 0,
                                      0)]),
        }
        data = _setup(tmp, games, summaries)
        profiles, _ = aggregate_players(data)
        sam = [p for p in profiles["2026-27"] if p["name"] == "Sam Star"][0]
        r = sam["ratings"]
        assert abs(r["ortg"] - 125.628) < 0.01, r
        # Ben Bench is on Beta (away) in this fixture, so Alpha's
        # team minutes are Sam's 50 alone: usage is
        # 100 * (23.88 * 10) / (50 * 164.72), and %Min is 100.
        assert abs(r["poss_pct"] - 2.899) < 0.01, r
        # Alpha played 2 games, so one roster spot had 80 minutes
        # available; Sam played 50 of them.
        assert abs(r["min_pct"] - 62.5) < 0.01, r
        assert abs(r["rpr"] - 6.31) < 0.01, r


def test_top_minutes_floor():
    """A two-minute cameo cannot top the ORtg list by default,
    but does when the floor is turned off."""
    with tempfile.TemporaryDirectory() as tmp:
        games = [_game("100", "2026-27", "Alpha", "Beta"),
                 _game("101", "2026-27", "Alpha", "Beta")]
        games[0]["home_stats"] = {"fga": 60, "fta": 20, "tov": 12}
        games[0]["away_stats"] = {"fga": 55, "fta": 15, "tov": 10}
        games[1]["home_stats"] = {"fga": 65, "fta": 18, "tov": 11}
        games[1]["away_stats"] = {"fga": 58, "fta": 22, "tov": 13}
        summaries = {
            "100": _summary("100", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 20, 10, "4-8",
                                      "2-4", "0-0", 5, 2, 1, 1, 0, 2, 3,
                                      1, starter=True),
                             _athlete("9", "Cal Cup", 2, 8, "3-4",
                                      "0-0", "2-2", 0, 0, 0, 0, 0, 0, 0,
                                      0)],
                            [_athlete("8", "Ben Bench", 10, 2, "1-3",
                                      "0-1", "0-0", 1, 0, 0, 0, 0, 0, 1,
                                      0)]),
            "101": _summary("101", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 30, 20, "8-12",
                                      "2-5", "2-2", 7, 4, 2, 0, 1, 3, 4,
                                      2, starter=True)],
                            [_athlete("8", "Ben Bench", 5, 0, "0-1",
                                      "0-0", "0-0", 0, 1, 1, 0, 0, 0, 0,
                                      0)]),
        }
        data = _setup(tmp, games, summaries)
        profiles, _ = aggregate_players(data)
        all_profiles = profiles["2026-27"]
        cal = [p for p in all_profiles if p["name"] == "Cal Cup"][0]
        # ORtg 100 * 8 / (4 + 0.44 * 2) = 163.9, on 2 of 80
        # available minutes (Alpha played 2 games).
        assert abs(cal["ratings"]["ortg"] - 163.9) < 0.1, cal["ratings"]
        assert abs(cal["ratings"]["min_pct"] - 2.5) < 0.01
        ranked = rank_players(all_profiles, "ortg")
        names = [p["name"] for p in ranked]
        assert "Cal Cup" not in names, names
        assert names[0] == "Sam Star", names
        ranked_off = rank_players(all_profiles, "ortg", min_min_pct=0)
        assert ranked_off[0]["name"] == "Cal Cup", (
            [p["name"] for p in ranked_off])
        # The --top CLI applies the floor and says so in its header.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["--season", "2026-27", "--top", "ortg",
                       "--limit", "5", "--data-dir", str(data)])
        assert rc == 0
        out = buf.getvalue()
        assert "min 40% of team minutes" in out, out
        assert "Cal Cup" not in out, out
        assert "Sam Star" in out, out


def test_zero_attempts_give_null_percentages():
    """No shot attempts: percentages are None, not 0."""
    with tempfile.TemporaryDirectory() as tmp:
        games = [_game("100", "2026-27", "Alpha", "Beta")]
        summaries = {
            "100": _summary("100", "Alpha", "Beta",
                            [_athlete("7", "Sam Star", 5, 0, "0-0",
                                      "0-0", "0-0", 1, 0, 0, 0, 0, 0, 1,
                                      0)],
                            []),
        }
        data = _setup(tmp, games, summaries)
        profiles, _ = aggregate_players(data)
        s = profiles["2026-27"][0]["shooting"]
        assert s == {"fg_pct": None, "fg3_pct": None, "ft_pct": None,
                     "efg_pct": None, "ts_pct": None}, s


if __name__ == "__main__":
    test_aggregation_two_games()
    test_dnp_does_not_count()
    test_seasons_stay_separate()
    test_multi_team_flagged()
    test_bad_and_unmapped_files_skipped()
    test_zero_attempts_give_null_percentages()
    test_ratings_formulas()
    test_ratings_on_real_aggregation()
    test_top_minutes_floor()
    print("all player profile tests passed")
