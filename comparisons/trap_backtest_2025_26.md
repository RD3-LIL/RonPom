# Trap backtest: fit 2024-25, test 2025-26

Fit on 5759 2024-25 games (league-average prior, prior weight 300), 364 teams. Scored on 3851 2025-26 games with a market spread and a clear favorite (|model margin| >= 2). Trap thresholds were locked in trap.py before this run: MARKET_GAP required, total flags >= 3. History uses only games played before each game's date.

## Headline

| Group | Games | Underdog covers market | Underdog wins outright |
| --- | --- | --- | --- |
| All games | 3851 | 52.2% | 33.2% |
| Trap | 76 | 47.4% | 1.3% |
| Gap only | 560 | 54.3% | 12.5% |
| Gap all | 636 | 53.5% | 11.2% |

Breakeven for a cover bet at -110 is 52.4%. Underdog cover is the actual favorite margin falling short of the market favorite margin.

## Read

Trap games cover at 47.4% (76 games), against 52.2% for all games and a 52.4% breakeven. That is no signal: the flags describe letdown context, they do not beat the market. The trap section stays on the page as a watch list, what is weird, not a pick, and the spread magnitudes stay unbacktested.

Selection note: trap games are mostly blowout favorites, not close games. Median market favorite margin is 16.5 points for trap games vs 6.5 for all games, mean 20.1, and 49 of 76 trap games had the favorite by 14 or more. That is why the underdog outright win rate is only 1.3% for trap games: the underdog is usually a big underdog. Do not read that 1.3% as favorites being safe in trap games, it is the mismatch talking. The cover rate is the fair comparison, and it is below breakeven.

## Flag counts (test season)

- TOP25: 555 games
- BIG_WIN: 459 games
- BUSY: 69 games
- SHORT_REST: 45 games
- ROAD_FAV: 877 games
- MARKET_GAP: 636 games

## Trap games in the test season

| Date | Favorite | Underdog | Flags | Dog covered? | Dog won? |
| --- | --- | --- | --- | --- | --- |
| 20251128 | Missouri Tigers | Cleveland State Vikings | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251202 | Purdue Boilermakers | Rutgers Scarlet Knights | TOP25, BIG_WIN, ROAD_FAV, MARKET_GAP | no | no |
| 20251203 | Vanderbilt Commodores | SMU Mustangs | BIG_WIN, BUSY, MARKET_GAP | no | no |
| 20251203 | Iowa State Cyclones | Alcorn State Braves | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251206 | Michigan Wolverines | Rutgers Scarlet Knights | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251207 | Gonzaga Bulldogs | North Florida Ospreys | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251209 | Michigan Wolverines | Villanova Wildcats | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251213 | Gonzaga Bulldogs | UCLA Bruins | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251213 | Purdue Boilermakers | Marquette Golden Eagles | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251213 | Michigan State Spartans | Penn State Nittany Lions | TOP25, ROAD_FAV, MARKET_GAP | yes | no |
| 20251216 | Arizona Wildcats | Abilene Christian Wildcats | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251217 | Gonzaga Bulldogs | Campbell Fighting Camels | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251219 | BYU Cougars | Abilene Christian Wildcats | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251220 | Arizona Wildcats | San Diego State Aztecs | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251221 | Iowa State Cyclones | Long Beach State Beach | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251221 | Michigan Wolverines | La Salle Explorers | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251221 | Gonzaga Bulldogs | Oregon Ducks | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251221 | Tennessee Volunteers | Gardner-Webb Runnin' Bulldogs | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251222 | Arizona Wildcats | Bethune-Cookman Wildcats | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251223 | UCLA Bruins | UC Riverside Highlanders | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251228 | Gonzaga Bulldogs | Pepperdine Waves | TOP25, ROAD_FAV, MARKET_GAP | no | no |
| 20251229 | Iowa State Cyclones | Houston Christian Huskies | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251229 | Purdue Boilermakers | Kent State Golden Flashes | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251229 | Michigan Wolverines | McNeese Cowboys | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251229 | Arizona Wildcats | South Dakota State Jackrabbits | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251229 | Illinois Fighting Illini | Southern Jaguars | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251229 | Florida Gators | Dartmouth Big Green | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20251230 | Gonzaga Bulldogs | San Diego Toreros | TOP25, BIG_WIN, ROAD_FAV, MARKET_GAP | yes | no |
| 20251230 | Saint Mary's Gaels | Pepperdine Waves | TOP25, ROAD_FAV, MARKET_GAP | no | no |
| 20251230 | Tennessee Volunteers | South Carolina State Bulldogs | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20251231 | High Point Panthers | UNC Asheville Bulldogs | BIG_WIN, ROAD_FAV, MARKET_GAP | no | no |
| 20260102 | Michigan Wolverines | USC Trojans | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20260102 | Ohio State Buckeyes | Rutgers Scarlet Knights | BIG_WIN, ROAD_FAV, MARKET_GAP | yes | no |
| 20260102 | Iowa State Cyclones | West Virginia Mountaineers | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20260103 | Illinois Fighting Illini | Penn State Nittany Lions | TOP25, BIG_WIN, ROAD_FAV, MARKET_GAP | yes | no |
| 20260103 | Arizona Wildcats | Utah Utes | TOP25, BIG_WIN, ROAD_FAV, MARKET_GAP | no | no |
| 20260107 | Murray State Racers | Evansville Purple Aces | BIG_WIN, ROAD_FAV, MARKET_GAP | no | no |
| 20260108 | Gonzaga Bulldogs | Santa Clara Broncos | TOP25, BIG_WIN, MARKET_GAP | yes | no |
| 20260110 | BYU Cougars | Utah Utes | TOP25, BIG_WIN, ROAD_FAV, MARKET_GAP | yes | no |
| 20260114 | Illinois Fighting Illini | Northwestern Wildcats | TOP25, ROAD_FAV, MARKET_GAP | no | no |
| 20260117 | Purdue Boilermakers | USC Trojans | TOP25, ROAD_FAV, MARKET_GAP | yes | no |
| 20260124 | St. John's Red Storm | Xavier Musketeers | TOP25, ROAD_FAV, MARKET_GAP | yes | no |
| 20260124 | Arizona Wildcats | West Virginia Mountaineers | TOP25, BIG_WIN, MARKET_GAP | no | no |
| 20260127 | Michigan State Spartans | Rutgers Scarlet Knights | TOP25, BIG_WIN, ROAD_FAV, MARKET_GAP | yes | no |
| 20260131 | North Dakota State Bison | South Dakota Coyotes | BIG_WIN, ROAD_FAV, MARKET_GAP | yes | no |
| 20260131 | Arizona Wildcats | Arizona State Sun Devils | TOP25, ROAD_FAV, MARKET_GAP | yes | no |
| 20260131 | New Mexico Lobos | San José State Spartans | BIG_WIN, ROAD_FAV, MARKET_GAP | yes | no |
| 20260201 | Iowa State Cyclones | Kansas State Wildcats | TOP25, BIG_WIN, ROAD_FAV, MARKET_GAP | no | no |
| 20260202 | Howard Bison | Coppin State Eagles | BIG_WIN, ROAD_FAV, MARKET_GAP | no | no |
| 20260205 | Michigan Wolverines | Penn State Nittany Lions | TOP25, BIG_WIN, MARKET_GAP | no | no |
(26 more trap games, not listed)
