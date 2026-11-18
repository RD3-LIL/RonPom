# Incorporating player stats into RonPom — research notes (corrected)

**Date:** 2026-11-18 (research read 2026-11-18; corrected after review the same day)
**Status:** Research only. No RonPom code was changed. Phase 1 (fuller Oliver ORtg + PORPAG) is not built yet; building it is a separate decision.
**Source:** Deep research into KenPom, Torvik, EvanMiya, hoopR and free data sources, 2026-11-18. The full original report is local only, at `research_notes/ronpom-player-stats-research-20261118-1619/report.md` (not in this repo). A plain-language page version exists as the `ronpom-player-stats-research` artifact.

## Changelog — what was corrected after the Nov 18 review

The first version of this research was reviewed fresh-context on Nov 18 and given a **Block** verdict: the direction was sound, but key formulas could not be implemented as written, phase numbering contradicted itself, and Phase 2 re-proposed work this repo had already tested and rejected. This version fixes all seven blockers, and nothing in it was built or pushed before the fix:

- **B1, PORPAG:** both formulas rewritten with every variable defined (fraction vs percent vs minutes per game), with one worked example and the arithmetic shown. The original form is now `(ORtg - 88) x %Poss x %Min x pace / 100`, all of %Poss and %Min as fractions. A star at ORtg 118, 28% usage, 80% Min, pace 69.4 gives 4.66 points per game, not 436.8.
- **B2, BPM team constraint:** the weighting `w_i` is defined once and used everywhere (see § "How player ratings aggregate to a team number"). It is `sum(%Min_i x BPM_i) = AdjEM`, where %Min weights sum to 5.
- **B3, phase numbering:** one numbering throughout, Phases 0-6 (see § "Phased plan"). The Summary and the metrics table now use it. There is no separate P0-P3 scheme.
- **B4, Phase 2 history:** a "What we already tried" section cites the Nov 14 transfer-blended prior (replaced by noshrinkw600) and the Nov 16 DO NOT ADOPT verdicts for the recruit component and the hybrid prior. The transfer-blended prior is dropped; Phase 2 keeps only KenPom returning-value weighting for returners.
- **B5, Phase 2 dependency:** Phase 2 now explicitly depends on running `fetch_rosters.py` first for class year. No roster data exists in this repo yet. The class multiplier is a later add-on if rosters do not land.
- **B6, Stops:** the garbled Stops formula was deleted. It is cited only as "Oliver Stops, see Basketball on Paper / Basketball-Reference", with no formula reproduced.
- **B7, availability:** rewritten as one explicit formula with every term defined, no undefined "replacement share" multiplier. The old caps are labelled as tuning parameters to be set by backtest, not asserted.
- **M4, data source:** ESPN box scores are the primary source of truth; Torvik is validation-only. The earlier recommendation of Torvik CSVs as primary ingestion was reversed, with reasons given.
- **M8, stale counts:** the README's season counts were updated to the Nov 18 local state (see README.md). The Lillard returning-weight arithmetic was corrected to 3.22 (was 3.23).
- **Other corrections carried in:** the PORPAG table label now says the usage-adjusted form is unverified, not "essentially public"; the EvanMiya author-bias caveat is carried into the Summary; home court is stated in points per 100 possessions, not points per game; the significance test is paired bootstrap on log loss, not Diebold-Mariano.

## Bottom line

KenPom's in-season team ratings are purely team-level. Player stats do **not** enter AdjO, AdjD or AdjEM during the season. They matter in exactly two places:

1. **The preseason prior**, via returning production.
2. **Availability / lineup adjustments**, when a key player is out.

Adding a minutes-weighted player total on top of AdjEM in season mostly double counts what team efficiency already captures. Nobody reputable does it as an additive term.

Evidence for the low ceiling: EvanMiya vs KenPom vs Torvik over 17,000+ games (2023-26) are essentially tied on spread RMSE (about 11.4). The KenPom-EvanMiya MAE gap is 0.004 points per game, which is about 21 points over a 5,300-game season (about 68 over the 17,000-game study, not 23). That comparison is EvanMiya's own self-comparison of his model against KenPom and Torvik, so carry the author-bias caveat: it is not an independent benchmark, and it does not say all three systems are within 0.004 of each other. The KenPom-Torvik gap is larger, about 400 points per season in the same study. Player data, even done at EvanMiya's level with play-by-play, adds almost nothing to average game prediction once AdjEM is known. Gains concentrate in early season and in absence games.

