# KenPom-like college basketball ratings (prototype)

A real database + Python ratings engine, not a scrape of KenPom.
No KenPom data, no paywall, no login. Free ESPN box scores only.

## Method

Possessions (Dean Oliver / KenPom formula):
  Poss = FGA - ORB + TOV + 0.44 * FTA

Raw efficiency, per 100 possessions:
  OffEff = 100 * points / possessions
  DefEff = 100 * opponent points / possessions
  Tempo = possessions per game

Adjusted efficiency, one pass, additive:
  AdjO = RawO + (league_avg - avg opponent RawD)
  AdjD = RawD + (league_avg - avg opponent RawO)
  AdjT = RawT + (league_avg_tempo - avg opponent RawT)
  Net = AdjO - AdjD

## Data

57 games, 84 teams, Nov 2-8, 2026, from ESPN's public
scoreboard/summary endpoints (`fetch_games.py`).
Excluded: not-yet-played games (Nov 9, 0-0), and obvious
non-D1 opponents (KenPom excludes those too).

## Results, early season

League avg OffEff 104.2, tempo 72.4.
Illinois: AdjO 106.6, AdjD 96.5, Net +10.1, AdjT 74.1, rank 18 of 84.
  120-45 vs Fairleigh Dickinson, 112-70 vs Penn.

## Solver v2 (new)

`python3 solver.py` replaces the one-pass adjustment with a proper
solve: damped Gauss-Seidel on the system y_ij = AdjO_i + AdjD_j
- league_avg, with a prior (default: league average, 300
possessions, about 4 games of weight) and home court off by
default (pass `--home-court 1.5` to enable it). Converges in 33
iterations on the prototype. `prior.py` builds a preseason prior
from last season's ratings plus returning minutes (formula in
that file, no minutes data invented). `rubric.md` defines how to
compare to KenPom without scraping or using his paywall.

Results on the same 57 games: Illinois AdjO 115.3, AdjD 94.4,
Net +20.9, AdjT 75.9, rank 1 of 84 (v1: 106.6, 96.5, +10.1,
74.1, rank 18). Spearman rank correlation v1 vs v2 is only
0.496, mean absolute rank change 19.2. The biggest v2 fix is
Chattanooga: v1 ranked it 1st (Net +25.9) after losing its only
game, v2 has it at Net -1.4. The 17-way tie at Net 0 in v1 is
gone. But v2 is still noisy: Illinois at rank 1 says more about
two blowouts of weak teams plus a league-average prior than
about Illinois, and a prior on one team in a tiny component can
even push its Net the "wrong" way (see solver.py). A real prior
from last season would pull it down. Run `python3 test_solver.py`
for the full check, including a synthetic 8-team season where
the solver recovers the true ordering (Spearman 0.9 or better).

## Honest limits (read this before trusting the ranking)

1. 1-2 games per team, no preseason prior. KenPom leans on
   priors early in the season for exactly this reason.
2. One-pass adjustment, not a full linear-system solve.
   I tried iterating to convergence first: it diverges on
   1-2 game blowouts, a bad team's adjusted defense explodes
   and collapses its opponents' offense. The one-pass version
   is stable, but it has a known flaw: a team with only one
   game, against an opponent who also played only that game,
   gets AdjO = AdjD = league average and Net 0, because
   there is no other information to adjust with. Those teams
   all tie in the middle of the table. That is the math
   telling you it does not know yet.
3. ESPN's scoreboard in this window lists only a subset of
   D1 games (77 events Nov 2-9), so this is not the full
   360-team universe. A real version needs a full-season
   game log, a preseason prior, and a proper solve.

Next step if you want to take it further: pull a full
season of games (or last season, 2025-26, complete), add
a preseason prior, and solve the AdjO/AdjD system properly.

## Data grab (full, Nov 2026)

`fetch_full.py` pulls three seasons from the free ESPN endpoints
(scoreboard with groups=50, full summary JSON per game):
2024-25 (Nov 4, 2024 to Apr 7, 2025), 2025-26 (Nov 3, 2025 to
Apr 6, 2026), and 2026-27 to date (Nov 2-9, 2026). Raw summaries
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
assist credit), %Poss usage, %Min, and RPR, RonPom's own
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

As of the first build (Nov 10, 2026, about 00:04 CST, updated
00:11 CST):
2026-27 complete, 520 games, 6,631 players (6,591 with minutes).
2025-26 partial, 428 games and counting, 6,191 players. Full
2025-26 is 6,318 events. Re-run the same command once the pull
finishes and both files rebuild from the complete data:
`python3 player_profiles.py`. Same for 2024-25 when its pull lands.
Tests: `python3 test_player_profiles.py`.

Honest limits: no height, weight, or class year until rosters run
(`fetch_rosters.py`, not started yet), so profiles have no bio fields.
Early-season numbers are 1-2 game samples, so per-game leaders are
noise (top 2026-27 scorer at min 2 games is Dior Johnson, UCF,
34.5 PPG on 2 games). eFG% and TS% can read over 100% on tiny
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

```
python3 fetch_games.py   # re-pull ESPN games, saves data/games.json
python3 ratings.py       # compute ratings, save kenpom.db
python3 ratings.py Illinois
python3 test_ratings.py
sqlite3 kenpom.db "SELECT * FROM ratings ORDER BY net DESC LIMIT 10;"
```

Stdlib only, no dependencies.
