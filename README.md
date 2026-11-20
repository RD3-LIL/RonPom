# KenPom-like college basketball ratings

A real database + Python ratings engine, not a scrape of KenPom.
No KenPom data, no paywall, no login. Free ESPN box scores only.

Last updated: Nov 20, 2026. Current season: 2026-27, 1,070 events,
801 D1 games used, 365 teams, 1-7 games per team. Illinois #1,
Net +37.6 (AdjO 130.8, AdjD 93.2, AdjT 74.7, 5 GP). Daily update
runs 6:00 AM Chicago time; the site and CSVs update with it.
Predictions are wired into the daily update too: predict.py
runs after the ratings rebuild, so the predictions file is
fresh each morning (current file: Nov 20). If the file ever
lags the ratings, the site labels it stale instead of
presenting it as current.

## Method (current)

Possessions (Dean Oliver / KenPom formula):
  Poss = FGA - ORB + TOV + 0.44 * FTA

Raw efficiency, per 100 possessions:
  OffEff = 100 * points / possessions
  DefEff = 100 * opponent points / possessions
  Tempo = possessions per game

Adjusted efficiency is solved, not one-pass adjusted. `solver.py`
runs damped Gauss-Seidel on y_ij = AdjO_i + AdjD_j - league_avg,
with a preseason prior and home court off by default. Net = AdjO - AdjD.
The 2026-27 prior is noshrinkw600, adopted Nov 14, 2026: a team's
own 2025-26 final rating, regressed 0.85 toward the league average,
weight 600 possessions scaled by informed returning-minutes share,
no minutes fade (see `build_prior_2026.py` and `write_ratings.py`).
2024-25 and 2025-26 still use a league-average prior.

The one-pass additive adjustment (v1) was the prototype; it is
kept in the history note below, not the current method.

## History: the Nov 2-8 prototype

The first version ran on 57 games, 84 teams, Nov 2-8, 2026, from
ESPN's public scoreboard/summary endpoints (`fetch_games.py`).
Excluded: not-yet-played games (Nov 9, 0-0), and obvious non-D1
opponents. League avg OffEff 104.2, tempo 72.4. Illinois: AdjO
106.6, AdjD 96.5, Net +10.1, AdjT 74.1, rank 18 of 84
(120-45 vs Fairleigh Dickinson, 112-70 vs Penn).

The prototype used a one-pass additive adjustment (v1):
  AdjO = RawO + (league_avg - avg opponent RawD)
  AdjD = RawD + (league_avg - avg opponent RawO)
  AdjT = RawT + (league_avg_tempo - avg opponent RawT)

On the same 57 games, solver v2 gave Illinois AdjO 115.3, AdjD
94.4, Net +20.9, AdjT 75.9, rank 1 of 84 (v1: 106.6, 96.5,
+10.1, 74.1, rank 18). Spearman rank correlation v1 vs v2 was
only 0.496, mean absolute rank change 19.2. The biggest v2 fix
was Chattanooga: v1 ranked it 1st (Net +25.9) after losing its
only game, v2 had it at Net -1.4. The 17-way tie at Net 0 in v1
is gone. But v2 was still noisy on that tiny sample: Illinois
at rank 1 said more about two blowouts of weak teams than about
Illinois, and a prior on one team in a tiny component could even
push its Net the "wrong" way (see solver.py). The real prior
from last season is now in place for 2026-27 (noshrinkw600, see
Method above), so that caveat no longer applies in the same way.

## Solver (current)

`python3 solver.py` runs the solve: damped Gauss-Seidel on the
system y_ij = AdjO_i + AdjD_j - league_avg, with a prior
(default: league average, 300 possessions, about 4 games of
weight) and home court off by default (pass `--home-court 1.5`
to enable it). It converged in 33 iterations on the prototype.
`prior.py` builds a preseason prior from last season's ratings
plus returning minutes (formula in that file, no minutes data
invented). `rubric.md` defines how to compare to KenPom without
scraping or using his paywall. Run `python3 test_solver.py` for
the full check, including a synthetic 8-team season where the
solver recovers the true ordering (Spearman 0.9 or better).

## Team ratings (full seasons)

`python3 write_ratings.py` runs solver v2 on each consolidated
season and writes `data/ratings_<season>.csv` (rank, team, GP,
AdjO, AdjD, Net, AdjT). Those CSVs are in the repo; the games
JSONs are not, they are about 15 MB per full season.

- 2024-25: 5,759 D1 games used, 364 teams. 1 Duke Net +37.7,
  2 Houston +34.3, 3 Auburn +32.8. Illinois rank 14, Net +23.3.
- 2025-26: 5,752 D1 games used, 365 teams. 1 Michigan +37.3,
  2 Duke +36.2, 3 Arizona +33.9. Illinois rank 5, Net +31.1.
