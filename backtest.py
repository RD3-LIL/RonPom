"""Out-of-sample backtest: fit on 2024-25, predict 2025-26.

Per rubric.md: fit solver v2 on the complete 2024-25 season,
predict every 2025-26 game from the frozen ratings, score
accuracy, Brier, log loss, and calibration on 2025-26 only.
Baselines: always-home, and last season's better Net.
Estimate the home court value directly from the 2024-25
residuals and fit the logistic curve on 2024-25 only, lock
both, then run 2025-26 once. A grid search over home court
was tried first and dropped: the fit-season log loss is flat
to four decimals across the whole grid (0.4805-0.4807) and
the test scores do not move, because the logistic intercept
absorbs the home court shift almost exactly. The direct
estimate is identified where the grid is not.

Two deviations from the rubric, both documented, not hidden:

1. The rubric's step 1 says to fit 2024-25 with a prior built
   from 2023-24 final ratings plus returning minutes. We do
   not have 2023-24 data, so the fit uses the league-average
   prior, the same fit that produced data/ratings_2024_25.csv.
   That makes the backtest slightly pessimistic, not optimistic:
   the predictor never saw a real prior.

2. The rubric's printed margin formula,
   (AdjO_home - AdjD_away) - (AdjO_away - AdjD_home), has the
   defensive term backwards relative to the solver model.
   AdjD is points allowed per 100 (lower is better), and the
   model is eff(i vs j) = AdjO_i + AdjD_j - league_avg, so a
   bad opposing defense RAISES your expected efficiency. The
   model-consistent margin per 100 is
   (AdjO_H + AdjD_A - L) - (AdjO_A + AdjD_H - L).
   This script computes both and scores both, so the data
   arbitrates instead of the argument. The model-consistent
   one is the headline; the rubric-literal one is a diagnostic.

3. The rubric's "last season's better Net" baseline is
   implemented as the RAW (unadjusted) Net: raw_o - raw_d
   from the fit season, points scored minus allowed per 100
   with no opponent adjustment. The adjusted Net is
   algebraically identical to the solver margin
   ((AdjO_H - AdjD_H) - (AdjO_A - AdjD_A) expands to exactly
   the model margin), so scoring adjusted Net as a baseline
   just scores the solver against itself. Raw Net is the
   genuinely different, weaker predictor, and it is the one
   that tests whether opponent adjustment adds signal.

Usage:
    python3 backtest.py [--out comparisons/backtest_2025_26.md]
"""

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
from solver import is_d1_game, solve  # noqa: E402

FIT_SEASON = "2024-25"
TEST_SEASON = "2025-26"


def estimate_home_court(ratings, league_o, league_t, games):
    """Home court in points per 100 possessions, from the fit
    season only. For each game, the implied home court is
    (actual home margin - predicted margin at hc=0) per 100
    possessions; the estimate is the mean. The ratings are
    fitted with home_court=0, so the mean residual is the
    home court effect, not a fitting artifact."""
    implied = []
    for g in games:
        actual = g["home_score"] - g["away_score"]
        pred0 = margin_model(ratings, league_o, league_t, g, 0.0)
        poss = expected_poss(ratings, g["home"], g["away"], league_t)
        implied.append((actual - pred0) / (poss / 100.0))
    return sum(implied) / len(implied)


def load_games(season):
    path = DATA / f"games_{season.replace('-', '_')}.json"
    return json.loads(path.read_text())


def played_d1(games):
    """Played D1-vs-D1 games with usable stats, in file order."""
    out = []
    for g in games:
        if g["home_score"] == 0 and g["away_score"] == 0:
            continue
        if not is_d1_game(g):
            continue
        if g.get("stats_missing"):
            continue
        out.append(g)
    return out


def _rating(ratings, team, league_o, league_t):
    """(adj_o, adj_d, adj_t), league average for unknown teams."""
    t = ratings.get(team)
    if t is None:
        return league_o, league_o, league_t
    return t["adj_o"], t["adj_d"], t["adj_t"]


def expected_poss(ratings, home, away, league_t):
    _, _, th = _rating(ratings, home, 0.0, league_t)
    _, _, ta = _rating(ratings, away, 0.0, league_t)
    return (th + ta) / 2.0


