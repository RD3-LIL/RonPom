# Spread backtest: fit 2024-25, predict 2025-26

Fit on 5759 2024-25 games (league-average prior, prior weight 150 possessions), 364 teams, league OffEff 107.0, tempo 67.9. Scored on 4766 2025-26 games with a market spread. Home court 4.69 pts/100 poss, none on a neutral floor, same as predict.py.

## Headline (points; lower MAE is better)

| | MAE vs actual | Bias vs actual |
| --- | --- | --- |
| Model | 10.45 | +0.19 |
| Market | 8.86 | +0.19 |

Model vs market MAE: 5.46 points. That is how far the model sits from the market on average, the number to watch as the calculator is refined.

## Edge cover (does disagreeing with the market pay?)

| Min disagreement | Games | Model cover rate |
| --- | --- | --- |
| 2 pts | 3650 | 50.4% |
| 3 pts | 3130 | 50.5% |
| 5 pts | 2181 | 49.4% |

Breakeven at -110 is 52.4%. Above it, the model's disagreements are real money; at or below 50%, they are noise and the model should stay closer to the market.

## By market-spread size

| Market line | Games | Model MAE | Market MAE | Model bias | Market bias |
| --- | --- | --- | --- | --- | --- |
| away by 14+ | 55 | 11.07 | 7.66 | +6.31 | -0.66 |
| away by 7-14 | 342 | 10.75 | 8.75 | +4.88 | -0.20 |
| away by 0-7 | 1110 | 10.39 | 8.88 | +2.50 | -0.32 |
| home by 0-7 | 1669 | 10.32 | 8.82 | +0.15 | +0.55 |
| home by 7-14 | 1035 | 10.16 | 8.68 | -1.75 | +0.49 |
| home by 14-21 | 346 | 10.94 | 9.21 | -3.64 | -0.34 |
| home by 21+ | 209 | 11.76 | 9.98 | -5.04 | +0.20 |

## Neutral-site split

| | Games | Model MAE | Market MAE | Model bias |
| --- | --- | --- | --- | --- |
| Home/away | 4207 | 10.41 | 8.84 | +0.29 |
| Neutral site | 559 | 10.72 | 9.02 | -0.58 |

## Calibrated margins

Scales fitted on the fit season only (cross-fitted, no test-season data). A slope above 1 stretches the compressed raw margins.

| Variant | Scale | MAE vs actual | Bias vs actual | Model vs market MAE |
| --- | --- | --- | --- | --- |
| Raw | - | 10.45 | +0.19 | 5.46 |
| Linear | +1.95 + 0.967 * pred | 10.53 | +2.00 | 5.57 |
| Slope only | +0.00 + 1.065 * pred | 10.58 | +0.47 | 5.66 |

Edge cover, linear:

| Min disagreement | Games | Model cover rate |
| --- | --- | --- |
| 2 pts | 3686 | 49.9% |
| 3 pts | 3159 | 49.9% |
| 5 pts | 2215 | 50.6% |

Bias by market-spread size, linear:

| Market line | Games | Model bias |
| --- | --- | --- |
| away by 14+ | 55 | +8.61 |
| away by 7-14 | 342 | +6.98 |
| away by 0-7 | 1110 | +4.46 |
| home by 0-7 | 1669 | +1.99 |
| home by 7-14 | 1035 | -0.05 |
| home by 14-21 | 346 | -2.13 |
| home by 21+ | 209 | -3.84 |

Edge cover, slope only:

| Min disagreement | Games | Model cover rate |
| --- | --- | --- |
| 2 pts | 3703 | 50.4% |
| 3 pts | 3188 | 50.3% |
| 5 pts | 2255 | 48.8% |

Bias by market-spread size, slope only:

| Market line | Games | Model bias |
| --- | --- | --- |
| away by 14+ | 55 | +5.63 |
| away by 7-14 | 342 | +4.60 |
| away by 0-7 | 1110 | +2.47 |
| home by 0-7 | 1669 | +0.37 |
| home by 7-14 | 1035 | -1.25 |
| home by 14-21 | 346 | -2.76 |
| home by 21+ | 209 | -3.54 |

## Read

The market beats the model on spread error (8.86 vs 10.45 points), as expected: the market prices injuries, rest, and motivation the ratings cannot see. The gap is the room the refinement has to close.

Neither scale improves the test season: both raise MAE and move the model further from the market, so neither was adopted. The compression pattern in the bucket biases is real, but a global stretch amplifies noise in the middle, where most games are, more than it helps at the extremes. The fix has to come from the ratings themselves, not a post-hoc scale, e.g. a lower prior weight so the ratings spread out more.

