"""Fetch rosters for every D1 team, for each season (prior approximation).

Endpoint: free ESPN site API, same family as scoreboard/summary.
  /teams/{team_id}/roster?season={year}
where year is the season-ending year: 2027 = 2026-27, 2026 = 2025-26,
2025 = 2024-25. The ?season= form returns a postseason snapshot
(10 athletes for Illinois 2025-26 vs 14 on the current roster), so
treat it as a returning-player identity list, not a full depth chart.

Each athlete carries id, name, position, jersey, height, weight, and
experience (Freshman/Sophomore/Junior/Senior years). Combined with
player minutes from the raw summary box scores, this is what lets a
later step approximate KenPom-style returning minutes: which players
were on last season's roster, and how many minutes they played.

Checkpointing: one file per team per season,
  data/raw/rosters/{year}/{team_id}.json
Existing files are skipped. Failures logged to data/roster_failures.jsonl.

Usage:
  python3 fetch_rosters.py                  # all seasons, all teams
  python3 fetch_rosters.py --year 2027      # one season
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.espn.com/',
}
BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams'
YEARS = [2027, 2026, 2025]


def get_json(url, retries=3):
    # 403 waits are long: ESPN's bot protection clears only after
    # minutes of quiet; fast retries extend the penalty box.
    backoffs = [10, 60, 180]
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if attempt < retries:
                time.sleep(backoffs[attempt])
                continue
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, choices=YEARS)
    args = ap.parse_args()
    teams = json.loads((DATA / 'teams_parsed.json').read_text())
    years = [args.year] if args.year else YEARS
    for year in years:
        outdir = DATA / 'raw' / 'rosters' / str(year)
        outdir.mkdir(parents=True, exist_ok=True)
        got = skipped = failed = 0
        for t in teams:
            path = outdir / f"{t['id']}.json"
            if path.exists():
                skipped += 1
                continue
            try:
                payload = get_json(f'{BASE}/{t["id"]}/roster?season={year}')
                path.write_text(json.dumps(payload))
                got += 1
            except Exception as e:
                failed += 1
                with open(DATA / 'roster_failures.jsonl', 'a') as f:
                    f.write(json.dumps({'team_id': t['id'], 'year': year,
                                        'error': str(e)}) + '\n')
            time.sleep(0.3)
        print(f'rosters {year}: fetched {got}, reused {skipped}, failed {failed}', flush=True)


if __name__ == '__main__':
    main()