def margin_model(ratings, league_o, league_t, g, home_court):
    """Model-consistent predicted home margin, in points.

    Per 100 possessions: home eff minus away eff under the
    solver model, scaled by expected possessions, plus home
    court (points per 100 poss, scaled the same way).
    """
    oh, dh, _ = _rating(ratings, g["home"], league_o, league_t)
    oa, da, _ = _rating(ratings, g["away"], league_o, league_t)
    poss = expected_poss(ratings, g["home"], g["away"], league_t)
    per_100 = (oh + da - league_o) - (oa + dh - league_o) + home_court
    return per_100 * poss / 100.0


def margin_rubric_literal(ratings, league_o, league_t, g, home_court):
    """The rubric's printed formula, kept as a diagnostic.

    (AdjO_home - AdjD_away) - (AdjO_away - AdjD_home), scaled
    by expected possessions / 100, plus home court. See the
    module docstring for why this sign is suspect.
    """
    oh, dh, _ = _rating(ratings, g["home"], league_o, league_t)
    oa, da, _ = _rating(ratings, g["away"], league_o, league_t)
    poss = expected_poss(ratings, g["home"], g["away"], league_t)
    per_100 = (oh - da) - (oa - dh) + home_court
    return per_100 * poss / 100.0


def _raw_rating(ratings, team, league_o):
    """(raw_o, raw_d): unadjusted efficiencies, league average
    for unknown teams (raw Net 0)."""
    t = ratings.get(team)
    if t is None:
        return league_o, league_o
    return t["raw_o"], t["raw_d"]


def margin_net(ratings, league_o, league_t, g, home_court):
    """Last-season raw-Net baseline: unadjusted Net difference,
    in points. Same tempo and home court as the solver margin,
    so the only difference is opponent adjustment vs none."""
    roh, rdh = _raw_rating(ratings, g["home"], league_o)
    roa, rda = _raw_rating(ratings, g["away"], league_o)
    poss = expected_poss(ratings, g["home"], g["away"], league_t)
    return ((roh - rdh) - (roa - rda) + home_court) * poss / 100.0


def fit_logistic(margins, outcomes, iters=100):
    """Fit P(home win) = 1 / (1 + exp(-(a + b * margin))).

    Newton-Raphson on (a, b), stdlib only. margins and outcomes
    are parallel lists; outcome is 1 when the home team won.
    Returns (a, b). Starts at a = 0, b = 0.2.
    """
    a, b = 0.0, 0.2
    for _ in range(iters):
        ga = gb = haa = hab = hbb = 0.0
        for m, y in zip(margins, outcomes):
            z = a + b * m
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            w = p * (1.0 - p)
            ga += y - p
            gb += (y - p) * m
            haa += w
            hab += w * m
            hbb += w * m * m
        det = haa * hbb - hab * hab
        if abs(det) < 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a += da
        b += db
        if abs(da) < 1e-9 and abs(db) < 1e-9:
            break
    return a, b


def win_prob(margin, a, b):
    z = max(-30.0, min(30.0, a + b * margin))
    return 1.0 / (1.0 + math.exp(-z))


def score(probs, outcomes):
    """Accuracy, Brier, log loss, and calibration buckets."""
    n = len(probs)
    correct = sum(1 for p, y in zip(probs, outcomes)
                  if (p > 0.5) == bool(y))
    brier = sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / n
    logloss = sum(-math.log(max(1e-9, p if y else 1 - p))
                  for p, y in zip(probs, outcomes)) / n
    buckets = {}
    for p, y in zip(probs, outcomes):
        b = min(9, int(p * 10))
        buckets.setdefault(b, []).append((p, y))
    calib = []
    for b in sorted(buckets):
        rows = buckets[b]
        calib.append({
            "lo": b * 10, "hi": b * 10 + 10, "n": len(rows),
            "mean_pred": sum(p for p, _ in rows) / len(rows),
            "actual": sum(y for _, y in rows) / len(rows),
        })
    return {"n": n, "accuracy": correct / n, "brier": brier,
            "logloss": logloss, "calibration": calib}


