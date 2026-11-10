"""Validate the full data grab (data step only, no new solver).

For each consolidated games file (data/games_YYYY_YY.json):
  - counts: games, teams, D1-vs-D1 games (both conf_ids present)
  - sanity: every game has fga/fta/orb/tov for both teams, possessions
    in a plausible range, scores > 0 for completed games
  - runs the EXISTING one-pass ratings.compute on the D1-vs-D1 subset
    and prints top 10 by Net plus Illinois, if present
  - for 2026-27, cross-checks the two Illinois games from the original
    prototype (120-45 vs Fairleigh Dickinson, 112-70 vs Penn)

Usage:
    python3 validate_full.py
    python3 validate_full.py 2026-27
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
from ratings import compute, possessions  # noqa: E402


def check_season(season):
    path = DATA / f"games_{season.replace('-', '_')}.json"
    if not path.exists():
        print(f'{season}: MISSING {path}')
        return None
    games = json.loads(path.read_text())
    teams = {g['home'] for g in games} | {g['away'] for g in games}
    d1 = [g for g in games if g.get('home_conf_id') and g.get('away_conf_id')]
    d1_teams = {g['home'] for g in d1} | {g['away'] for g in d1}
    bad = []
    poss_range = []
    for g in games:
        for side in ('home_stats', 'away_stats'):
            s = g[side]
            if not all(isinstance(s.get(k), int) and s[k] > 0 for k in ('fga', 'fta')):
                bad.append((g['event_id'], side, 'missing fga/fta'))
            if s.get('orb') is None or s.get('tov') is None:
                bad.append((g['event_id'], side, 'missing orb/tov'))
        poss_range.append(possessions(g['home_stats']))
    print(f'\n== {season}: {len(games)} games, {len(teams)} teams; '
          f'D1-vs-D1: {len(d1)} games, {len(d1_teams)} teams')
    print(f'   dates: {min(g["date"] for g in games)} .. {max(g["date"] for g in games)}')
    print(f'   possessions per game: min {min(poss_range):.1f}, max {max(poss_range):.1f}')
    print(f'   with spread: {sum(1 for g in games if g.get("spread") is not None)}, '
          f'with win prob: {sum(1 for g in games if g.get("home_win_prob_final") is not None)}, '
          f'OT games: {sum(1 for g in games if g.get("overtime"))}, '
          f'neutral site: {sum(1 for g in games if g.get("neutral_site"))}')
    print(f'   bad stat rows: {len(bad)} {bad[:5]}')
    tms, league_o, league_t = compute(d1)
    ranked = sorted(tms.items(), key=lambda kv: kv[1]['net'], reverse=True)
    print(f'   D1 ratings (existing one-pass): league OffEff {league_o:.1f}, tempo {league_t:.1f}')
    for i, (name, t) in enumerate(ranked[:10], 1):
        print(f'   {i:>3} {name:<32} GP {t["games"]:>2} AdjO {t["adj_o"]:>6.1f} '
              f'AdjD {t["adj_d"]:>6.1f} Net {t["net"]:>6.1f} AdjT {t["adj_t"]:>5.1f}')
    for name, t in tms.items():
        if 'Illinois' in name and 'Chicago' not in name:
            print(f'   Illinois: GP {t["games"]} AdjO {t["adj_o"]:.1f} AdjD {t["adj_d"]:.1f} '
                  f'Net {t["net"]:.1f} AdjT {t["adj_t"]:.1f}')
    return {'season': season, 'games': len(games), 'teams': len(teams),
            'd1_games': len(d1), 'd1_teams': len(d1_teams), 'bad': len(bad)}


if __name__ == '__main__':
    seasons = sys.argv[1:] or ['2024-25', '2025-26', '2026-27']
    for s in seasons:
        check_season(s)
