# Home court re-estimate and solver home court test, Nov 20, 2026

## Re-estimate: excluding neutral-site and OT games

Direct residual estimate on the 2024-25 fit (5,759 played D1
games), hc=0 ratings, prior weight 300:

| Subset | Games | Implied home court (pts/100 poss) |
| --- | --- | --- |
| All games (old method) | 5,759 | 4.69 |
| Non-neutral | 5,020 | 5.16 |
| Non-OT | 5,434 | 4.86 |
| Non-neutral, non-OT (adopted estimate) | 4,746 | 5.33 |
| Neutral only | 739 | 1.45 |
| OT only | 325 | 1.71 |

Why the exclusions are correct: the designated "home" team
on a neutral floor still won 60.9% of neutral games in
2024-25, which is team quality (the better seed is usually
designated home), not a floor effect, so neutral residuals
drag the estimate down toward 1.45. OT games carry extra
possessions and a different margin distribution (1.71). The
clean estimate is 5.33, not 4.69.

## Code fixes (backtest.py, solver.py)

1. `estimate_home_court` now skips neutral-site and OT games.
   The prediction step therefore uses 5.33 instead of 4.69.
   Side effect, measured: the no-cap baseline backtest moved
   slightly, from 0.669 / 0.2105 / 0.6081 (old estimate) to
   0.670 / 0.2102 / 0.6074 (new estimate), on the same 5,752
   test games. Small, in the right direction, and it comes
   from the cleaner estimate, not from tuning on the test
   season: the estimate uses fit-season data only.
2. `margin_model` (and the rubric-literal and raw-Net
   diagnostic margins, for a consistent comparison) now apply
   zero home court on neutral floors, as predict.py already
   does. Previously a neutral-site test game got the full
   home court added to its predicted margin.
3. `solver.py` now sets the home-court sign to 0 on neutral
   floors when home court is enabled inside the solve. Inert
   live (home court stays 0.0), and it only matters for
   home-court-enabled experiments.

One thing NOT changed: `predict.py` still hardcodes
HOME_COURT = 4.69. That file belongs to another track. The
re-estimated 5.33 is recorded here for the prediction track;
whether to update the hardcoded constant is that track's
call, and it should be validated on the live prediction
scorecard, not assumed from this backtest.

## Solver home court: re-run, cross-fitted

Win/loss backtest, fit 2024-25, test 2025-26, 5,752 games,
cross-fitted logistic, fixed code throughout:

| Solver home court | Accuracy | Brier | Log loss |
| --- | --- | --- | --- |
| 0.0 (baseline, published) | 0.670 | 0.2102 | 0.6074 |
| 5.33 (re-estimated) | 0.667 | 0.2124 | 0.6132 |

## Decision: NOT adopted

Home court inside the solver loses on all three metrics at
the re-estimated value, the same verdict as the Nov 10 test
at 2.0, 3.0, and 4.69 with the in-sample logistic. The
ratings keep home court off (0.0); home court lives only in
the prediction step.

## Stated consequence: published ratings are home-schedule-biased early in the season

This is documented explicitly here and in a code comment at
DEFAULT_HOME_COURT in solver.py, not left implicit. Early in
the season most teams play the bulk of their games at home,
and with no home-court term in the solve, part of the home
floor advantage is credited to the teams themselves as
offense and defense. The bias fades as road and neutral
games accumulate, but on a 4-5 game sample it is real and
it is in the published numbers. Any early-season read of
the table should carry that caveat.
