# Player profiles rebuilt after the stale-cache fix, 2026-11-20

## Fetch fix verification (per event id)

`fetch_full.py` now treats a cached summary as unusable unless
both teams have non-empty statistics arrays and non-empty
athlete lists, deletes it, and re-fetches. The five bad
summaries were deleted and re-fetched on Nov 20. All five
came back full:

| Event id | Date | Game | Team stats | Athletes | stats_missing |
| --- | --- | --- | --- | --- | --- |
| 401918987 | Nov 10 | Memphis at Vanderbilt, 81-105 | 25 and 25 | 15 and 15 | False (was True) |
| 401920378 | Nov 10 | Virginia Tech at Iowa, 93-88 | 25 and 25 | 15 and 14 | False (was True) |
| 401917950 | Nov 10 | Livingstone at Austin Peay, 61-82 | 25 and 25 | 26 and 12 | False (was True) |
| 401924949 | Nov 10 | Penn State Lehigh Valley at Lafayette, 46-89 | 25 and 25 | 19 and 16 | False (was True) |
| 401921153 | Nov 3 | Warren Wilson at NC A&T, 53-92 | 24 and 24 | 20 and 15 | False (was True) |

ESPN still returns empty stats for the four postponed 0-0
games (Nov 14: Pacific vs Air Force, Cornell vs UNC
Greensboro, UNC Wilmington vs Louisiana; Nov 15: Oregon vs
Pepperdine). Those were not re-fetched in this window, they
keep the `stats_missing` flag, and they stay out of the
solver and out of Luck. They were never played, so there is
nothing to recover.

## stats_missing backfill

The 345 games with no `stats_missing` key at all (Nov 2:
182, Nov 4: 26, Nov 5: 65, Nov 6: 72) were re-parsed by
re-running the fetch for Nov 2-10 with the fixed code. None
of those 345 games has empty team stats, so all 345 were
backfilled to `stats_missing: false`. Games with no key: 0
after the run. Total `stats_missing: true` in
`games_2026_27.json` is now 4, all postponed 0-0 games.
Solver games went 801 to 803 (the two recovered D1 games
now count); skipped zero-possession games went 6 to 4.

## Player rebuild

`player_profiles.py --season 2026-27` after the fix:
8,015 players (was 7,962), 1,070 games included, 24,623
player rows counted (was 24,485), 0 unmapped events.

- Amani Hansberry (Virginia Tech): gp 4 to 5, matching
  Virginia Tech's 5 games. Minutes 118 to 158, points 74
  to 90. RPR 10.11 to 7.76.
- Jayden Reid (Memphis): gp 3 to 4, matching Memphis's 4
  games. Minutes 95 to 125, points 82 to 93. RPR 11.52
  to 8.32.

Both now match their teams' game counts. The recovered
games were bad games for both players, so their RPR fell
even as their GP became correct.

## Top 150 RPR: did it change?

Yes. Top 10 before and after (RPR, min 1 game, 40% of team
minutes floor):

Before (Nov 20, pre-fix):
1. Dior Johnson (UCF) 13.45
2. Xavier Harris (Cameron) 12.25
3. Jayden Reid (Memphis) 11.52
4. Daniel Zatsepin (Lindsey Wilson) 11.25
5. Pryce Sandfort (Nebraska) 11.17
6. Clyde Harris Jr. (Corban) 10.67
7. Patrick Wessler (UNC Wilmington) 10.46
8. James Ellis (Colorado Colorado Springs) 10.12
9. Amani Hansberry (Virginia Tech) 10.11
10. Amari Allen (Alabama) 10.11

After (Nov 20, post-fix):
1. Dior Johnson (UCF) 13.45
2. Xavier Harris (Cameron) 12.25
3. Daniel Zatsepin (Lindsey Wilson) 11.25
4. Pryce Sandfort (Nebraska) 11.17
5. Clyde Harris Jr. (Corban) 10.67
6. Patrick Wessler (UNC Wilmington) 10.46
7. James Ellis (Colorado Colorado Springs) 10.12
8. Amari Allen (Alabama) 10.11
9. Owen Evans (Friends) 10.00
10. Sean Caldwell (Miami OH Hamilton) 9.87

Reid falls to #52 (8.32) and Hansberry to #80 (7.76).
Only three players in the Top 150 changed RPR at all:
Reid 11.52 to 8.32, Hansberry 10.11 to 7.76, and Tyler
Tanner (Vanderbilt) 9.38 to 9.15 (#24 to #27). Everything
else in the Top 150 moved only by knock-on rank shifts
(mostly up one) as Reid and Hansberry fell. Three players
left the Top 150: Rihards Vavers (Memphis, 7.93 to 6.47),
Ace Glass (Vanderbilt, 6.65 to 6.15), and Chandler Bing
(Vanderbilt, 6.65 to 5.42). Three entered: Ben Hammond
(Virginia Tech, #67, 7.97), Ivan Kharchenkov (Arizona,
#149, 6.64), and Rashawn Inglemon (Campbell, #150, 6.64).

Note the Top 150 itself is not stable yet at this point in
the season; see comparisons/split_half_2026-11-20.md, where
the split-half correlation for RPR is only about 0.20.
