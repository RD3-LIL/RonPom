#!/bin/bash
# College Ratings daily updater.
#
# Fetches the last few days of 2026-27 games, validates the
# fetched games (fails without pushing on a bad D1 stat row),
# rebuilds player profiles, the returning-minutes prior, the
# team ratings, then generates fresh predictions for the next
# 3 days and scores finished predictions, then builds the site
# (index.html plus one page per team under teams/), and pushes
# all of those files to GitHub: the two rebuilt CSVs, the
# prior, the index, the fresh predictions file, the prediction
# scores, and every teams/*.html page. Predictions and scoring
# run BEFORE the site build on purpose: build_page.py embeds
# the newest predictions file and the live scorecard, so
# generating them after the build left the index showing
# yesterday's predictions labelled stale (Nov 21, 2026).
# The sync record lists exactly the paths in the manifest, so
# it never lies about what a push contained.
#
# Rebuild trigger: the sha256 of data/games_2026_27.json
# before and after the fetch, not the game count, so a
# corrected game (same count, different content) still
# triggers a rebuild.
#
# Why the last 3 days, not just yesterday: a date fetched in
# the morning is marked done, but games played that evening
# are not in yet. Each run re-fetches the last 3 days of
# scoreboards fresh (cached scoreboard files for those dates
# are deleted first, and the dates are removed from
# done_dates), so evening games land on the next morning's
# run. Raw summaries are cached per event and reused, so the
# re-fetch is cheap.
#
# Dates are Chicago dates (TZ=America/Chicago). ESPN's
# scoreboard is keyed by date the same way the original pull
# was done, and a 3-day window absorbs late west-coast games
# that roll to the next date.
#
# Push: github push-files needs Ron's approval on a card each
# time it runs. A scheduled run therefore prepares everything
# and then waits for his one tap to push. If nothing changed
# (no new games), it exits without pushing.
#
# Usage:
#   daily_update.sh [--no-push]
#   DAILY_UPDATE_PUSH=0 daily_update.sh
set -u
cd /home/hatch/workspace/kenpom-clone || exit 1

NO_PUSH=0
if [ "${1:-}" = "--no-push" ] || [ "${DAILY_UPDATE_PUSH:-1}" = "0" ]; then
  NO_PUSH=1
fi

export TZ=America/Chicago
TODAY=$(date +%Y%m%d)
START=$(date -d "$TODAY -3 days" +%Y%m%d)
echo "$(date -Iseconds) daily update: window $START..$TODAY"

GAMES_BEFORE=0
HASH_BEFORE=""
if [ -f data/games_2026_27.json ]; then
  GAMES_BEFORE=$(python3 -c "import json; print(len(json.load(open('data/games_2026_27.json'))))")
  HASH_BEFORE=$(sha256sum data/games_2026_27.json | cut -d' ' -f1)
fi

# Clear the window's cached scoreboards and done_dates so the
# fetch re-pulls those dates fresh. Summaries stay cached.
python3 - "$START" "$TODAY" <<'PYEOF'
import json, sys
from datetime import date, timedelta
from pathlib import Path
start = date(int(sys.argv[1][:4]), int(sys.argv[1][4:6]), int(sys.argv[1][6:8]))
end = date(int(sys.argv[2][:4]), int(sys.argv[2][4:6]), int(sys.argv[2][6:8]))
days = []
d = start
while d <= end:
    days.append(d.strftime('%Y%m%d'))
    d += timedelta(days=1)
for ds in days:
    p = Path(f'data/raw/scoreboard/2026-27/{ds}.json')
    if p.exists():
        p.unlink()
        print(f'  cleared cached scoreboard {ds}')
state_path = Path('data/fetch_state.json')
state = json.loads(state_path.read_text())
sstate = state.get('season_2026-27', {})
done = set(sstate.get('done_dates', []))
removed = sorted(set(days) & done)
sstate['done_dates'] = sorted(done - set(days))
state['season_2026-27'] = sstate
state_path.write_text(json.dumps(state, indent=2))
print(f'  removed {len(removed)} dates from done_dates: {removed}')
PYEOF

