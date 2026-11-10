# Rubric: comparing our ratings to KenPom

This is the target, not a claim. KenPom (kenpom.com, Ken Pomeroy)
is the reference for adjusted efficiency ratings. Our ratings
are built from free ESPN box scores only. We compare against
his published rankings to see if we are in the same ballpark,
not to reproduce his numbers.

## What we do NOT do

- No scraping of kenpom.com, no paywall bypass, no login, no
  automated fetching of his ratings pages. His full ratings
  are behind a subscription, and the subscription terms are
  the reason, not just a technical barrier.
- No copying of his exact prior formula, iterative weighting,
  or recent-game weighting. Those are proprietary and unknown
  to us. Our prior (prior.py) and solver (solver.py) are our
  own formulas, written down in those files, and any similarity
  is a similarity of approach (adjusted efficiencies, a prior,
  an iterative solve), not of implementation.
- No quoting of his full ranking table. Comparison uses rank
  positions and summary statistics computed from rankings we
  record by hand, with the date noted.

## What comparison data we can use

Only rankings that are publicly visible without a subscription,
recorded by hand with a date:

1. The top 25 list on KenPom's public front page, on the day
   we record it. That list is visible without paying.
2. A team's rank as cited in a public article, broadcast, or
   social post that quotes KenPom, with the source and date
   noted. Secondhand, so treat it as a spot check, not a table.
3. Our own backtest (below), which needs no KenPom data at all.

If we ever subscribe, the comparison can use the full table
from a paid account, read by a human, under the subscription
terms. That has not happened, and this rubric does not assume
it will.

## Comparison metrics

Mean absolute Net difference is NOT valid. Our Net and his Net
live on different scales: different priors, different game
sets (he excludes non-D1 and uses a full season, we use a
subset of games), different home court handling. A Net of +20
in ours and +25 in his can mean the same thing. So use
rank-based metrics only.

1. Spearman rank correlation (rho) on Net rank.
   - Top 25: rho on the 25 teams in his public top 25, using
     our rank for those same teams.
   - Top 100: rho on the top 100, once we have a full season
     and a way to read his top 100 legitimately (see above).
   - Report the sample size with the number. Rho on 25 teams
     is noisy; rho on 100 is the real test.
   - Implementation: rank both lists, rho = 1 - 6 * sum(d^2) /
     (n * (n^2 - 1)), where d is the rank difference per team.
     Stdlib only, no scipy.
2. Overlap at 10 and at 25: how many of his top 10 are in our
   top 10, and the same at 25. Simple, hard to game, easy to
   explain.
3. Mean absolute rank difference: average |our rank - his rank|
   over the compared set. Report it alongside rho, because rho
   hides a team that is off by 40 spots if the rest are close.
4. Illinois spot check: our rank and Net for Illinois, his rank
   for Illinois, on the same date. Illinois is the team we
   watch, so it gets its own line every time, not just a place
   in an average. Compare rank only, not Net, for the scale
   reason above.
5. Direction check on the biggest disagreements: for the 5
   teams where our rank and his rank differ most, write one
   line each on why. Common honest reasons: we have 1-2 games
   and he has a prior, we include a game he excludes (or the
   reverse), our opponent set is a subset of his.

## What counts as good

These are targets to report against, not pass/fail gates.
A target missed is information, not a failure to hide.

- Top 25 Spearman rho above 0.7: we are ranking the same
  good teams in roughly the same order.
- Top 100 Spearman rho above 0.8: the full-season solver is
  working.
- Overlap at 25 of at least 18 of 25.
- Mean absolute rank difference under 15 on the top 100.
- Illinois within 10 ranks of his Illinois rank.

Early season, expect all of these to miss. With 1-2 games per
team and a league-average prior, our top 25 will be mostly
teams that had big blowouts, and his will be mostly last
season's good teams carried by his prior. That gap is the
prior doing its job on his side and missing on ours, and it
should close as games accumulate. If it does not close by
mid-season on a full game log, the solver or the prior is
wrong, not the metric.

## Backtest (no KenPom data needed)

Fit on one season, predict the next, compare to actuals.
This is the honest test of whether the ratings predict
basketball, and it does not need his numbers at all.

1. Fit: run solver v2 on the complete 2024-25 season (full
   game log, D1 vs D1 only, with a prior built from 2023-24
   final ratings plus returning minutes).
2. Predict: for each 2025-26 game, predict the winner from
   the fitted AdjO/AdjD, adjusted for tempo and home court.
   The predicted margin is:
   (AdjO_home - AdjD_away) - (AdjO_away - AdjD_home), scaled
   by expected possessions / 100, plus the home court margin.
   Convert the margin to a win probability with a logistic
   curve fitted on the 2024-25 games, not a guessed constant.
3. Score, on the 2025-26 games only, never on the fitting games:
   - Accuracy: share of games where the predicted winner won.
   - Brier score: mean squared error of the predicted win
     probability against the actual outcome (0 or 1). Lower
     is better, 0.25 is guessing 50 percent every game.
   - Log loss: mean -log(p) for the actual outcome. Lower is
     better, punishes confident wrong picks.
   - Calibration: bucket predictions by probability (50-60,
     60-70, and so on) and check the actual win rate in each
     bucket is close to the bucket's average prediction.
4. Baselines to beat: picking the home team every game, and
   picking last season's better Net every game. If the solver
   cannot beat "home team wins", it is not predicting anything.
5. Overfitting guard: the backtest is out-of-sample by
   construction (fit on one season, test on the next). Do not
   tune the prior weight, damping, or regression constants on
   the test season and then report the test score as if it
   were untouched. Tune on 2024-25, lock the constants, then
   run 2025-26 once.

## What we can and cannot copy

Can use (public method, described by KenPom himself and by
Dean Oliver before him): possessions = FGA - ORB + TOV +
0.44 * FTA, efficiencies per 100 possessions, adjusting for
opponent strength, adjusting tempo for opponent tempo, and
the general idea of a preseason prior that fades.

Cannot copy, because it is proprietary and unknown: his exact
prior formula (how last season, returning minutes, recruiting,
and transfers combine), his iterative weighting (how much each
game counts, and whether recent games count more), his home
court value, and his exact non-D1 and game exclusion rules.
Our versions of all of those are our own choices, written
down in solver.py and prior.py. When our numbers differ from
his, the first suspects are those choices, in that order.

## How to record a comparison

One dated note per comparison, in the README or a dated file,
with: the date, the KenPom source (public top 25, cited rank,
or paid table if subscribed), the metric values above, the
Illinois line, and the 5 biggest disagreements with one line
each. No undated comparisons, because early-season rankings
move fast and an undated rho is meaningless.
