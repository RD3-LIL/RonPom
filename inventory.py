"""Inventory pass for the KenPom-style model data grab.

Loops the ESPN scoreboard (groups=50, the Division I group) for every
date in the two seasons and counts events, teams, and D1-filtered games.
No summary calls, so this is fast. No KenPom data, no paywall, no login.

Key finding baked in here: the DEFAULT scoreboard (no groups param)
returns only featured games (18 events on 2026-11-02). With
groups=50 it returns the full slate (182 events that day).
D1 filter: a team is D1 if it has a conferenceId in the scoreboard
payload. Non-D1 opponents (Adams State, Reinhardt, etc.) have no
conferenceId. This is captured from the scoreboard, because the
summary payload does NOT carry conferenceId.

Usage:
    python3 inventory.py
Writes:
    data/inventory.json   per-date counts for both seasons
    data/inventory.md     human-readable summary
"""
import json, sys, time, urllib.request, urllib.error
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
DATA.mkdir(exist_ok=True)
HEADERS = {'User-Agent': 'Mozilla/5.0 (kenpom-clone inventory)'}
BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard'

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def inventory_season(label, start, end):
    rows = []
    all_teams = set()
    d1_teams = set()
    non_d1_teams = set()
    total_events = 0
    d1_vs_d1 = 0
    d1_vs_non = 0
    non_vs_non = 0
    for d in daterange(start, end):
        ds = d.strftime('%Y%m%d')
        try:
            payload = get(f'{BASE}?dates={ds}&limit=500&groups=50')
        except Exception as e:
            print(label, ds, 'SCOREBOARD FAILED', e)
            rows.append({'date': ds, 'events': None, 'error': str(e)})
            time.sleep(0.5)
            continue
        events = payload.get('events', [])
        day_d1_vs_d1 = 0
        for ev in events:
            comps = ev.get('competitions', [{}])[0].get('competitors', [])
            if len(comps) != 2:
                continue
            flags = []
            for c in comps:
                t = c.get('team', {})
                name = t.get('displayName')
                all_teams.add(name)
                if t.get('conferenceId'):
                    d1_teams.add(name)
                    flags.append(True)
                else:
                    non_d1_teams.add(name)
                    flags.append(False)
            if all(flags):
                day_d1_vs_d1 += 1
                d1_vs_d1 += 1
            elif any(flags):
                d1_vs_non += 1
            else:
                non_vs_non += 1
        total_events += len(events)
        rows.append({'date': ds, 'events': len(events), 'd1_vs_d1': day_d1_vs_d1})
        if len(events):
            print(label, ds, len(events), 'events,', day_d1_vs_d1, 'D1-vs-D1, cum', total_events)
        time.sleep(0.3)
    summary = {
        'label': label,
        'start': start.isoformat(), 'end': end.isoformat(),
        'days': len(rows),
        'total_events_groups50': total_events,
        'unique_teams_all': len(all_teams),
        'unique_d1_teams_conferenceId': len(d1_teams),
        'unique_non_d1_teams_no_conferenceId': len(non_d1_teams),
        'd1_vs_d1_games': d1_vs_d1,
        'd1_vs_non_d1_games': d1_vs_non,
        'non_d1_vs_non_d1_games': non_vs_non,
        'non_d1_team_names': sorted(non_d1_teams),
        'per_date': rows,
    }
    return summary

if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--season') + 1] if '--season' in sys.argv else None
    out = {}
    existing = DATA / 'inventory.json'
    if existing.exists() and only:
        out = json.loads(existing.read_text())
    seasons = {
        '2024-25': ('2024-25', date(2024, 11, 4), date(2025, 4, 7)),
        '2025-26': ('2025-26', date(2025, 11, 3), date(2026, 4, 6)),
        '2026-27': ('2026-27', date(2026, 11, 2), date(2026, 11, 9)),
    }
    for key, (label, start, end) in seasons.items():
        if only and key != only:
            continue
        out[f'season_{key.replace("-", "_")}'] = inventory_season(label, start, end)
    (DATA / 'inventory.json').write_text(json.dumps(out, indent=2))
    lines = ['# Scoreboard inventory (groups=50)', '']
    for key, s in out.items():
        lines += [
            f"## {s['label']} ({s['start']} to {s['end']}, {s['days']} days)",
            f"- Total events (groups=50): {s['total_events_groups50']}",
            f"- Unique teams, all: {s['unique_teams_all']}",
            f"- Unique D1 teams (conferenceId present): {s['unique_d1_teams_conferenceId']}",
            f"- Unique non-D1 teams (no conferenceId): {s['unique_non_d1_teams_no_conferenceId']}",
            f"- D1-vs-D1 games: {s['d1_vs_d1_games']}",
            f"- D1-vs-non-D1 games: {s['d1_vs_non_d1_games']}",
            f"- Non-D1-vs-non-D1 games: {s['non_d1_vs_non_d1_games']}",
            '',
        ]
    (DATA / 'inventory.md').write_text('\n'.join(lines))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'per_date'} for k, v in out.items()}, indent=2))