python3 fetch_full.py --season 2026-27 --start "$START" --end "$TODAY" || {
  echo "fetch failed, stopping (state is checkpointed, retry tomorrow)"
  exit 1
}

# Validation gate: validate_full.py prints the per-season
# summary, then the gate below fails the run (without pushing)
# if any D1-vs-D1 game has a bad stat row. A bad row is a
# D1 game that is not flagged stats_missing but has bad
# fga/fta/orb/tov, or a played D1 game (not 0-0) that is
# flagged stats_missing, which is the Nov 10, 2026 bug
# recurring. Postponed 0-0 D1 games are expected to have no
# stats, so they do not fail the gate.
python3 validate_full.py 2026-27 || exit 1
python3 - <<'PYEOF'
import json, sys
games = json.load(open('data/games_2026_27.json'))
bad = []
n_missing = 0
for g in games:
    if not (g.get('home_conf_id') and g.get('away_conf_id')):
        continue
    if g.get('stats_missing'):
        n_missing += 1
        if not (g.get('home_score') == 0 and g.get('away_score') == 0):
            bad.append((g['event_id'], 'stats_missing but played'))
        continue
    for side in ('home_stats', 'away_stats'):
        s = g[side]
        if not (isinstance(s.get('fga'), int) and s['fga'] > 0
                and isinstance(s.get('fta'), int) and s['fta'] > 0):
            bad.append((g['event_id'], side, 'bad fga/fta'))
        if s.get('orb') is None or s.get('tov') is None:
            bad.append((g['event_id'], side, 'missing orb/tov'))
print(f'validation gate: {len(bad)} bad D1 rows, '
      f'{n_missing} stats_missing D1 games')
if bad:
    print(f'bad D1 rows: {bad[:10]}')
    sys.exit(1)
PYEOF
if [ "$?" -ne 0 ]; then
  echo "validation gate failed, stopping without pushing"
  exit 1
fi

GAMES_AFTER=$(python3 -c "import json; print(len(json.load(open('data/games_2026_27.json'))))")
HASH_AFTER=$(sha256sum data/games_2026_27.json | cut -d' ' -f1)
STATS_MISSING=$(python3 -c "import json; print(sum(1 for g in json.load(open('data/games_2026_27.json')) if g.get('stats_missing')))")
echo "games: $GAMES_BEFORE -> $GAMES_AFTER (stats_missing: $STATS_MISSING) hash ${HASH_BEFORE:0:8} -> ${HASH_AFTER:0:8}"
# Hash gate, not length only: a corrected game (same count,
# different content, e.g. a re-fetched boxscore) must still
# trigger a rebuild, so compare the file hash, not the count.
if [ "$GAMES_AFTER" -eq "$GAMES_BEFORE" ] && [ "$HASH_AFTER" = "$HASH_BEFORE" ]; then
  echo "no changes to games file, nothing to rebuild or push"
  exit 0
fi

python3 player_profiles.py --season 2026-27 || exit 1
python3 build_prior_2026.py || exit 1
python3 write_ratings.py 2026-27 || exit 1

# Fresh predictions for the next 3 days, from the ratings
# just built, plus scoring of any predictions whose games
# have now finished. These run BEFORE build_page.py: the
# index embeds the newest predictions file and the live
# scorecard, so generating them after the build left the
# index a day stale. A scoring failure stops the run without
# pushing, so a stale or broken predictions file never goes
# live. The predictions file is dated by run date, matching
# the existing data/predictions_YYYY_MM_DD.csv names.
PRED_FILE="data/predictions_$(date +%Y_%m_%d).csv"
python3 predict.py --days 3 --date "$TODAY" --out "$PRED_FILE" || exit 1
python3 score_predictions.py || {
  echo "prediction scoring failed, stopping without pushing"
  exit 1
}

python3 build_page.py || exit 1
python3 sharp_rating.py || exit 1
python3 build_player_pages.py || exit 1
python3 build_distributions.py || exit 1

if [ "$NO_PUSH" -eq 1 ]; then
  echo "push skipped (--no-push), files rebuilt locally"
  exit 0
fi