## Correction: what RonPom already does

RonPom already grabs every box stat (minutes, points, FG, 3PT, FT, rebounds, offensive/defensive rebounds, assists, turnovers, steals, blocks, fouls) from the raw ESPN summaries into `player_profiles.py`, and the current player rating RPR already uses them:

```
RPR = (ORtg - 100) * possessions used per game / 100
    + 0.5 * (AST - TO) per game
    + (STL + BLK) per game
    + 0.25 * REB per game
```

What is points-only is the **team** rating: `solver.py` / `ratings.py` AdjO/AdjD are team points per possession, opponent-adjusted, with a prior. No player stat enters the team ratings.

RPR's limits: it is hand-weighted, and its ORtg is simplified (`100 * PTS / (FGA + 0.44*FTA + TO)`), with no assist credit and no offensive-rebound adjustment, so it underrates playmakers. Also note the possessions coefficient: RonPom uses 0.44 everywhere, KenPom uses 0.475. That is a real inconsistency, about 0.7 possessions per game, and Phase 1 must choose one coefficient and state it, or player possessions used will not sum to team possessions under either definition.

## What KenPom actually does

- **In-season:** team game efficiencies (points per 100 possessions, possessions estimated as `FGA - OR + TO + 0.475*FTA`), adjusted iteratively for opponent strength. No player statistic appears in that calculation. Player stats on team pages are description and diagnosis, not inputs.
- **Preseason prior:** last season's offensive efficiency is the best predictor, then the season before, then last season's defensive efficiency, adjusted for returning players. Returning-minute weight (2012 version): `(Player ORtg / Team OE)^2 * (Player %Poss / 20)^2`, with a class curve (freshmen > sophomores > juniors). Returning defense uses Dean Oliver's Stops (formula not reproduced here; see Basketball on Paper / Basketball-Reference). The detailed weights are from 2010-2012 posts, so the structure is reliable and the exact coefficients are stale/unverified, and the transfer-portal era has almost certainly changed them.
  - Worked example, corrected: Damian Lillard, Weber State, `(124.2 / 111.5)^2 * (32.2 / 20)^2 = 3.22` (recomputed 3.216, not 3.23 as in the first draft). His minutes were about 3.2x as important as an average Weber State player's.
- **kPOY:** a separate award, formula proprietary and secret by Pomeroy's own statement (value-to-team times team skill level). Do not present any kPOY formula as verified, and do not try to reverse-engineer it. Its replicable idea is `PlayerValue x TeamStrength`.

KenPom player metrics, for reference: %Min (share of possible minutes), ORtg (Dean Oliver points produced per 100 possessions used; over 110 good, 120 excellent for a workhorse), %Poss (20% average, 25% a go-to guy), %Shots, eFG%, TS%, OR% (over 10% good), DR% (over 20% good), FT Rate, TO% (under 15% great), ARate. There is no KenPom individual defensive rating comparable to ORtg. "BRATE" was not found as a KenPom term; do not use that label for a KenPom stat.

## Best single-number player ratings (box-score only)

| Rating | Verdict |
|---|---|
| College-trained BPM (hoopR recipe: ridge on per-100 rates, team-constrained, qualified at 300+ min, YoY r about 0.75-0.77) | Best box-only option. Needs fitting, not hand weights. |
| Torvik PORPAG / PRPG! (original form, offense-only, in points per game) | Simplest, and the right units for an injury/availability adjustment ("if X is out, subtract ~Y points"). Start here. |
| EvanMiya BPR | Best public metric overall, but needs play-by-play RAPM plus priors and recruiting. Cannot be replicated box-only. Use published BPR as a validation benchmark only. |
| Dean Oliver ORtg / Points Produced | Foundation. Full ORtg gives assist and offensive-rebound credit; RonPom's current ORtg is the simplified form. |
| PER, Win Shares | Descriptive, not predictive. Display only, do not use for team adjustment. |

