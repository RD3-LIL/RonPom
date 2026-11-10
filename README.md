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
