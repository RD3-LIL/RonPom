"""Player profiles from the raw ESPN summaries already on disk.

Reads data/raw/summary/{event_id}.json, which holds the full box
score per game, and aggregates per player, per season, per team.

What each raw summary carries, per team in boxscore.players:
  athlete id, displayName, shortName, jersey, position abbreviation,
  headshot URL, starter flag, didNotPlay flag, and a stats array in
  this order: MIN, PTS, FG, 3PT, FT, REB, AST, TO, STL, BLK, OREB,
  DREB, PF. FG / 3PT / FT are "made-attempted" strings.

What it does NOT carry: height, weight, class year. Those come from
the roster pull (fetch_rosters.py), which has not run yet. They are
not invented here; profiles simply have no height/weight/class
until rosters land.

Season assignment comes from the parsed games on disk, never from
the raw header date (the header date is UTC and can be a day off):
  data/games_{season}.json (consolidated) and
  data/parsed/{season}/{YYYYMMDD}.json (per date).
A raw file whose event_id is in no parsed game is skipped and
counted as unmapped. That happens for a date the background pull
is still fetching: its summaries land before its parsed file is
written. Re-run after the pull finishes and those games appear.

Formulas (standard, documented here so they can be checked):
  FG%  = FGM / FGA
  3P%  = 3PM / 3PA
  FT%  = FTM / FTA
  eFG% = (FGM + 0.5 * 3PM) / FGA
  TS%  = PTS / (2 * (FGA + 0.44 * FTA))
  per game = total / GP
  per 40   = total / MIN * 40
Percentages are None when the denominator is zero, never 0 by
default, so a player with no attempts is not shown as a 0% shooter.

DNP handling: a player with didNotPlay true, or with an empty stats
array, does not count as a game played and contributes nothing.

Stdlib only. No network calls. Reads data/raw/ only.

Usage:
    python3 player_profiles.py
        Writes data/players_2026_27.json, data/players_2025_26.json,
        one file per season found in the parsed games on disk.
    python3 player_profiles.py --season 2026-27 --team Illinois
        Prints the Illinois profiles for that season.
    python3 player_profiles.py --season 2026-27 --player "Boakye"
        Prints matching players.
    python3 player_profiles.py --season 2026-27 --top pts_per_game --limit 10
        Prints the top 10 scorers (min 1 game; add --min-games 2 to
        require at least 2 games).
    python3 player_profiles.py --season 2025-26 --out /tmp/p.json
        Writes only that season to the given path.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
RAW_DIR = DATA / "raw" / "summary"

STAT_NAMES = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO",
              "STL", "BLK", "OREB", "DREB", "PF"]

# Totals fields, in the order they are stored on a profile.
TOTAL_FIELDS = ["gp", "gs", "min", "pts", "fgm", "fga", "fg3m", "fg3a",
                "ftm", "fta", "reb", "oreb", "dreb", "ast", "to",
                "stl", "blk", "pf"]


def _parse_int(value):
    """Parse an int from a string like '29' or an int. None on failure."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _parse_made_attempted(value):
    """Parse 'made-attempted' like '9-13' into (made, attempted)."""
    if not value or not isinstance(value, str) or "-" not in value:
        return (0, 0)
    made, _, att = value.partition("-")
    m = _parse_int(made)
    a = _parse_int(att)
    return (m if m is not None else 0, a if a is not None else 0)


def _pct(made, att):
    """A shooting percentage, or None when there were no attempts."""
    if not att:
        return None
    return made / att


def load_game_map(data_dir=DATA):
    """event_id -> parsed game record, from consolidated and per-date files.

    Both sources are read so a season still being pulled (parsed per
    date, no consolidated file yet) maps its finished dates too.
    """
    game_map = {}
    files = sorted(data_dir.glob("games_*.json"))
    for parsed_dir in sorted((data_dir / "parsed").glob("*")):
        if parsed_dir.is_dir():
            files.extend(sorted(parsed_dir.glob("*.json")))
    for path in files:
        try:
            games = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(games, list):
            continue
        for game in games:
            event_id = str(game.get("event_id", ""))
            if event_id and event_id not in game_map:
                game_map[event_id] = game
    return game_map