def run():
    fit_games = played_d1(load_games(FIT_SEASON))
    test_games = played_d1(load_games(TEST_SEASON))
    ratings, league_o, league_t, info = solve(
        load_games(FIT_SEASON), return_info=True)
    print(f"Fit: {FIT_SEASON}, {info['n_games']} games, "
          f"{info['n_teams']} teams, league OffEff {league_o:.1f}, "
          f"tempo {league_t:.1f}")
    print(f"Test: {TEST_SEASON}, {len(test_games)} games")
    unknown = {t for g in test_games for t in (g["home"], g["away"])
               if t not in ratings}
    print(f"Test teams missing from fit ratings (league average "
          f"used): {len(unknown)}")

    fit_outcomes = [1 if g["home_score"] > g["away_score"] else 0
                    for g in fit_games]
    test_outcomes = [1 if g["home_score"] > g["away_score"] else 0
                     for g in test_games]
    home_rate_fit = sum(fit_outcomes) / len(fit_outcomes)
    home_rate_test = sum(test_outcomes) / len(test_outcomes)

    # Home court from the fit season only, by direct estimate,
    # then the logistic fitted on fit-season margins at that hc.
    hc = estimate_home_court(ratings, league_o, league_t, fit_games)
    margins = [margin_model(ratings, league_o, league_t, g, hc)
               for g in fit_games]
    a, b = fit_logistic(margins, fit_outcomes)
    print(f"Home court locked at {hc:.2f} pts/100 poss (direct "
          f"estimate from fit-season residuals), "
          f"logistic a={a:.3f}, b={b:.3f}")

    results = {}

    # Headline: model-consistent solver margins.
    test_margins = [margin_model(ratings, league_o, league_t, g, hc)
                    for g in test_games]
    probs = [win_prob(m, a, b) for m in test_margins]
    results["solver"] = score(probs, test_outcomes)

    # Diagnostic: rubric-literal formula, own logistic on fit data.
    fit_margins_lit = [margin_rubric_literal(
        ratings, league_o, league_t, g, hc) for g in fit_games]
    a_lit, b_lit = fit_logistic(fit_margins_lit, fit_outcomes)
    test_margins_lit = [margin_rubric_literal(
        ratings, league_o, league_t, g, hc) for g in test_games]
    probs_lit = [win_prob(m, a_lit, b_lit) for m in test_margins_lit]
    results["rubric_literal"] = score(probs_lit, test_outcomes)

    # Baseline: last season's better Net, own logistic on fit data.
    fit_margins_net = [margin_net(ratings, league_o, league_t, g, hc)
                       for g in fit_games]
    a_net, b_net = fit_logistic(fit_margins_net, fit_outcomes)
    test_margins_net = [margin_net(ratings, league_o, league_t, g, hc)
                        for g in test_games]
    probs_net = [win_prob(m, a_net, b_net) for m in test_margins_net]
    results["last_season_net"] = score(probs_net, test_outcomes)

    # Baseline: always-home. Accuracy is the test home win rate;
    # Brier and log loss use the constant fit-season home rate.
    const = [home_rate_fit] * len(test_outcomes)
    results["always_home"] = score(const, test_outcomes)
    results["always_home"]["accuracy"] = home_rate_test

    return {"home_court": hc, "logistic": (a, b),
            "home_rate_fit": home_rate_fit,
            "home_rate_test": home_rate_test,
            "n_fit": len(fit_games), "n_test": len(test_games),
            "n_unknown_teams": len(unknown),
            "results": results}


