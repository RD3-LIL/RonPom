# Split-half reliability of player RPR and ORtg, 2026-11-20

## Verdict, plainly

Weak. Do not claim the Top 150 is stable. The split-half
correlation for RPR is about 0.20 to 0.28 depending on the
cut, and about 0.10 to 0.16 for ORtg. A leaderboard built
on 3 to 6 games per player will move a lot as more games
arrive.

## Method

Per player, per game, from the raw ESPN summaries on disk
for 2026-27 (1,070 mapped games, after the Nov 20
stale-cache fix). Each player's games were ordered by date
and split into a first half and a second half (for an odd
game count the second half gets the extra game). RPR and
ORtg were computed on each half with the same formulas as
`player_profiles.py` (simplified ORtg, RPR from
`compute_rpr`). Pearson r (and Spearman rho where noted)
between the two halves, across players. A player needs at
least 2 games to have a half at all; higher minimums are
shown as separate cuts. Halves here are 1 to 3 games each,
because teams have only played 3 to 6 games so far.

## Results

All players, by minimum games:

| Min GP | n players | RPR r | ORtg r |
| --- | --- | --- | --- |
| 2 | 4,554 | 0.275 | 0.143 |
| 3 | 4,086 | 0.240 | 0.116 |
| 4 | 3,655 | 0.236 | 0.100 |

Regulars and rotation players, gp >= 4:

| Cut | n players | RPR Pearson r | RPR Spearman rho | ORtg Pearson r |
| --- | --- | --- | --- | --- |
| >= 20 min/game | 1,795 | 0.201 | 0.198 | 0.160 |
| >= 15 min/game | 2,481 | 0.202 | 0.196 | 0.121 |
| gp >= 5, >= 20 min/game | 1,411 | 0.217 | 0.215 | 0.175 |

Pearson and Spearman agree, so the weak result is not an
outlier artifact. RPR half means for the gp >= 4 cut were
1.77 (first half) and 1.63 (second half).

## What this does and does not mean

It does not prove RPR is a bad rating. With halves of 2
games, single-game variance dominates: one hot or cold
night swings a half by several RPR points, and that alone
caps the correlation. What it does prove is that a Top 150
ranked on 3 to 6 games is not a stable statement about who
the best players are. The honest read is to re-run this
check when halves are 8 to 10 games each (mid-December at
the current pace) and see whether the correlation rises
toward 0.5 or better. Until then, treat the Top 150 as a
snapshot of a small sample, not a settled ranking.