def _blank_totals():
    return {field: 0 for field in TOTAL_FIELDS}


def aggregate_players(data_dir=DATA, season_filter=None):
    """Aggregate raw summaries into per-player, per-season profiles.

    Returns (profiles_by_season, report) where profiles_by_season is
    {season: [profile, ...]} sorted by total points descending, and
    report is a dict of counts for logging and verification.
    """
    game_map = load_game_map(data_dir)
    raw_dir = Path(data_dir) / "raw" / "summary"
    raw_files = sorted(raw_dir.glob("*.json")) if raw_dir.is_dir() else []

    report = {
        "raw_files": len(raw_files),
        "failed_json": 0,
        "unmapped_events": 0,
        "games_included": {},
        "players_skipped_dnp": 0,
        "player_rows": 0,
        "multi_team_athlete_ids": [],
    }
    # (athlete_id, season, team_id) -> working totals + identity
    working = {}
    # athlete_id -> set of (season, team_id), to flag mid-season moves
    teams_by_athlete = {}

    for raw_path in raw_files:
        event_id = raw_path.stem
        try:
            summary = json.loads(raw_path.read_text())
        except (OSError, ValueError):
            # The background pull may be mid-write on this file.
            report["failed_json"] += 1
            continue
        game = game_map.get(event_id)
        if game is None:
            report["unmapped_events"] += 1
            continue
        season = game.get("season")
        if season_filter and season != season_filter:
            continue
        if season is None:
            report["unmapped_events"] += 1
            continue
        report["games_included"][season] = (
            report["games_included"].get(season, 0) + 1)

        players = summary.get("boxscore", {}).get("players", []) or []
        for team_entry in players:
            team = team_entry.get("team", {}) or {}
            team_id = str(team.get("id", ""))
            team_name = team.get("displayName", "")
            for group in team_entry.get("statistics", []) or []:
                names = group.get("names", []) or STAT_NAMES
                idx = {name: i for i, name in enumerate(names)}
                for athlete_row in group.get("athletes", []) or []:
                    if athlete_row.get("didNotPlay"):
                        report["players_skipped_dnp"] += 1
                        continue
                    stats = athlete_row.get("stats") or []
                    if not stats:
                        report["players_skipped_dnp"] += 1
                        continue
                    athlete = athlete_row.get("athlete", {}) or {}
                    athlete_id = str(athlete.get("id", ""))
                    if not athlete_id:
                        continue
                    key = (athlete_id, season, team_id)
                    if key not in working:
                        working[key] = {
                            "athlete_id": athlete_id,
                            "name": athlete.get("displayName", ""),
                            "short_name": athlete.get("shortName", ""),
                            "team": team_name,
                            "team_id": team_id,
                            "season": season,
                            "jersey": athlete.get("jersey", ""),
                            "position": (athlete.get("position", {}) or {}
                                         ).get("abbreviation", ""),
                            "headshot": (athlete.get("headshot", {}) or {}
                                         ).get("href", ""),
                            "totals": _blank_totals(),
                        }
                    totals = working[key]["totals"]
                    totals["gp"] += 1
                    if athlete_row.get("starter"):
                        totals["gs"] += 1
                    minutes = _parse_int(stats[idx["MIN"]]) \
                        if "MIN" in idx and idx["MIN"] < len(stats) else None
                    totals["min"] += minutes if minutes is not None else 0
                    totals["pts"] += _parse_int(stats[idx["PTS"]]) or 0 \
                        if "PTS" in idx and idx["PTS"] < len(stats) else 0
                    fgm, fga = _parse_made_attempted(
                        stats[idx["FG"]] if "FG" in idx
                        and idx["FG"] < len(stats) else "")
                    totals["fgm"] += fgm
                    totals["fga"] += fga
                    tpm, tpa = _parse_made_attempted(
                        stats[idx["3PT"]] if "3PT" in idx
                        and idx["3PT"] < len(stats) else "")
                    totals["fg3m"] += tpm
                    totals["fg3a"] += tpa
                    ftm, fta = _parse_made_attempted(
                        stats[idx["FT"]] if "FT" in idx
                        and idx["FT"] < len(stats) else "")
                    totals["ftm"] += ftm
                    totals["fta"] += fta
                    for name, field in (("REB", "reb"), ("OREB", "oreb"),
                                        ("DREB", "dreb"), ("AST", "ast"),
                                        ("TO", "to"), ("STL", "stl"),
                                        ("BLK", "blk"), ("PF", "pf")):
                        if name in idx and idx[name] < len(stats):
                            totals[field] += _parse_int(stats[idx[name]]) or 0
                    report["player_rows"] += 1
                    teams_by_athlete.setdefault(athlete_id, set()).add(
                        (season, team_id))

    for athlete_id, teams in teams_by_athlete.items():
        seasons = {}
        for season, team_id in teams:
            seasons.setdefault(season, set()).add(team_id)
        for season, team_ids in seasons.items():
            if len(team_ids) > 1:
                report["multi_team_athlete_ids"].append(
                    {"athlete_id": athlete_id, "season": season,
                     "team_ids": sorted(team_ids)})

    profiles_by_season = {}
    for (athlete_id, season, team_id), entry in working.items():
        totals = entry["totals"]
        gp = totals["gp"]
        minutes = totals["min"]
        profile = dict(entry)
        profile["totals"] = totals
        profile["per_game"] = {
            field: (totals[field] / gp if gp else 0.0)
            for field in ("min", "pts", "reb", "oreb", "dreb", "ast",
                          "to", "stl", "blk", "pf")
        }
        profile["per_40"] = {
            field: (totals[field] / minutes * 40 if minutes else 0.0)
            for field in ("pts", "reb", "oreb", "dreb", "ast",
                          "to", "stl", "blk", "pf")
        }
        profile["shooting"] = {
            "fg_pct": _pct(totals["fgm"], totals["fga"]),
            "fg3_pct": _pct(totals["fg3m"], totals["fg3a"]),
            "ft_pct": _pct(totals["ftm"], totals["fta"]),
            "efg_pct": ((totals["fgm"] + 0.5 * totals["fg3m"])
                        / totals["fga"] if totals["fga"] else None),
            "ts_pct": (totals["pts"] / (2 * (totals["fga"]
                        + 0.44 * totals["fta"]))
                       if totals["fga"] + totals["fta"] else None),
        }
        profiles_by_season.setdefault(season, []).append(profile)

    for season in profiles_by_season:
        profiles_by_season[season].sort(
            key=lambda p: (p["totals"]["pts"], p["totals"]["min"]),
            reverse=True)
    return profiles_by_season, report