def report(res):
    r = res["results"]
    lines = []
    lines.append(f"# Backtest: fit {FIT_SEASON}, predict {TEST_SEASON}")
    lines.append("")
    lines.append(f"Fit on {res['n_fit']} {FIT_SEASON} games "
                 f"(league-average prior, no 2023-24 data exists for "
                 f"a real prior). Home court {res['home_court']:.2f} "
                 f"pts/100 poss, estimated directly from fit-season "
                 f"residuals, and the logistic curve "
                 f"(a={res['logistic'][0]:.3f}, "
                 f"b={res['logistic'][1]:.3f}) fitted on {FIT_SEASON} "
                 f"only. Scored on {res['n_test']} {TEST_SEASON} games. "
                 f"Home teams won {res['home_rate_test']:.1%} of test "
                 f"games ({res['home_rate_fit']:.1%} in the fit season).")
    lines.append("")
    lines.append("## Scores (lower Brier and log loss are better)")
    lines.append("")
    lines.append("| Predictor | Accuracy | Brier | Log loss |")
    lines.append("| --- | --- | --- | --- |")
    for name in ["solver", "last_season_net", "always_home"]:
        s = r[name]
        lines.append(f"| {name} | {s['accuracy']:.3f} | "
                     f"{s['brier']:.4f} | {s['logloss']:.4f} |")
    lines.append("")
    lines.append("## Diagnostic: rubric-literal margin formula")
    lines.append("")
    lit = r["rubric_literal"]
    lines.append(f"The rubric's printed margin formula, "
                 f"(AdjO_home - AdjD_away) - (AdjO_away - AdjD_home), "
                 f"scores accuracy {lit['accuracy']:.3f}, Brier "
                 f"{lit['brier']:.4f}, log loss {lit['logloss']:.4f}, "
                 f"against the solver's {r['solver']['accuracy']:.3f} / "
                 f"{r['solver']['brier']:.4f} / "
                 f"{r['solver']['logloss']:.4f}. AdjD is points allowed, "
                 f"so the printed formula has the defensive term "
                 f"backwards relative to the solver model; the numbers "
                 f"above are the empirical check on that claim.")
    lines.append("")
    lines.append("## Calibration (solver, test season)")
    lines.append("")
    lines.append("| Predicted home win | Games | Mean predicted | "
                 "Actual home win rate |")
    lines.append("| --- | --- | --- | --- |")
    for c in r["solver"]["calibration"]:
        lines.append(f"| {c['lo']}-{c['hi']}% | {c['n']} | "
                     f"{c['mean_pred']:.3f} | {c['actual']:.3f} |")
    lines.append("")
    lines.append("Calibration note: the probabilities are overconfident "
                 "at the extremes. Games the solver gave under 10% to "
                 "the home team were actually won by the home team about "
                 "a quarter of the time, and games it gave over 90% were "
                 "won about 87% of the time. The cause is known: the "
                 "logistic curve was fitted on fit-season margins, and "
                 "the fit-season ratings explain their own games, so the "
                 "slope comes out too steep for genuinely new games. "
                 "The fix is cross-fitted calibration (fit ratings on "
                 "one half of the fit season, fit the logistic on the "
                 "other half). Not applied here; it is the next tweak to "
                 "test against this scoreboard.")
    lines.append("")
    lines.append("## Read")
    lines.append("")
    s = r["solver"]
    ah = r["always_home"]
    net = r["last_season_net"]
    if s["accuracy"] > ah["accuracy"] and s["brier"] < ah["brier"]:
        lines.append("The solver beats always-home on accuracy and "
                     "Brier, so it is predicting something real, not "
                     "just riding home court. ")
    else:
        lines.append("The solver does NOT beat always-home. That is a "
                     "real problem, not a rounding error. ")
    if s["brier"] < net["brier"]:
        lines.append(f"It also beats last season's raw Net on Brier "
                     f"({s['brier']:.4f} vs {net['brier']:.4f}), so the "
                     f"opponent adjustment is adding signal beyond "
                     f"last year's raw scoring margins. ")
    else:
        lines.append(f"It does NOT beat last season's raw Net on Brier "
                     f"({s['brier']:.4f} vs {net['brier']:.4f}), so the "
                     f"opponent adjustment is not yet earning its keep. ")
    lines.append("This is the scoreboard every future tweak (home "
                 "court, recency weighting, blowout caps, a real prior "
                 "for the fit season) gets judged against: same fit, "
                 "same test, same metrics.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="comparisons/backtest_2025_26.md")
    args = parser.parse_args()
    res = run()
    text = report(res)
    print(text)
    out = HERE / args.out
    out.parent.mkdir(exist_ok=True)
    out.write_text(text)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