PORPAGATU! (usage-adjusted PORPAG): the constants found in this research (13.023, 10.143, 1.25/1.5, 104.9, 69.4) come from a secondary Substack restatement, not Torvik's own page. They are **unverified, do not hard-code them**. The table label in the first draft said PORPAG's formula was "essentially public"; that was wrong for the usage-adjusted form, and is corrected here. The original form below is well-attested and safe to implement first.

## PORPAG, done correctly (B1)

Definitions, used consistently everywhere in this doc:

- `ORtg` is points per 100 possessions used (use the adjusted ORtg when available, else the simplified ORtg labelled as such).
- `%Poss` is a **fraction** (0.28, not 28) — the share of team possessions a player uses while on court.
- `%Min` is a **fraction** (0.80, not 80) — the share of one roster spot's available minutes a player plays.
- `pace` is team possessions per game (a count, e.g. 69.4, not a fraction).
- Replacement level is ORtg 88, roughly the 10th man on an average team. PORPAG is points **over replacement** per game, offense only.

Formula (original PORPAG):

```
PORPAG = (ORtg - 88) * %Poss * %Min * pace / 100
```

Worked example, with the arithmetic shown:

```
Star: ORtg 118, %Poss 0.28, %Min 0.80, pace 69.4
PORPAG = (118 - 88) * 0.28 * 0.80 * 69.4 / 100
       = 30 * 0.28 * 0.80 * 0.694
       = 4.66 points per game over replacement
```

The wrong form in the first draft was `(ORtg - 88) * %Poss * %Min * 65`, which gives `30 * 0.28 * 0.80 * 65 = 436.8` points per game. That is nonsense, and it is what happens when pace is used as a raw multiplier instead of `pace / 100`. The usage-adjusted PORPAGATU! form from the first draft had the same class of error: its minutes term was never defined as fraction, percent, or minutes per game, and the three readings gave about 3.3, about 333, or about 125 for the same player. Do not use that form until its variables and constants are verified against Torvik's own page.

## How player ratings aggregate to a team number (B2)

Define the weight once, here, and use it everywhere. Do not use a different weighting in another section.

- `w_i = %Min_i`, where `%Min_i` is the fraction defined above (player minutes / (team games x 40)). Summed over a whole roster, `sum_i w_i = 5`, because there are five spots on court at a time (slightly over 5 in overtime games, a known small bias in the current code).
- For a per-100-possessions rating such as BPM, the team aggregate is:

```
TeamPlayerAggregate = sum_i (%Min_i * BPM_i)
```

- The team constraint (hoopR method) is:

```
sum_i (%Min_i * BPM_i) = AdjEM
```

That is, the minutes-weighted player ratings decompose the team rating; they do not add to it. It follows that the minutes-weighted **mean** BPM is `AdjEM / 5`. Worked example: a team with AdjEM +37 (for example 2024-25 Duke, Net +37.7) has mean BPM about `37 / 5 = 7.4`, which is plausible for a BPM scale that tops out around +10. The first draft instead said the weights were a minutes-weighted mean (weights summing to 1) and then required that sum to equal AdjEM, which would force mean BPM to +37. That was impossible, and is corrected here.
- For a per-game rating such as PORPAG, do **not** minutes-weight it again. `sum_i PORPAG_i` over the rotation is already in points per game.
- Aggregation choice: minutes-weighted over the rotation (players with 10%+ Min or 100+ min), replacement level imputed for unplayed / unknown minutes (BPM about -2, PORPAG about 0), never zero and never the team mean. Not top-5 only (ignores the bench), not an all-roster mean (walk-ons drag it).
- Replacement level, defined explicitly: BPM -2.0 is replacement (Sports-Reference); PORPAG replacement is ORtg 88; BPR 0 is average, about -3 is end-of-bench. A player at replacement is not "zero value", he is the value of the next man up, which is what an availability adjustment must subtract.

### Residual (Phase 5, test only)

```
Residual = TeamPlayerAggregate - AdjEM
         = sum_i (%Min_i * BPM_i) - AdjEM
```

