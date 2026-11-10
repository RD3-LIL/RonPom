"""Full data grab for the KenPom-style model (data step only).

Pulls, from free ESPN public endpoints only, no KenPom data, no paywall:
  - scoreboard (groups=50, the Division I group) for every date
  - FULL raw summary JSON per completed game
  - teams list (id, name, abbreviation, slug)

Seasons (default order: smallest first, so the pipeline validates fast):
  2026-27  2026-11-02 .. 2026-11-09  (to date)
  2025-26  2025-11-03 .. 2026-04-06  (full)
  2024-25  2024-11-04 .. 2025-04-07  (full, for prior + backtest)

Why groups=50: the default scoreboard returns only featured games
(18 events on 2026-11-02). With groups=50 it returns the full slate
(182 events that day). D1 identity: a team is D1 if it has a
conferenceId in the scoreboard payload; non-D1 opponents have none.
That conferenceId is captured from the scoreboard, because the
summary payload does NOT carry it.

Why summaries are required: the scoreboard's team statistics lack
offensiveRebounds and totalTurnovers, both needed for possessions
(FGA - ORB + TOV + 0.44*FTA). The summary boxscore has them, plus
player box scores (minutes), pickcenter spread/over-under, and
per-play win probability.

Checkpointing: the unit of work is one date. Per date we save
  data/raw/scoreboard/{season}/{YYYYMMDD}.json   (raw scoreboard)
  data/parsed/{season}/{YYYYMMDD}.json           (parsed games)
  data/raw/summary/{event_id}.json               (FULL raw summary)
A date with a parsed file is skipped on re-run. A summary file that
already exists and parses is reused, not re-fetched. Failures are
logged to data/fetch_failures.jsonl and retried on the next run.
State is in data/fetch_state.json, updated after every date.

Rate limit: 0.9s between summary calls, 0.3s between scoreboard
calls. HTTP 429 / 5xx / timeout: retry up to 4 times with
backoff 2s, 5s, 10s, 30s.

Parsed game record (per game):
  date, event_id, season, home, away, home_id, away_id,
  home_conf_id, away_conf_id (conferenceId from scoreboard, None for non-D1),
  home_score, away_score, neutral_site, conference_game,
  overtime (linescores > 2 periods), venue, status,
  home_stats / away_stats: FULL team stat dict (name -> displayValue)
    plus fga, fta, orb, tov as ints for convenience,
  spread, over_under (from pickcenter, DraftKings, if present),
  home_win_prob_final (last winprobability entry, if present),
  odds (raw, if present, usually empty).

Usage:
  python3 fetch_full.py                  # all seasons, in order above
  python3 fetch_full.py --season 2026-27 # one season
  python3 fetch_full.py --season 2026-27 --start 20261102 --end 20261102  # one date (test)
  python3 fetch_full.py --teams-only      # just the teams list
"""
import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
RAW_SB = DATA / "raw" / "scoreboard"
RAW_SUM = DATA / "raw" / "summary"
PARSED = DATA / "parsed"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.espn.com/',
}
SB_BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard'
SUM_BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary'
TEAMS_URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=1000'

SEASONS = {
    '2026-27': (date(2026, 11, 2), date(2026, 11, 9)),
    '2025-26': (date(2025, 11, 3), date(2026, 4, 6)),
    '2024-25': (date(2024, 11, 4), date(2025, 4, 7)),
}
SUMMARY_SLEEP = 0.9
SCOREBOARD_SLEEP = 0.3


def get_json(url, retries=4):
    """GET JSON with backoff. Returns parsed JSON.

    403/429 backoff is LONG on purpose: ESPN's bot protection tripped
    twice after bursts of requests and cleared only after ~3 minutes
    of no requests. Retrying every few seconds during a penalty box
    just extends it, so a 403 waits 10s, 60s, 180s, 300s.
    """
    backoffs_403 = [10, 60, 180, 300]
    backoffs_other = [2, 5, 10, 30]
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last_err = f'HTTP {e.code}'
            if e.code in (403, 429) and attempt < retries:
                wait = backoffs_403[attempt]
                print(f'  HTTP {e.code} on {url[:80]}... waiting {wait}s (attempt {attempt + 1})', flush=True)
                time.sleep(wait)
                continue
            if e.code in (500, 502, 503, 504) and attempt < retries:
                time.sleep(backoffs_other[attempt])
                continue
            raise
        except Exception as e:  # timeout, connection reset, bad JSON
            last_err = str(e)
            if attempt < retries:
                time.sleep(backoffs_other[attempt])
                continue
            raise
    raise RuntimeError(f'get failed after retries: {last_err}')


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def load_state():
    p = DATA / 'fetch_state.json'
    return json.loads(p.read_text()) if p.exists() else {}