# The manifest is the two rebuilt CSVs, the prior, the index,
# the fresh predictions file and the prediction scores, every
# team page build_page.py just wrote, and every player profile
# page build_player_pages.py just wrote (top-25 teams only).
# nullglob so an (impossible after a successful build) empty
# dir would expand to nothing instead of a literal "*.html".
# NOTE: this manifest is now about 730 files / 15 MB. A single
# push-files call that big already failed with HTTP 413 on
# Nov 20 (the 370-file team-pages push), so if this push fails
# with 413, split it into batches of about 90 files / 1.7 MB
# as the Nov 20 fix did, index plus data first, then team
# pages, then player pages, recording each confirmed SHA in
# the sync record before the next batch.
shopt -s nullglob
TEAM_PAGES=(teams/*.html)
PLAYER_PAGES=(players/*.html)
printf '%s\0' data/players_2026_27.csv data/ratings_2026_27.csv data/prior_2026_27.json index.html distributions.html "$PRED_FILE" data/prediction_scores.csv "${TEAM_PAGES[@]}" "${PLAYER_PAGES[@]}" > /home/hatch/workspace/ronpom-push-manifest.bin

# Sync-base check: the branch head must match the last sync
# record entry, or someone else pushed since our last run.
# If it moved, stop and let a human reconcile; never push
# blind over an unknown head.
SYNC_RECORD=/home/hatch/workspace/kenpom-clone.muse-github-snapshot-sync.json
LAST_SHA=$(python3 -c "import json; print(json.load(open('$SYNC_RECORD'))[-1]['commit_sha'])")
LIVE_SHA=$(/opt/hatch/bin/github call-read-tool --name list_commits --arguments-json '{"owner":"RD3-LIL","repo":"RonPom","branch":"main","perPage":1}' 2>/dev/null | python3 -c "import sys, json; d = json.load(sys.stdin); print(json.loads(d['result']['content'][0]['text'])[0]['sha'])")
if [ "$LIVE_SHA" != "$LAST_SHA" ]; then
  echo "branch head moved ($LAST_SHA -> $LIVE_SHA), stopping without pushing"
  exit 1
fi

PUSH_OUT=$(/opt/hatch/bin/github push-files --owner RD3-LIL --repo RonPom --branch main \
  --message "Daily update: $GAMES_AFTER games through $TODAY" \
  --source-dir /home/hatch/workspace/kenpom-clone \
  --paths-file /home/hatch/workspace/ronpom-push-manifest.bin 2>&1) || {
  echo "push failed or was not approved; files are rebuilt locally"
  echo "$PUSH_OUT"
  exit 1
}
NEW_SHA=$(echo "$PUSH_OUT" | python3 -c "import sys, json; d = json.load(sys.stdin); print(json.loads(d['result']['content'][0]['text'])['object']['sha'])" 2>/dev/null)
if [ -z "$NEW_SHA" ]; then
  echo "push output did not include a commit SHA; sync record NOT updated"
  echo "$PUSH_OUT"
  exit 1
fi
python3 - "$NEW_SHA" <<'PYEOF'
import json, os, sys, uuid
from pathlib import Path
rec_path = '/home/hatch/workspace/kenpom-clone.muse-github-snapshot-sync.json'
records = json.load(open(rec_path))
# Paths come from the manifest just pushed, not a hardcoded
# list, so the record matches the commit exactly (including
# all the team pages).
manifest = Path('/home/hatch/workspace/ronpom-push-manifest.bin').read_bytes()
paths = [p for p in manifest.decode('utf-8').split('\0') if p]
records.append({
    'owner': 'RD3-LIL', 'repo': 'RonPom', 'branch': 'main',
    'source_dir': '/home/hatch/workspace/kenpom-clone',
    'commit_sha': sys.argv[1],
    'paths': paths,
})
tmp = rec_path + '.tmp-' + uuid.uuid4().hex[:8]
with open(tmp, 'w') as f:
    json.dump(records, f, indent=2)
os.replace(tmp, rec_path)
print(f'sync record updated, head {sys.argv[1][:8]}')
PYEOF
echo "pushed daily update ($GAMES_AFTER games through $TODAY)"