If BPM is team-constrained as above, the residual is zero by construction, and testing it is vacuous; the constraint **is** the aggregation. If BPM is **not** team-constrained, the residual is a candidate feature: `AdjEM_adj = AdjEM + lambda * Residual`, with lambda fit out-of-sample and expected to be small (0 to 0.2). If lambda is about 0 in backtest, drop it. Do not ship a lambda fit in-sample. The first draft defined the residual without saying which weighting it used, so the test was ill-defined; that is fixed here.

## How player stats can feed team ratings (and how they cannot)

| Channel | When it helps | RonPom feasibility |
|---|---|---|
| (A) Preseason prior, returning production | Most valuable. Quality-weighted returning minutes beat raw returning-minutes %. | High, last-season data already on disk. |
| (B) Transfer / freshman priors | Needed in the portal era; hard. Transfers volatile, freshmen uncertain. | Medium, and see the "What we already tried" section below. Do not re-propose the transfer-blended prior. |
| (C) In-season availability adjustment | Second-most valuable, and the only in-season use that is not double-counting. Tonight's team is not the season-average team when a star is out. | High, if there is a credible per-game player value (PORPAG) and an availability feed, even a manual one. |
| (D) In-season minutes-weighted player aggregate added to AdjEM | Mostly noise / double-counting. | Do not do as an additive term. Use only as a diagnostic, or as a shrunk residual (Phase 5), and ship only if it passes out-of-sample backtest. |

### Availability adjustment, done correctly (B7)

Let `Value_i = PORPAG_i`, in points per game **over replacement**. That phrase matters: PORPAG already nets replacement out, so there is no extra "replacement share" multiplier and no second add-back of a replacement player. If player `i` is out and was in the expected rotation:

```
AdjO_adj = AdjO - PORPAG_i / TeamPace * 100
```

Every term: `AdjO` is the team's adjusted offensive efficiency in points per 100 possessions; `PORPAG_i` is points per game over replacement; `TeamPace` is team possessions per game; dividing by pace and multiplying by 100 converts points per game to points per 100 possessions. The same form applies on defense with DBPM / D-PORPAG, shrunk harder than offense, because box-score defense is a weak proxy.

Worked example: the star above, PORPAG 4.66, team pace 69.4, gives `4.66 / 69.4 * 100 = 6.7` points per 100 possessions. That is a large adjustment, and it is larger than the old caps in the first draft (about 4 for one player, about 6 for multiple). Those caps had no source and no backtest behind them, so they are **not asserted here**. Treat any cap as a tuning parameter to be set by backtest on absence games only, and only apply the adjustment for players with %Min at least 20% and a value materially above replacement. The first draft's formula multiplied by an undefined "replacement share" and then talked about adding a replacement value back; that double counts, and is removed here.

## What we already tried — Phase 2 history (B4)

Phase 2 must be read against this history, or it will waste a build cycle re-proposing rejected work.

- **Transfer-blended prior, replaced Nov 14, 2026.** The old prior was a minutes-weighted average of source teams' ratings, so a star transfer from a weak team dragged the prior down, freshmen with no profile counted as league average, and the whole thing was faded again by informed share times 0.85. Arizona was +33.9 last season but its old prior was only +9.3, with prior defense 104.6 against its own last-season 91.8. That put Arizona 35th, Iowa State 40th, Alabama 39th, Texas Tech 37th, against KenPom's 9th, 15th, 17th and 16th. The adopted replacement is **noshrinkw600**: own-team rating regressed 0.85 toward league, weight 600 scaled by informed share (`600 * (0.25 + 0.75 * informed share)`). It puts those teams at 10th, 17th, 21st and 24th, with KenPom rho 0.779 on Nov 14. Source: `build_prior_2026.py` docstring and `comparisons/mend_2026-11-14.md`.
- **Recruit component, DO NOT ADOPT, Nov 16, 2026.** A freshman recruiting component inside the blend was tested in `comparisons/recruit_component_2026-11-16.md`. Verdict DO NOT ADOPT: prediction was a wash (Brier slightly better but unconfirmed, spread MAE worse), KenPom rho 0.435 vs 0.470 for the plain blend and 0.744 for noshrinkw600, and the marginal test (recruit minus blend) was a precise zero on Brier. Grade explains little of individual freshman ORtg (R2 = 0.082).
- **Hybrid prior (noshrink + recruiting), DO NOT ADOPT, Nov 16, 2026.** Tested in `comparisons/hybrid_prior_2026-11-16.md`. Verdict DO NOT ADOPT: Brier directionally better but unconfirmed, KenPom rho 0.604 vs 0.744 for noshrinkw600, MAD 5.8 vs 4.4. It fixes Illinois and Iowa State but breaks Arizona, Kansas and Texas. The note's own diagnosis: the adjustment compares freshmen to last year's elite team, so for every good team it pulls the prior down.