- 2026-27 (current, Nov 20, 2026): 801 D1 games used, 1,070 events,
  365 teams, 1-7 games per team. League OffEff 107.2, tempo 69.8,
  solver converged in 36 iterations. 1 Illinois Net +37.6
  (AdjO 130.8, AdjD 93.2, AdjT 74.7, 5 GP), 2 Duke +33.7,
  3 Houston +33.5, 4 Michigan +31.3, 5 St. John's +29.4.
  Early season, and Illinois at rank 1 is still mostly blowouts
  plus a small sample, not a real claim, even though 2026-27 now
  uses the real noshrinkw600 preseason prior (see `write_ratings.py`),
  not the league-average prior the prototype used.

## Honest limits (read this before trusting the ranking)

1. Early season, 1-7 games per team. The noshrinkw600 preseason
   prior helps, and KenPom leans on priors early in the season
   for exactly this reason, but the top of the table is still
   mostly blowout noise, not a real ranking. Big early wins are
   counted at full value, so blowouts move teams a lot.
2. The prototype one-pass adjustment (v1) is not the current
   method. The current solver (v2, damped Gauss-Seidel) does
   converge, 36 iterations on Nov 20, but on 1-2 game blowouts
   an early version diverged: a bad team's adjusted defense
   explodes and collapses its opponents' offense. The one-pass
   version was stable, but it had a known flaw: a team with only
   one game, against an opponent who also played only that game,
   gets AdjO = AdjD = league average and Net 0, because there
   is no other information to adjust with. Those teams all tie
   in the middle of the table. That is the math telling you it
   does not know yet.
3. Non-D1 games are excluded from the ratings solve (263 skipped
   on Nov 20), and 6 games were skipped for zero possessions.
   ESPN's scoreboard with groups=50 returns the full slate,
   unlike the default scoreboard which returns only featured games.

Next step if you want to take it further: keep updating daily as
the sample grows, and re-check the prior and the solve against
KenPom's published numbers as the season fills in.

## Data grab (full, Nov 2026)

`fetch_full.py` pulls three seasons from the free ESPN endpoints
(scoreboard with groups=50, full summary JSON per game):
2024-25 (Nov 4, 2024 to Apr 7, 2025), 2025-26 (Nov 3, 2025 to
Apr 6, 2026), and 2026-27 to date (Nov 2-20, 2026, 1,070 events).
Raw summaries
live in `data/raw/summary/{event_id}.json`, parsed games in
`data/games_2024_25.json`, `data/games_2025_26.json`,
`data/games_2026_27.json`. Teams list in `data/teams_parsed.json`
(365 teams). See `data/inventory.md` for per-season counts.
Checkpointed per date, so a re-run resumes where it left off.

## Player Profiles

`player_profiles.py` aggregates the raw box scores into per-player,
per-season profiles. It reads only local files, no network calls.

```
python3 player_profiles.py
    # writes data/players_2026_27.json and .csv, same for 2025-26
python3 player_profiles.py --season 2026-27 --team "Illinois Fighting Illini"
python3 player_profiles.py --season 2026-27 --player "Stojakovic"
python3 player_profiles.py --season 2026-27 --top pts_per_game --min-games 2 --limit 10
```

