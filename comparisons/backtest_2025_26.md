# Backtest: fit 2024-25, predict 2025-26

Fit on 5759 2024-25 games (league-average prior, no 2023-24 data exists for a real prior). Solver home court 0.00 pts/100 poss inside the fit. Prediction home court 4.69 pts/100 poss, estimated directly from fit-season residuals, and the logistic curve (a=0.150, b=0.148, calibration crossfit) fitted on 2024-25 only. Scored on 5752 2025-26 games. Home teams won 63.7% of test games (64.3% in the fit season).

## Scores (lower Brier and log loss are better)

| Predictor | Accuracy | Brier | Log loss |
| --- | --- | --- | --- |
| solver | 0.669 | 0.2105 | 0.6081 |
| last_season_net | 0.661 | 0.2142 | 0.6178 |
| always_home | 0.637 | 0.2313 | 0.6552 |

## Diagnostic: rubric-literal margin formula

The rubric's printed margin formula, (AdjO_home - AdjD_away) - (AdjO_away - AdjD_home), scores accuracy 0.637, Brier 0.2308, log loss 0.6542, against the solver's 0.669 / 0.2105 / 0.6081. AdjD is points allowed, so the printed formula has the defensive term backwards relative to the solver model; the numbers above are the empirical check on that claim.

## Calibration (solver, test season)

| Predicted home win | Games | Mean predicted | Actual home win rate |
| --- | --- | --- | --- |
| 0-10% | 26 | 0.067 | 0.115 |
| 10-20% | 111 | 0.155 | 0.279 |
| 20-30% | 242 | 0.257 | 0.376 |
| 30-40% | 370 | 0.354 | 0.427 |
| 40-50% | 532 | 0.452 | 0.498 |
| 50-60% | 730 | 0.552 | 0.559 |
| 60-70% | 852 | 0.651 | 0.577 |
| 70-80% | 1001 | 0.751 | 0.667 |
| 80-90% | 985 | 0.849 | 0.738 |
| 90-100% | 903 | 0.947 | 0.909 |

Calibration note: the logistic curve is cross-fitted (ratings on one half of the fit season, logistic on the other half, pooled), so the probabilities are much better behaved than the old in-sample fit: games given under 10% were actually won by the home team 11.5% of the time (was 25.5% with the in-sample fit), and games given over 90% were won 90.9% of the time (was 87.3%). The top buckets are still a little overconfident, but the extremes no longer lie by a factor of two.

## Read

The solver beats always-home on accuracy and Brier, so it is predicting something real, not just riding home court. 
It also beats last season's raw Net on Brier (0.2105 vs 0.2142), so the opponent adjustment is adding signal beyond last year's raw scoring margins. 
This is the scoreboard every future tweak (recency weighting, blowout caps, a real prior for the fit season) gets judged against: same fit, same test, same metrics. Home court inside the solver was already tested and rejected: it made Brier and log loss worse at every value tried.

## Experiment (Nov 10, 2026): home court inside the solver

The prediction step already adds home court (4.69 pts/100 poss, estimated from 2024-25 residuals). This experiment also removed home court inside the solver fit, so the ratings themselves became neutral-site ratings. Run with `backtest.py --solver-home-court 4.69` (full report in comparisons/backtest_2025_26_hc469.md). Measured with the in-sample logistic, against the in-sample baseline of 0.660 / 0.2192 / 0.6392:

| Solver home court | Accuracy | Brier | Log loss |
| --- | --- | --- | --- |
| 0.0 (baseline) | 0.660 | 0.2192 | 0.6392 |
| 2.0 | 0.661 | 0.2207 | 0.6442 |
| 3.0 | 0.660 | 0.2215 | 0.6469 |
| 4.69 | 0.659 | 0.2230 | 0.6517 |

Worse on Brier and log loss at every value, monotonically worse as the value rises, while accuracy stays flat. The picks do not change; the probabilities get worse. NOT adopted: the solver keeps home court off (0.0) and home court lives only in the prediction step. The 2.0 and 3.0 runs are diagnostics, not tuning: no value from the test season was adopted.