**Decision for Phase 2:** drop the transfer-blended prior. Do not re-propose it unless a concrete level-adjustment is stated that avoids the Arizona failure, i.e. a transfer from a weak team must not drag a strong team's prior down toward the weak team's rating, and the proposal must say exactly how that is prevented and be tested against the same two judges (rolling-origin prediction and the KenPom list). No such adjustment is proposed in this doc. Phase 2 therefore keeps only KenPom returning-value weighting for **returners**, on top of the adopted noshrinkw600 program anchor, with unknown minutes at replacement level (ORtg about 88 / BPM about -2), not team mean and not zero. Freshman and transfer priors are open questions, not part of the Phase 2 design (see "Open design questions").

### Phase 2 dependency: rosters and class year (B5)

Phase 2 depends on running `fetch_rosters.py` first and joining class year by athlete_id. That has **not** happened yet: there is no `data/raw/rosters/` output in this repo as of Nov 18, 2026, and `player_profiles.py` states explicitly that it has no height, weight or class year. Do not assume class year exists.

`fetch_rosters.py` fetches ESPN rosters per team per season; each athlete carries id, name, position, jersey, height, weight and experience (Freshman / Sophomore / Junior / Senior years). Two caveats from that file: the `?season=` form returns a postseason snapshot (10 athletes for Illinois 2025-26 vs 14 on the current roster), so treat it as a returning-player identity list, not a full depth chart; and athlete_id alone is not a safe person key, because ESPN id 5325549 (Jeremiah White) appears for two non-D1 teams in 2025-26, likely an id reuse, so join with a name/team sanity check. If rosters do not land, drop the class multiplier (FR > SO > JR) from Phase 2 and note it as a later add-on; the returning-value weighting for returners can proceed without it.

## Phased plan (Phases 0-6, one numbering throughout)

| Phase | What | Success criterion |
|---|---|---|
| 0. Freeze baseline | Lock team-only AdjO/AdjD/AdjEM + prior; walk-forward, point-in-time backtest harness (log loss / Brier / spread MAE) | Baseline numbers on 2-3 held-out seasons, documented |
| 1. Player rates + PORPAG | %Min, %Poss, eFG%, TS%, OR%/DR%, AST%, TO%, STL%, BLK%, simplified Oliver ORtg (labelled simplified, see open question M1), PORPAG original form (see § PORPAG above). Usage-adjusted PORPAG only once its constants are verified against Torvik's own page. | PORPAG correlates r > 0.9 with Torvik's published PORPAG on the same seasons; leaderboard looks sane (stars on top, not walk-ons) |
| 2. Preseason prior v2 | KenPom returning-value weighting for returners, on the noshrinkw600 anchor; class curve only if rosters land (see B5); no transfer-blended prior, no recruit component as tested Nov 16 (see B4). Unknown minutes at replacement level. Fit prior weight / decay by backtest. | November log loss improves vs Phase 0 on held-out seasons; preseason rank correlation improves |
| 3. College BPM | Ridge BPM, team-constrained as defined in § "How player ratings aggregate", shrunk, qualified flag at 300+ min; validate vs hoopR BPM and EvanMiya BPR (r, rank overlap). Feature list is an open question (see M3): shot-location shares are not in ESPN box scores. | YoY r for qualified players about 0.7+; correlation with BPR about 0.7+; OBPM/DBPM weakly correlated |
| 4. Availability adjustment | Manual or ESPN injury feed, subtract PORPAG / BPM-over-replacement per the formula in § "Availability adjustment", caps tuned by backtest not asserted; backtest on games with known absences only | Log-loss gain on absence-games subset; no loss on full season |
| 5. Ship / don't ship the residual | Test the residual term as defined in § "Residual (Phase 5)"; ship only if it passes the backtest protocol | Either a proven gain or a documented "no gain, dropped" |
| 6. Optional: play-by-play | CBD/NCAA PBP, on/off, RAPM-lite shrunk to BPM prior | Multi-week project; only after Phases 0-5 |