def save_state(state):
    (DATA / 'fetch_state.json').write_text(json.dumps(state, indent=2))


def log_failure(event_id, season, ds, err):
    with open(DATA / 'fetch_failures.jsonl', 'a') as f:
        f.write(json.dumps({'event_id': event_id, 'season': season,
                            'date': ds, 'error': str(err),
                            'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + '\n')


def fetch_teams():
    if (DATA / 'teams_parsed.json').exists() and (DATA / 'teams.json').exists():
        n = len(json.loads((DATA / 'teams_parsed.json').read_text()))
        print(f'teams list: {n} teams already saved, reusing data/teams_parsed.json', flush=True)
        return
    print('fetching teams list ...', flush=True)
    payload = get_json(TEAMS_URL)
    (DATA / 'teams.json').write_text(json.dumps(payload, indent=2))
    teams = payload['sports'][0]['leagues'][0]['teams']
    slim = []
    for entry in teams:
        t = entry['team']
        slim.append({'id': t['id'], 'displayName': t['displayName'],
                     'abbreviation': t.get('abbreviation'),
                     'slug': t.get('slug'), 'location': t.get('location'),
                     'name': t.get('name'), 'shortDisplayName': t.get('shortDisplayName'),
                     'isActive': t.get('isActive')})
    (DATA / 'teams_parsed.json').write_text(json.dumps(slim, indent=2))
    print(f'teams list: {len(slim)} teams saved to data/teams.json + data/teams_parsed.json', flush=True)
    return slim


def parse_team_stats(box_team):
    """Full stat dict + convenience ints from a summary boxscore team."""
    stats = {x['name']: x['displayValue'] for x in box_team.get('statistics', [])}

    def split_int(key, idx=1, default=0):
        try:
            return int(str(stats.get(key, '0-0')).split('-')[idx])
        except Exception:
            return default

    def plain_int(key, default=0):
        try:
            return int(float(str(stats.get(key, default))))
        except Exception:
            return default

    return {
        'all': stats,
        'fga': split_int('fieldGoalsMade-fieldGoalsAttempted'),
        'fta': split_int('freeThrowsMade-freeThrowsAttempted'),
        'orb': plain_int('offensiveRebounds'),
        'tov': plain_int('totalTurnovers'),
    }


def fetch_season(season, start, end):
    state = load_state()
    key = f'season_{season}'
    sstate = state.setdefault(key, {'done_dates': [], 'fetched': 0, 'reused': 0,
                                    'skipped_unplayed': 0, 'failed': 0})
    done = set(sstate['done_dates'])
    for d in daterange(start, end):
        ds = d.strftime('%Y%m%d')
        if ds in done:
            continue
        sb_dir = RAW_SB / season
        sb_dir.mkdir(parents=True, exist_ok=True)
        sb_path = sb_dir / f'{ds}.json'
        if sb_path.exists():
            payload = json.loads(sb_path.read_text())
        else:
            try:
                payload = get_json(f'{SB_BASE}?dates={ds}&limit=500&groups=50')
            except Exception as e:
                # Do not mark the date done; a later run retries it.
                print(f'{season} {ds}: SCOREBOARD FAILED: {e} (date left for retry)', flush=True)
                with open(DATA / 'fetch_failures.jsonl', 'a') as f:
                    f.write(json.dumps({'event_id': None, 'season': season,
                                        'date': ds, 'error': f'scoreboard: {e}',
                                        'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + '\n')
                continue
            sb_path.write_text(json.dumps(payload))
            time.sleep(SCOREBOARD_SLEEP)
        events = payload.get('events', [])
        games = []
        fetched = reused = skipped = failed = 0
        for ev in events:
            comp = ev.get('competitions', [{}])[0]
            status = comp.get('status', {})
            stype = status.get('type', {})
            comps = comp.get('competitors', [])
            if len(comps) != 2 or stype.get('state') != 'post':
                skipped += 1
                continue
            eid = ev['id']
            # scoreboard-side identity + flags
            info = {}
            for c in comps:
                t = c.get('team', {})
                info[c.get('homeAway', '')] = {
                    'name': t.get('displayName'),
                    'id': t.get('id'),
                    'conf_id': t.get('conferenceId'),
                    'score': c.get('score'),
                    'linescores': c.get('linescores', []),
                }
            home = info.get('home') or info[list(info)[0]]
            away = info.get('away') or info[list(info)[1]]
            sum_path = RAW_SUM / f'{eid}.json'
            summary = None
            if sum_path.exists():
                try:
                    summary = json.loads(sum_path.read_text())
                    if not summary.get('boxscore', {}).get('teams'):
                        summary = None
                except Exception:
                    summary = None
            if summary is None:
                try:
                    summary = get_json(f'{SUM_BASE}?event={eid}')
                    RAW_SUM.mkdir(parents=True, exist_ok=True)
                    sum_path.write_text(json.dumps(summary))
                    fetched += 1
                except Exception as e:
                    log_failure(eid, season, ds, e)
                    failed += 1
                    print(f'  {ds} {eid} SUMMARY FAILED: {e}', flush=True)
                    continue
                time.sleep(SUMMARY_SLEEP)
            else:
                reused += 1
            # parse boxscore teams
            box_teams = summary.get('boxscore', {}).get('teams', [])
            if len(box_teams) != 2:
                log_failure(eid, season, ds, f'boxscore teams={len(box_teams)}')
                failed += 1
                continue
            by_id = {}
            for bt in box_teams:
                by_id[bt['team']['id']] = parse_team_stats(bt)
            # match boxscore teams to home/away by team id; fall back to order
            try:
                hs = by_id[home['id']]
                aws = by_id[away['id']]
            except KeyError:
                hs = parse_team_stats(box_teams[0])
                aws = parse_team_stats(box_teams[1])
            pick = summary.get('pickcenter') or []
            spread = ou = None
            if pick:
                spread = pick[0].get('spread')
                ou = pick[0].get('overUnder')
            wp = summary.get('winprobability') or []
            home_wp_final = wp[-1].get('homeWinPercentage') if wp else None
            lines = home.get('linescores') or []
            games.append({
                'date': ds, 'event_id': eid, 'season': season,
                'home': home['name'], 'away': away['name'],
                'home_id': home['id'], 'away_id': away['id'],
                'home_conf_id': home.get('conf_id'), 'away_conf_id': away.get('conf_id'),
                'home_score': int(home['score'] or 0), 'away_score': int(away['score'] or 0),
                'neutral_site': comp.get('neutralSite'),
                'conference_game': comp.get('conferenceCompetition'),
                'overtime': len(lines) > 2,
                'periods': len(lines),
                'venue': (comp.get('venue') or {}).get('fullName'),
                'status': stype.get('description'),
                'home_stats': hs, 'away_stats': aws,
                'spread': spread, 'over_under': ou,
                'home_win_prob_final': home_wp_final,
                'odds': summary.get('odds'),
            })
        parsed_dir = PARSED / season
        parsed_dir.mkdir(parents=True, exist_ok=True)
        (parsed_dir / f'{ds}.json').write_text(json.dumps(games, indent=2))
        sstate['fetched'] += fetched
        sstate['reused'] += reused
        sstate['skipped_unplayed'] += skipped
        sstate['failed'] += failed
        done.add(ds)
        sstate['done_dates'] = sorted(done)
        save_state(state)
        print(f'{season} {ds}: {len(events)} events, {len(games)} games parsed '
              f'(fetched {fetched}, reused {reused}, skipped {skipped}, failed {failed})', flush=True)
    # build consolidated file for the season
    all_games = []
    parsed_dir = PARSED / season
    for p in sorted(parsed_dir.glob('*.json')):
        all_games.extend(json.loads(p.read_text()))
    all_games.sort(key=lambda g: (g['date'], g['event_id']))
    (DATA / f"games_{season.replace('-', '_')}.json").write_text(json.dumps(all_games, indent=2))
    teams = {g['home'] for g in all_games} | {g['away'] for g in all_games}
    print(f'{season} DONE: {len(all_games)} games, {len(teams)} teams '
          f'-> data/games_{season.replace("-", "_")}.json', flush=True)
    return all_games


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', choices=list(SEASONS))
    ap.add_argument('--start', help='YYYYMMDD, limit start date')
    ap.add_argument('--end', help='YYYYMMDD, limit end date')
    ap.add_argument('--teams-only', action='store_true')
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    RAW_SUM.mkdir(parents=True, exist_ok=True)
    try:
        fetch_teams()
    except Exception as e:
        # The season pull does not depend on the teams list (team
        # identity comes from the scoreboard/summary payloads), so do
        # not let a teams-endpoint block kill a multi-hour run.
        # Re-run with --teams-only later to fill it in.
        print(f'WARNING: teams list failed ({e}); continuing without it', flush=True)
    if args.teams_only:
        return
    seasons = [args.season] if args.season else list(SEASONS)
    for season in seasons:
        start, end = SEASONS[season]
        if args.start:
            start = date(int(args.start[:4]), int(args.start[4:6]), int(args.start[6:8]))
        if args.end:
            end = date(int(args.end[:4]), int(args.end[4:6]), int(args.end[6:8]))
        fetch_season(season, start, end)


if __name__ == '__main__':
    main()
