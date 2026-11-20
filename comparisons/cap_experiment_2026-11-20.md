# Margin cap experiment, Nov 20, 2026

## Preregistration

Fit 2024-25, test 2025-26. Solver with margin_cap None, 20,
and 15, plus a per-possession cap of 0.30 points per
possession (tested separately, same protocol). Prior weight
300 possessions, league-average prior, solver home court 0.0.
Win/loss scored with the cross-fitted logistic (fit season
only); spread MAE on test games with a market spread.

Adoption rule, set before running: adopt cap-20 live in
write_ratings.py only if it beats no-cap on at least two of
the three metrics (spread MAE, Brier, log loss).

KenPom rank gap: not measurable. There is no KenPom data
available without the paywall, and no KenPom data was
scraped. The Nov 14 prior comparison used a KenPom list Ron
provided; no such list exists for this experiment.

## Method

Runs used the fixed backtest.py (Nov 20): margin_model
applies zero home court on neutral floors, and the home
court estimate excludes neutral-site and OT games (see
comparisons/home_court_2026-11-20.md). The cap runs were
first done on the pre-fix code and then re-run on the fixed
code; the numbers below are the fixed-code runs. Sample
sizes: 5,759 fit games (364 teams), 5,752 test games for
win/loss, 4,766 test games with a market spread.

Commands (from the repo root; outputs in /tmp, not committed
over the existing comparison files):

    python3 backtest.py --out /tmp/.../backtest_cap_none.md
    python3 backtest.py --out /tmp/.../backtest_cap_20.md --blowout-cap 20
    python3 backtest.py --out /tmp/.../backtest_cap_15.md --blowout-cap 15
    python3 backtest.py --out /tmp/.../backtest_pp030.md --margin-cap-per-poss 0.30
    python3 cap_experiment.py   (spread MAE for the per-poss cap, live effect)

## Results

| Cap | Accuracy | Brier | Log loss | Spread MAE |
| --- | --- | --- | --- | --- |
| None | 0.670 | 0.2102 | 0.6074 | 10.38 |
| 20 | 0.671 | 0.2117 | 0.6112 | 10.34 |
| 15 | 0.670 | 0.2118 | 0.6114 | 10.35 |
| Per-poss 0.30 | 0.669 | 0.2117 | 0.6113 | 10.34 |

Market spread MAE for reference: 8.86 on the same 4,766 games.

## Decision: NOT adopted

Cap-20 beats no-cap on only one of the three metrics
(spread MAE, 10.34 vs 10.38, a 0.04-point difference) and
loses on Brier (0.2117 vs 0.2102) and log loss (0.6112 vs
0.6074). Cap-15 and the per-possession cap fail the same
way: each wins only spread MAE by 0.03-0.04 points and loses
both probability metrics. The pattern is monotonic: the
tighter the cap, the worse Brier and log loss get, while
accuracy stays flat (0.669-0.671). Capping throws away real
signal about the size of a win; the blowouts are
informative, not noise, at this prior weight. No change was
made to write_ratings.py: live ratings still run with
margin_cap None.

Note: the cap does move the live table a lot (below), which
is exactly why the decision had to come from the backtest
and not from liking the look of the capped table.

## Live effect (snapshot Nov 20, 2026, 1,070 games, 801 D1 used)

Reported separately from the backtest decision, as required.
No-cap is live; the capped columns are what the table would
have looked like.

| Team | No cap (live) | Cap 20 | Cap 15 | Per-poss 0.30 |
| --- | --- | --- | --- | --- |
| Illinois | 37.6 (#1) | 26.2 | 23.5 | 27.7 |
| Duke | 33.7 (#2) | 23.2 | 21.7 | 24.0 |
| Houston | 33.5 (#3) | 28.3 | 26.6 | 28.5 |
| Michigan | 31.3 (#4) | 27.8 | 27.0 | 28.6 |
| St. John's | 29.4 (#5) | 22.8 | 20.8 | 23.5 |

Under cap-20, Houston would be #1 (28.3) ahead of Michigan
(27.8) and Illinois (26.2). That is a large change driven by
Illinois's 75- and 42-point early wins counting at full
value, and it is not hand-tuned away: the backtest says the
uncapped numbers predict better, so Illinois stays #1.

## OT normalization and neutral site (task 4)

Conditioned on the cap experiment supporting it. It did
not, so OT normalization was left out and is recorded here
rather than built:

- OT games (325 of 5,759 fit games) keep their full
  boxscore possessions. Their extra possessions are real
  possessions played, and there is no evidence from this
  experiment that rescaling them to regulation possessions
  would improve prediction. A tempo-normalization change
  would need its own out-of-sample win, not a ride on the
  cap experiment.
- Neutral-site games are treated as neutral inside the
  solver when home court is enabled (s = 0 on neutral
  floors, solver.py, Nov 20). That change is inert live
  because home court inside the solver stays 0.0 (see the
  home court note), and it was validated as part of the
  solver home court backtest, not adopted as a ratings
  change on its own.