## Backtest protocol (follow it exactly)

1. Walk-forward, never random K-fold. Train on seasons up to T, predict T+1.
2. Point-in-time ratings only: a prediction for a game on date D uses only data available before D. Note the hidden cost (see M5): the current player pipeline aggregates whole seasons with no date field, so point-in-time player ratings need a per-game player table first.
3. Baseline first: team-only AdjEM, home court in points per 100 possessions (`solver.py` documents about 1.0 to 2.0 per side, default 0.0; do not use "3-4 points" without a unit, as the first draft did), pace to predicted score/spread.
4. Test challengers one at a time, not all together.
5. Report log loss (primary), Brier, spread MAE/RMSE, win% accuracy (report, do not optimise on it).
6. Require the gain to hold in at least 2 of 3 held-out seasons, or a paired bootstrap on log loss with p < 0.05 and a stated multiple-testing correction. Do not use Diebold-Mariano for log loss, as the first draft suggested. A gain that only appears in-sample is a failure. Note also (see M5): only 2026-27 currently uses a real preseason prior; 2024-25 and 2025-26 still use the league-average prior, so a 3-season held-out backtest of the prior cannot run as stated until those priors are built.
7. Report November, December, January+ separately. Prior and availability gains, if any, show in November and vanish by February.
8. Check calibration (reliability plot by predicted-win-probability bucket). A player adjustment that improves MAE but wrecks calibration is a net loss.
9. Ablation for defense: test OBPM-only vs OBPM+DBPM. If DBPM hurts log loss, drop it from the team adjustment and keep it for display.

Expected outcome: (A) preseason prior, small but real gain in November. (B) availability, real gain on the ~5-10% of games with a material absence, invisible in season averages. (C) residual, most likely no gain; if it "helps", check for leakage first.

## Pitfalls that matter most

- **Small samples:** hoopR BPM standard deviation is 6.89 at under 50 min, plateauing around 3.5-3.7 only at 600-800+ min. Minutes floor for display (300+ min for ranking, 100+ min for any team use) and Bayesian shrinkage for use. Shrinkage starting values in the first draft (k about 300 possessions for ORtg, about 200 min for BPM) are tuning parameters with no derivation, and the BPM one contradicts the 600-800 min plateau evidence; do not treat them as derived.
- **Double-counting:** team AdjEM already contains every point, rebound, assist, steal, block and turnover in the player metrics.
- **Pace and opponent adjustment are not optional:** raw PPG/RPG/APG reward fast teams; a 120 ORtg vs the SWAC is not a 120 ORtg vs the Big Ten.
- **Defense in box scores is a proxy, not a measurement:** shrink it harder than offense, never rank defenders by DBPM alone. The "cap the defensive component at about 30-40%" rule in the first draft had no source or backtest; it is a heuristic, to be set by the OBPM-only vs OBPM+DBPM ablation in the backtest protocol, not asserted as a rule.
- **Usage-efficiency tradeoff:** a role player at 125 ORtg on 15% usage is not better than a star at 112 ORtg on 32% usage.
- **Assist and rebound credit are hard:** use AST% and OR%/DR% rather than raw totals; let a fitted model decide weights, do not add "AST x 2" by hand. On rebound credit, do not use the hoopR fitted slopes quoted in the first draft (`oreb_pct` +0.325, `dreb_pct` -0.325) as evidence for weighting ORB over DRB; a negative DRB slope is almost certainly a collinearity artifact, not a causal weight, and it was unverified.
- **Regression to the mean for shooting:** 3P% over under 100 attempts is mostly noise; shrink toward position/league mean by attempts.

