# Backtest: fit 2024-25, predict 2025-26

Fit on 5759 2024-25 games (league-average prior, no 2023-24 data exists for a real prior). Home court 4.69 pts/100 poss, estimated directly from fit-season residuals, and the logistic curve (a=-0.161, b=0.203) fitted on 2024-25 only. Scored on 5752 2025-26 games. Home teams won 63.7% of test games (64.3% in the fit season).

## Scores (lower Brier and log loss are better)

| Predictor | Accuracy | Brier | Log loss |
| --- | --- | --- | --- |
| solver | 0.660 | 0.2192 | 0.6392 |
| last_season_net | 0.653 | 0.2259 | 0.6589 |
| always_home | 0.637 | 0.2313 | 0.6552 |

## Diagnostic: rubric-literal margin formula

The rubric's printed margin formula, (AdjO_home - AdjD_away) - (AdjO_away - AdjD_home), scores accuracy 0.637, Brier 0.2308, log loss 0.6541, against the solver's 0.660 / 0.2192 / 0.6392. AdjD is points allowed, so the printed formula has the defensive term backwards relative to the solver model; the numbers above are the empirical check on that claim.

## Calibration (solver, test season)

| Predicted home win | Games | Mean predicted | Actual home win rate |
| --- | --- | --- | --- |
| 0-10% | 145 | 0.058 | 0.255 |
| 10-20% | 308 | 0.154 | 0.370 |
| 20-30% | 358 | 0.254 | 0.444 |
| 30-40% | 418 | 0.350 | 0.502 |
| 40-50% | 524 | 0.450 | 0.552 |
| 50-60% | 564 | 0.552 | 0.569 |
| 60-70% | 632 | 0.650 | 0.590 |
| 70-80% | 725 | 0.751 | 0.673 |
| 80-90% | 865 | 0.851 | 0.710 |
| 90-100% | 1213 | 0.957 | 0.873 |

Calibration note: the probabilities are overconfident at the extremes. Games the solver gave under 10% to the home team were actually won by the home team about a quarter of the time, and games it gave over 90% were won about 87% of the time. The cause is known: the logistic curve was fitted on fit-season margins, and the fit-season ratings explain their own games, so the slope comes out too steep for genuinely new games. The fix is cross-fitted calibration (fit ratings on one half of the fit season, fit the logistic on the other half). Not applied here; it is the next tweak to test against this scoreboard.

## Read

The solver beats always-home on accuracy and Brier, so it is predicting something real, not just riding home court. 
It also beats last season's raw Net on Brier (0.2192 vs 0.2259), so the opponent adjustment is adding signal beyond last year's raw scoring margins. 
This is the scoreboard every future tweak (home court, recency weighting, blowout caps, a real prior for the fit season) gets judged against: same fit, same test, same metrics.