def write_players_json(season, profiles, games_included, out_path):
    """Write one season of profiles to a JSON file."""
    payload = {
        "season": season,
        "games_included": games_included,
        "players": profiles,
        "player_count": len(profiles),
        "players_with_minutes": sum(
            1 for p in profiles if p["totals"]["min"] > 0),
        "notes": (
            "Totals and derived stats from ESPN raw box scores on disk. "
            "No height, weight, or class year: rosters have not been "
            "pulled yet. Percentages are null when the denominator is "
            "zero. DNP players are excluded."
        ),
    }
    Path(out_path).write_text(json.dumps(payload, indent=2))
    return out_path


def _fmt_pct(value):
    return f"{100 * value:.1f}%" if value is not None else "-"


def print_profile(profile):
    """One compact line per player, plus a shooting line."""
    t = profile["totals"]
    pg = profile["per_game"]
    s = profile["shooting"]
    print(f'{profile["name"]} ({profile["position"] or "?"}, '
          f'#{profile["jersey"] or "-"}, {profile["team"]}) '
          f'GP {t["gp"]} GS {t["gs"]} MIN {t["min"]} '
          f'PTS {pg["pts"]:.1f} REB {pg["reb"]:.1f} '
          f'AST {pg["ast"]:.1f} STL {pg["stl"]:.1f} '
          f'BLK {pg["blk"]:.1f} TO {pg["to"]:.1f} PF {pg["pf"]:.1f}')
    print(f'    FG {_fmt_pct(s["fg_pct"])} 3P {_fmt_pct(s["fg3_pct"])} '
          f'FT {_fmt_pct(s["ft_pct"])} eFG {_fmt_pct(s["efg_pct"])} '
          f'TS {_fmt_pct(s["ts_pct"])} | per 40: '
          f'PTS {profile["per_40"]["pts"]:.1f} '
          f'REB {profile["per_40"]["reb"]:.1f} '
          f'AST {profile["per_40"]["ast"]:.1f}')


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build player profiles from raw ESPN summaries.")
    parser.add_argument("--season", default=None,
                        help="season to use, e.g. 2026-27 (default: all)")
    parser.add_argument("--team", default=None,
                        help="filter to team names containing this text")
    parser.add_argument("--player", default=None,
                        help="filter to player names containing this text")
    parser.add_argument("--top", default=None,
                        help="rank by this field, e.g. pts_per_game, "
                             "pts, min, reb, ast, pts_per40")
    parser.add_argument("--limit", type=int, default=10,
                        help="how many rows to print with --top")
    parser.add_argument("--min-games", type=int, default=1,
                        help="minimum GP for --top (default 1)")
    parser.add_argument("--out", default=None,
                        help="write the selected season JSON to this path")
    parser.add_argument("--data-dir", default=str(DATA),
                        help="data directory (default data/)")
    args = parser.parse_args(argv)

    profiles_by_season, report = aggregate_players(
        Path(args.data_dir), season_filter=args.season)

    seasons = sorted(profiles_by_season)
    if not seasons:
        print("No player profiles found. Is data/raw/summary/ populated?")
        return 1

    if args.out:
        if len(seasons) != 1:
            print("Use --season with --out so exactly one season is written.")
            return 1
        season = seasons[0]
        write_players_json(season, profiles_by_season[season],
                           report["games_included"].get(season, 0),
                           args.out)
        print(f"Wrote {args.out}: {len(profiles_by_season[season])} players, "
              f"{report['games_included'].get(season, 0)} games")
    else:
        for season in seasons:
            out_path = Path(args.data_dir) / (
                f"players_{season.replace('-', '_')}.json")
            write_players_json(season, profiles_by_season[season],
                               report["games_included"].get(season, 0),
                               out_path)
            print(f"Wrote {out_path}: "
                  f"{len(profiles_by_season[season])} players, "
                  f"{report['games_included'].get(season, 0)} games")

    print(f"Raw files read: {report['raw_files']}, "
          f"failed JSON: {report['failed_json']}, "
          f"unmapped events: {report['unmapped_events']}, "
          f"DNP rows skipped: {report['players_skipped_dnp']}, "
          f"player rows counted: {report['player_rows']}")
    if report["multi_team_athlete_ids"]:
        print("Athletes on two teams in one season: "
              f"{report['multi_team_athlete_ids']}")

    # Query mode: print matching profiles, or a leaderboard.
    selected = [p for season in seasons
                for p in profiles_by_season[season]]
    if args.team:
        selected = [p for p in selected
                    if args.team.lower() in p["team"].lower()]
    if args.player:
        selected = [p for p in selected
                    if args.player.lower() in p["name"].lower()]
    if args.top:
        def _top_key(profile):
            field = args.top
            if field in profile["totals"]:
                return profile["totals"][field]
            if field.endswith("_per_game"):
                return profile["per_game"].get(
                    field[:-len("_per_game")], 0)
            if field.endswith("_per40"):
                return profile["per_40"].get(
                    field[:-len("_per40")], 0)
            if field in profile["shooting"]:
                return profile["shooting"][field] or 0
            raise KeyError(field)
        try:
            selected = [p for p in selected
                        if p["totals"]["gp"] >= args.min_games]
            selected.sort(key=_top_key, reverse=True)
        except KeyError:
            print(f"Unknown --top field: {args.top}")
            return 1
        for profile in selected[:args.limit]:
            print_profile(profile)
    elif args.team or args.player:
        for profile in selected:
            print_profile(profile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