## Data source of truth (M4)

**Decision: ESPN box scores are the primary source of truth for RonPom. Torvik is validation-only.**

Reasons: RonPom's stated principle is "Free ESPN box scores only", stdlib-only, and `player_profiles.py` reads only local files with no network calls. The ESPN data is already owned, already pulled for three seasons, and already validated in-sample (summed player points matched parsed team scores in a 25-game sample). Torvik CSVs are the best free source of already-computed advanced stats, but they have no headers, 67 fields expanding to 78 since Nov 2026 with 11 undocumented, column mapping must be re-checked on each fetch, and Torvik asks to be contacted before bulk use. Mixing Torvik `adj_oe` with ESPN raw ORtg would break reproducibility, and the first draft's Phase 1 success criterion (correlate r > 0.9 with Torvik's published PORPAG) would be circular if Torvik were both input and validation. With Torvik as validation-only, that criterion is a genuine check: compute PORPAG from ESPN box scores, then compare it to Torvik's published PORPAG on the same player-seasons.

Other sources, in the same roles as the first draft: CollegeBasketballData API (free key, structured player season + per-game box + plays/lineups, useful if game-level player stats are ever needed); Sports-Reference CBB (rich tables incl. BPM/PER/WS, no official API, validation / spot-check only, do not scrape in bulk); hoopR / SportsDataverse (wrappers and pre-built data releases, incl. college BPM loaders; its KenPom wrappers require a paid subscription, do not use them to circumvent the paywall); NCAA.com (leaderboards only). KenPom is paywalled. Do not scrape it.

What no box-score source gives you: who guarded whom, screens, spacing, help defense, deflections, contested shots, on/off splits, lineup combinations, shot location (except via CBD/NCAA shots data). Any individual defensive rating built from box scores is therefore a proxy, not a measurement.

## Illinois preview, 2026-27 season (Nov 18, 2026, 12:00 files)

From `data/players_2026_27.csv` (7,721 players, 7,683 with minutes; Illinois 5 GP). Team context from `data/ratings_2026_27.csv`: Illinois #1 at Net +37.3, AdjO 130.3, AdjD 93.0, AdjT 74.8. Early season, 5 games, take the rank with a grain of salt.

| Player | Pts | Ast | ORtg | %Poss | RPR |
|---|---|---|---|---|---|
| Andrej Stojakovic | 27.0 | 3.4 | 130.6 | 30.6 | 9.73 |
| Quentin Coleman | 17.8 | 4.4 | 114.3 | 24.5 | 7.52 |
| Ethan Brown | 9.6 | 4.8 | 123.5 | 12.4 | 6.72 |
| Tomislav Ivisic | 11.2 | 2.4 | 90.0 | 25.7 | 2.01 |
| Stefan Vaaks | 11.4 | 2.0 | 82.9 | 28.4 | 0.11 |

Brown is third on the team despite low usage, driven by the flat `0.5*(AST-TO)` add-on in RPR, not by ORtg, which gives him no assist credit. That is exactly the playmaker gap Phase 1 is meant to fix.

Small-sample flags: Lincoln Williams ORtg 149.4 on 11.1% usage; Jake Davis ORtg 227.3 in 1 game on 6.2% usage. This is why the 40% %Min leaderboard floor in the code matters.

## Open design questions (carried, not silently resolved)

- **M1, simplified Oliver ORtg is underspecified.** "Points produced approx scoring + assist credit + ORB credit" gives no weights, no `qAST` / team-assist-rate handling, and no possession decomposition. The claim in the first draft that the simplified version "correlates >0.95 with the full version" had no source; do not state it as fact. Phase 1 must either give the exact simplified formula with weights and a validation target (correlate vs Torvik `adj_oe` on the same player-seasons, report r), or scope Phase 1 to the original PORPAG form only and defer full Oliver ORtg.
- **M2, per-possession rates are named but not defined.** AST%, TO%, STL%, BLK%, OR%/DR% need denominators (AST% is assists per teammate field goal made while on court; STL% is steals per opponent possession while on court; OR% needs team OR plus opponent DR while on court). The first draft's shorthand for %Poss was just the numerator, not the rate. The existing code already does %Poss correctly via the Basketball-Reference formula in `compute_usage()`; Phase 1 should reference that instead of redefining it loosely. OR%/DR% at season level are computable from parsed team totals, but per-game opponent adjustment is not in `player_profiles.py` today (team totals are season sums only).
- **M3, BPM feature list is not implementable from current data.** The 16 hoopR features include shot shares (rim/mid/3). ESPN box scores have no shot location; those features need CBD/NCAA shot data or must be dropped. The list also includes PTS/REB/AST per 100 alongside the rate features, which are near-duplicates. State the feature list as "to be finalised after checking what the chosen source actually carries", not as a ready recipe. The hoopR ridge lambdas (300 offense / 100 defense) and training seasons should be re-checked against the hoopR page before coding, not taken from the research paraphrase.
- **M5, backtest protocol underestimates the work.** Point-in-time player ratings need a per-game player table first (see backtest protocol step 2). Only 2026-27 uses a real preseason prior; 2024-25 and 2025-26 still use the league-average prior. Home court must be stated in points per 100 possessions. Significance must use paired bootstrap with a multiple-testing correction, not Diebold-Mariano. Shrinkage starting k values are tuning parameters, not derived values (see Pitfalls).

## Open questions / what could not be verified

- kPOY exact formula: proprietary, secret.
- Current KenPom preseason formula: detailed weights are from 2010-2012 posts; current coefficients, transfer-portal handling and freshman treatment are unverified.
- Torvik PORPAGATU! current constants: from a secondary restatement; verify against Torvik's own page before hard-coding.
- EvanMiya BPR exact weights/priors: structure public, coefficients proprietary. The "r < ~0.7, something is wrong" threshold in the first draft was the researcher's own heuristic, not EvanMiya's; label it as such.
- Haslametrics: no player metric was found; it appears to be team-only. Do not cite it as a player-rating system.
- No clean ablation study found isolating "team-only vs team + minutes-weighted player aggregate" on log loss/Brier. RonPom's own backtest is the only way to settle it for its own data.
- Torvik CSV field expansion: 78 fields since Nov 2026, 11 undocumented; re-check column mapping on each fetch.
- ESPN APIs are undocumented, change without notice, about 1 req/sec. Any ESPN-based ingestion needs a fallback (Torvik / CollegeBasketballData).
- Possessions coefficient: RonPom uses 0.44, KenPom uses 0.475 (see "Correction: what RonPom already does").

## Sources (primary, verified live 2026-11-18)

- KenPom preseason ratings: https://kenpom.com/blog/say-hello-to-your-big-ten-overlords/
- KenPom kPOY race (2013): https://kenpom.com/blog/the-2013-kenpom.com-poy-race/
- EvanMiya BPR: https://blog.evanmiya.com/p/bayesian-performance-rating
- EvanMiya / KenPom / Torvik comparison (2023-26, 17k+ games): https://blog.evanmiya.com/p/which-cbb-supercomputer-should-you — self-comparison, carry the author-bias caveat (see Bottom line).
- hoopR college BPM model: https://hoopr.sportsdataverse.org/articles/college-basketball-player-value-model.html
- Sports-Reference Win Shares: https://www.sports-reference.com/cbb/about/ws.html
- Torvik data availability: https://adamcwisports.blogspot.com/p/data.html

Secondary / index sources (search results, not opened in full): KenPom Ratings Glossary, KenPom Individual Stats Primer, KenPom roster attrition, APBRmetrics adjusted-stats discussion, Dean Oliver ORtg (Basketball-Reference), BPM origin (Sports-Reference blog), PER (Hollinger), PORPAG restatement (Beyond the Score / The Only Colors), Torvik fields (SportsDataverse docs), EvanMiya how-it-works, Value Add (Pudner Sports), CollegeBasketballData (hoopR docs), ESPN endpoints catalogue (hoopR docs), NCAA stats leaderboards.

## What NOT to do

Do not scrape KenPom. Do not hand-weight a new composite and call it a rating. Do not add a player sum to AdjEM. Do not rank players by unadjusted ORtg or PER. Do not use DBPM to rank defenders. Do not backtest in-sample.