Each profile carries totals, per-game and per-40 numbers, shooting
splits (FG%, 3P%, FT%, eFG%, TS%), and KenPom-style ratings: ORtg
(simplified approximation, points per 100 possessions used, no
assist credit), %Poss usage, %Min, and RPR, our own
single-number rating (not KenPom's proprietary kPOY). The full JSON
stays local (too large for the push route); the repo gets the CSV.
Leaderboards (`--top`) have a minutes floor: a player must have
played at least 40% of his team's minutes to qualify, so a
two-minute cameo cannot top the ORtg list. Use `--min-min-pct 0`
to turn the floor off, or another number to change it.

Each profile has totals (GP, GS, MIN, PTS, FGM/FGA, 3PM/3PA, FTM/FTA,
REB, OREB, DREB, AST, TO, STL, BLK, PF), per-game and per-40 numbers,
and shooting: FG%, 3P%, FT%, eFG% = (FGM + 0.5*3PM)/FGA,
TS% = PTS / (2*(FGA + 0.44*FTA)). Percentages are null when the
denominator is zero. DNP players are excluded, so they do not count
as a game played. A player id appearing for two teams in one season
gets two profiles and is flagged in the run output.

The JSON file is the full local version (totals, per-game, per-40,
shooting, headshot URL). The CSV is a compact version with totals
plus per-game PTS/REB/AST and shooting, made for GitHub, because
the full JSON is too large for the snapshot push route (HTTP 413
above about 5 MB). Per-40 can be recomputed from totals and
minutes, and the headshot URL is deterministic from the ESPN
athlete id.

Current state (Nov 20, 2026):
2024-25: 6,298 events in `data/games_2024_25.json`, 5,759 D1
games used, 9,812 players in `data/players_2024_25.csv`.
2025-26: 6,318 events, 5,752 D1 games used, 10,027 players.
2026-27 to date: 1,070 events in `data/games_2026_27.json`, 801
D1 games used, 7,962 players, up to 7 GP.
Re-run `python3 player_profiles.py` to rebuild all three files
from the raw summaries on disk.
Tests: `python3 test_player_profiles.py`.

Player-stats research, corrected after a Nov 18 fresh-context
review (Block verdict, 7 blockers fixed): see
`docs/player-stats-research.md`. Research only, no code changed
by that doc; Phase 1 is not built yet.

Honest limits: no height, weight, or class year until rosters run
(`fetch_rosters.py`, not started yet), so profiles have no bio fields.
Early-season numbers are 1-2 game samples, so per-game leaders are
noise (top 2026-27 scorer at min 2 games and 40% of team minutes
is Dior Johnson, UCF, 28.8 PPG on 5 games). eFG% and TS% can read over 100% on tiny
samples when a player scores almost only on threes; that is the
standard formula, not a bug. One data quirk: athlete id 5325549
(Jeremiah White) appears for two non-D1 teams in 2025-26 (Paine
and Bluefield, 1 game each), likely an ESPN id reuse, not a
mid-season transfer. Verification: in a 25-game sample of
2026-27, summed player points matched the parsed team score in
25 of 25 games, both teams.

## Benchmark rubric (later step, NOT an input)

KenPom's published ratings are the target to get close to, not
data to train on. Do not scrape his site or paywall as input.
After our model is built, the check is: take his published
AdjO, AdjD, AdjT and Net for a given date, for Illinois and a
small sample of top teams, and measure the gap to ours, then
tune the prior and the iterative solve until we are close.
That comparison needs only a handful of hand-recorded numbers
from his public rankings page on that date, not a scrape.

## Run it

The real pipeline, in order. Stdlib only, no dependencies.
`fetch_full.py` and `predict.py` are the only steps that touch
the network; the rest read local files only.

```
python3 fetch_full.py --season 2026-27 --start 20261117 --end 20261120
    # re-pull ESPN scoreboards and summaries for a date window;
    # checkpointed, so a re-run resumes where it left off
python3 player_profiles.py --season 2026-27
    # rebuild data/players_2026_27.json and .csv from the raw summaries
python3 build_prior_2026.py
    # rebuild the noshrinkw600 preseason prior, data/prior_2026_27.json
python3 write_ratings.py 2026-27
    # solve and write data/ratings_2026_27.csv
python3 build_page.py
    # rebuild index.html and every teams/*.html page
python3 predict.py --days 3
    # upcoming-game spreads, writes data/predictions_YYYY_MM_DD.csv
python3 score_predictions.py
    # score finished predictions into data/prediction_scores.csv
```

`daily_update.sh` runs the pipeline every morning at
6:00 AM Chicago time (fetch the last 3 days, profiles, prior,
ratings, site), then runs `predict.py --days 3` and
`score_predictions.py` from the fresh ratings, and pushes the
rebuilt files to GitHub after one approval tap. If the
predictions file ever lags the ratings, the site labels it
stale instead of presenting it as current.

Tests: `python3 test_solver.py` (solver and prior checks),
`python3 test_player_profiles.py`, `python3 test_predict.py`,
and the rest of `test_*.py`. Run them all with:

```
for f in test_*.py; do python3 "$f" || exit 1; done
```

## What is local-only (reproducibility)

The repo is a curated subset, not a full rebuild kit. These
files are intentionally local-only and are covered by
`.gitignore`, so a fresh clone cannot rebuild the site without
re-fetching:

- `data/raw/` (about 5.9 GB): the raw ESPN summary JSONs.
- `data/games_*.json` (about 15 MB per full season): parsed games.
- `data/players_*.json` (about 7-9 MB each): full player profiles.
- `data/teams.json`, `data/recruits_*.json`: team and recruit lists.
- `kenpom.db`: SQLite database from the prototype pipeline.

What the repo does carry: the derived CSVs
(`data/ratings_*.csv`, `data/players_*.csv`), the prior
(`data/prior_2026_27.json`), the built site (`index.html`,
`teams/*.html`), and all the code. With the local data files
present, the pipeline in "Run it" rebuilds everything. From
scratch, `fetch_full.py` re-pulls all three seasons from the
free ESPN endpoints, then the rest of the pipeline runs on
local files. No KenPom data is used anywhere.
