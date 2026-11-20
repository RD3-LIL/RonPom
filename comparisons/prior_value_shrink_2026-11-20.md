# Prior value shrink experiment, Nov 20, 2026

## Question

The adopted Nov 14 prior (build_prior_noshrink, base weight
600) fades the prior WEIGHT with the informed share
(returning + transfer minutes), 600 * (0.25 + 0.75 * info),
but not the prior VALUE: a team's value is its own
last-season rating regressed 0.85 toward league average,
whatever its info. Should the value also fade toward league
average when info is low, mirroring the weight factor? Two
variants were tested:

1. Value shrink: deviation multiplier 0.85 * (0.25 + 0.75 *
   info) for offense/defense, 0.70 * (0.25 + 0.75 * info) for
   tempo. At info 1.0 it is identical to the adopted prior.
2. Guard: teams with info below 0.25 get the league-average
   value with has_prior False (weight left as built).

## Verification first

build_prior_noshrink reproduces the live prior file
exactly (max |prior_o| difference 0.0 across all 576 teams):
Illinois prior Net +26.52, Duke +30.77, Houston +26.35,
Michigan +31.70, St. John's +21.34.

## Validation design (out of sample, not the live table)

Build 2025-26 priors from the 2024-25 final ratings (league
OffEff 107.0, tempo 67.9), all three variants. Rolling
origin on 2025-26: at cutoffs Nov 10, Nov 17, Nov 24, and
Dec 1, solve the games played so far with each prior and
predict the next 7 days of games. Same logistic for all
three (a=0.150, b=0.148, the 2024-25 crossfit), same home
court (predict_margin, 4.69, none on neutral floors), so the
only difference is the prior. Train sizes 338 / 637 / 967 /
1,256 games; test windows 299 / 330 / 289 / 297 games.

## Results (pooled, 1,215 next-7-days predictions)

| Variant | Accuracy | Brier | Log loss | Spread MAE |
| --- | --- | --- | --- | --- |
| Noshrink (adopted) | 0.757 | 0.1611 | 0.4826 | 9.80 |
| Value shrink | 0.753 | 0.1618 | 0.4846 | 9.88 |
| Guard info < 0.25 | 0.757 | 0.1611 | 0.4831 | 9.78 |

## Decision: NOT adopted, either variant

The value shrink is worse on all four metrics: accuracy
-0.004, Brier +0.0007, log loss +0.0020, spread MAE +0.08.
The guard is a no-op in validation (only 1 of 727 teams
fell below info 0.25 in the 2025-26 build, so its pooled
numbers are identical to noshrink to three decimals except
log loss +0.0005 and spread MAE -0.02), and it adds a
threshold rule with no demonstrated benefit. Neither is
adopted. The Nov 14 decision stands: value is the own-team
rating, weight carries the info fade.

The value-shrink option is implemented in
build_prior_noshrink as value_shrink=False (default off),
with tests in test_prior_2026.py, so the experiment is
reproducible and can be re-run when the season finishes.
The guard lives only in prior_shrink_experiment.py, not in
the builder.

## Live effect of the value shrink (for the record, not adopted)

Prior Net, noshrink vs value shrink, on the Nov 20 snapshot:

| Team | Info | Prior Net noshrink | Prior Net shrunk |
| --- | --- | --- | --- |
| Illinois | 0.489 | +26.5 | +16.4 |
| Duke | 0.613 | +30.8 | +21.8 |
| Houston | 0.911 | +26.3 | +24.6 |
| Michigan | 0.795 | +31.7 | +26.8 |
| St. John's | 0.694 | +21.3 | +16.4 |

Solved top 10 under the shrink (live table is the noshrink
one): 1 Houston 32.2, 2 Illinois 31.8, 3 Duke 28.2,
4 Michigan 27.8, 5 Florida 27.8, 6 Vanderbilt 26.8,
7 St. John's 26.7, 8 Nebraska 26.3, 9 UConn 25.8,
10 Texas Tech 25.6. The shrink would have flipped #1 to
Houston. That is a big change to make on a variant that
loses out of sample, so it stays out.

## Info measurement: minutes played to date, not roster membership

Info is the returning + transfer share of this season's
minutes played to date, split by whether the player has a
last-season profile. Minutes to date is the honest measure
of who is actually on the floor now; full roster membership
would count deep-bench players who never play and overstate
how much of last season's team is really back. The known
undercount still applies: DNP players are excluded from the
profiles, so shares read low, never high. In the live prior,
info ranges 0.114 to 0.997 (mean 0.693); 6 teams sit below
0.25 (Eastern Illinois 0.170, Mississippi Valley State
0.114, Idaho State 0.130, Louisiana Tech 0.217, East Texas
A&M 0.228, UT Martin 0.237).
