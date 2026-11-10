"""Fetch free college basketball games from ESPN's public scoreboard/summary endpoints.
Scope: Nov 2-9, 2026, ALL games ESPN lists (77 events in that window).
Stores raw JSON in data/games.json. No KenPom data, no paywall, no login.
Light use: 1 summary request per game, 0.6s pause.
Note: ESPN's scoreboard in this window lists only a subset of D1 games,
so this is an early-season prototype, 1-2 games per team, no preseason prior.
"""
import json, time, urllib.request
from pathlib import Path
HERE = Path(__file__).parent
DATA = HERE / "data"
DATA.mkdir(exist_ok=True)
HEADERS = {'User-Agent': 'Mozilla/5.0 (kenpom-clone prototype)'}
def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

games = []
for date in ['20261102','20261103','20261104','20261105','20261106','20261107','20261108','20261109']:
    d = get(f'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={date}&limit=500')
    for ev in d.get('events', []):
        comps = ev['competitions'][0]['competitors']
        eid = ev['id']
        try:
            s = get(f'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={eid}')
            time.sleep(0.6)
        except Exception as e:
            print('summary failed', eid, e)
            continue
        teams = {}
        for t in s['boxscore']['teams']:
            stats = {x['name']: x['displayValue'] for x in t['statistics']}
            fg = stats.get('fieldGoalsMade-fieldGoalsAttempted','0-0').split('-')
            ft = stats.get('freeThrowsMade-freeThrowsAttempted','0-0').split('-')
            teams[t['team']['displayName']] = {
                'team_id': t['team']['id'], 'abbr': t['team']['abbreviation'],
                'fga': int(fg[1]), 'fta': int(ft[1]),
                'orb': int(stats.get('offensiveRebounds',0)),
                'tov': int(stats.get('totalTurnovers',0)),
            }
        scores = {}
        home_away = {}
        for c in comps:
            scores[c['team']['displayName']] = int(c.get('score',0))
            home_away[c['team']['displayName']] = c.get('homeAway')
        if len(teams) != 2:
            continue
        names = list(teams.keys())
        home = next((n for n in names if home_away.get(n)=='home'), names[0])
        away = next((n for n in names if n != home), names[1])
        games.append({'date': date, 'event_id': eid, 'home': home, 'away': away,
                      'home_score': scores[home], 'away_score': scores[away],
                      'home_stats': teams[home], 'away_stats': teams[away]})
        print(date, away, scores[away], 'at', home, scores[home])
    print(date, 'total so far', len(games))
(DATA / 'games.json').write_text(json.dumps(games, indent=2))
print('saved', len(games), 'games')
