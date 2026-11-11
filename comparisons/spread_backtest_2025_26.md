# Spread backtest: fit 2024-25, predict 2025-26

Fit on 5759 2024-25 games (league-average prior), 364 teams, league OffEff 107.0, tempo 67.9. Scored on 4766 2025-26 games with a market spread. Home court 4.69 pts/100 poss, none on a neutral floor, same as predict.py.

## Headline (points; lower MAE is better)

| | MAE vs actual | Bias vs actual |
| --- | --- | --- |
| Model | 10.38 | -0.00 |
| Market | 8.86 | +0.19 |

Model vs market MAE: 5.34 points. That is how far the model sits from the market on average, the number to watch as the calculator is refined.

## Edge cover (does disagreeing with the market pay?)

| Min disagreement | Games | Model cover rate |
| --- | --- | --- |
| 2 pts | 3651 | 50.5% |
| 3 pts | 3106 | 50.4% |
| 5 pts | 2096 | 49.3% |

Breakeven at -110 is 52.4%. Above it, the model's disagreements are real money; at or below 50%, they are noise and the model should stay closer to the market.

## By market-spread size

| Market line | Games | Model MAE | Market MAE | Model bias | Market bias |
| --- | --- | --- | --- | --- | --- |
| away by 14+ | 55 | 11.38 | 7.66 | +7.33 | -0.66 |
| away by 7-14 | 342 | 10.72 | 8.75 | +5.38 | -0.20 |
| away by 0-7 | 1110 | 10.26 | 8.88 | +2.71 | -0.32 |
| home by 0-7 | 1669 | 10.17 | 8.82 | +0.09 | +0.55 |
| home by 7-14 | 1035 | 10.04 | 8.68 | -2.15 | +0.49 |
| home by 14-21 | 346 | 10.94 | 9.21 | -4.69 | -0.34 |
| home by 21+ | 209 | 12.54 | 9.98 | -7.46 | +0.20 |

## Neutral-site split

| | Games | Model MAE | Market MAE | Model bias |
| --- | --- | --- | --- | --- |
| Home/away | 4207 | 10.35 | 8.84 | +0.11 |
| Neutral site | 559 | 10.60 | 9.02 | -0.85 |

## Calibrated margins

Scales fitted on the fit season only (cross-fitted, no test-season data). A slope above 1 stretches the compressed raw margins.

| Variant | Scale | MAE vs actual | Bias vs actual | Model vs market MAE |
| --- | --- | --- | --- | --- |
| Raw | - | 10.38 | -0.00 | 5.34 |
| Linear | +1.83 + 1.063 * pred | 10.61 | +2.08 | 5.68 |
| Slope only | +0.00 + 1.172 * pred | 10.66 | +0.71 | 5.79 |

Edge cover, linear:

| Min disagreement | Games | Model cover rate |
| --- | --- | --- |
| 2 pts | 3695 | 49.6% |
| 3 pts | 3181 | 49.6% |
| 5 pts | 2272 | 50.3% |

Bias by market-spread size, linear:

| Market line | Games | Model bias |
| --- | --- | --- |
| away by 14+ | 55 | +8.56 |
| away by 7-14 | 342 | +6.97 |
| away by 0-7 | 1110 | +4.52 |
| home by 0-7 | 1669 | +2.12 |
| home by 7-14 | 1035 | +0.14 |
| home by 14-21 | 346 | -2.08 |
| home by 21+ | 209 | -4.34 |

Edge cover, slope only:

| Min disagreement | Games | Model cover rate |
| --- | --- | --- |
| 2 pts | 3709 | 50.3% |
| 3 pts | 3222 | 50.3% |
| 5 pts | 2300 | 48.8% |

Bias by market-spread size, slope only:

| Market line | Games | Model bias |
| --- | --- | --- |
| away by 14+ | 55 | +5.72 |
| away by 7-14 | 342 | +4.73 |
| away by 0-7 | 1110 | +2.68 |
| home by 0-7 | 1669 | +0.66 |
| home by 7-14 | 1035 | -0.90 |
| home by 14-21 | 346 | -2.54 |
| home by 21+ | 209 | -3.91 |

## Read

The market beats the model on spread error (8.86 vs 10.38 points), as expected: the market prices injuries, rest, and motivation the ratings cannot see. The gap is the room the refinement has to close.

Neither scale improves the test season: both raise MAE and move the model further from the market, so neither was adopted. The compression pattern in the bucket biases is real, but a global stretch amplifies noise in the middle, where most games are, more than it helps at the extremes. The fix has to come from the ratings themselves, not a post-hoc scale, e.g. a lower prior weight so the ratings spread out more.

