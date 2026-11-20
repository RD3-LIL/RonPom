# Live predictions scorecard

Scored 287 live predictions so far. Each row is one forecast from a dated predictions file, matched to its final score after the game. Predictions are never overwritten, so this log only grows.

## Headline (live, vs the 2025-26 backtest baseline)

| Metric | Live | Backtest baseline |
| --- | --- | --- |
| Accuracy | 71.4% (n=287) | 66.9% |
| Brier | 0.1666 | 0.2105 |
| Log loss | 0.4879 | 0.6081 |
| Spread MAE, model | 10.23 | - |
| Spread MAE, market | 9.64 (n=99) | - |

## Edge cover (does disagreeing with the market pay?)

| Min disagreement | Games | Model cover rate |
| --- | --- | --- |
| 2 pts | 72 | 59.7% |
| 3 pts | 65 | 61.5% |
| 5 pts | 47 | 63.8% |

Breakeven at -110 is 52.4%.

## Trap games

1 trap games scored. Underdog cover 100.0%, underdog win 0.0%.

## Read

Live accuracy is in line with the backtest so far. Keep collecting, the value is in the trend over hundreds of games, not in any one night.

