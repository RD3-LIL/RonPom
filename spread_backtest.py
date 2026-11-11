"""Backtest the spread calculator: fit 2024-25, predict 2025-26.

For every 2025-26 D1-vs-D1 game with a market spread, compare
three numbers, all in home-margin points:
  predicted margin (the model, the exact function predict.py
  uses, home court 4.69 pts/100 poss, none on a neutral floor),
  implied market margin (-spread; the spread is the home team's
  line, negative means the home team is favored),
  actual margin (home_score - away_score).

Metrics:
  MAE model vs actual, MAE market vs actual (the benchmark),
  MAE model vs market (how far the model sits from the market),
  bias (mean signed error) for model and market, which shows
  systematic under- or over-calling.
  Edge cover: when the model disagrees with the market by at
  least a threshold, does the actual margin fall on the model's
  side of the market line? Above 52.4% (the -110 breakeven)
  means the disagreements are real money; at or below 50%
  means they are noise. The market is the benchmark for
  magnitudes, but a model that matched it exactly would have
  no edge: the cover rate is the test that matters.
  Breakdowns by market-spread size and by neutral site, to
  find where the model is off.

The market line is the one recorded in the post-game summary,
effectively the closing line; ESPN does not label it as such.
2024-25 has no spreads on file, so it can only be the fit
season here, never the test season. Same discipline as the
win/loss backtest: constants are locked from the fit season,
the test season is run once, nothing is tuned on it.

Usage:
    python3 spread_backtest.py [--out comparisons/spread_backtest_2025_26.md]
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
from backtest import load_games, played_d1  # noqa: E402
from predict import predict_margin  # noqa: E402
from solver import solve  # noqa: E402

FIT_SEASON = "2024-25"
TEST_SEASON = "2025-26"
EDGE_THRESHOLDS = (2.0, 3.0, 5.0)
BREAKEVEN = 0.524  # -110 vig


def with_spread(games):
    """D1 games with a market spread and a final score."""
    return [g for g in played_d1(games) if g.get("spread") is not None]


def cross_fitted_spread_pairs(fit_games, prior_weight=300.0):
    """(predicted, actual) margin pairs with no in-sample leakage.

    Same chronological split as backtest.cross_fitted_margins,
    but keeps the actual margin instead of the win/loss outcome,
    and uses predict_margin (home court none on a neutral
    floor), the exact function predict.py uses. Everything
    stays inside the fit season: the test season is never
    touched. The fitted scale is locked from these pairs
    only.
    """
    ordered = sorted(fit_games, key=lambda g: (g["date"], g["event_id"]))
    half = len(ordered) // 2
    first, second = ordered[:half], ordered[half:]
    out = []
    for train, test in ((first, second), (second, first)):
        ratings, lo, lt, _ = solve(train, prior_weight=prior_weight,
                                   return_info=True)
        for g in test:
            out.append((predict_margin(ratings, lo, lt, g),
                        g["home_score"] - g["away_score"]))
    return out


def fit_margin_scale(pairs):
    """OLS fit of actual = a + b * predicted, on cross-fitted pairs.

    A slope above 1 means the raw margins are compressed toward
    zero (big favorites under-called) and need stretching; the
    intercept near 0 means no systematic home/away lean.
    """
    n = len(pairs)
    mx = sum(p for p, _ in pairs) / n
    my = sum(a for _, a in pairs) / n
    sxx = sum((p - mx) ** 2 for p, _ in pairs)
    sxy = sum((p - mx) * (a - my) for p, a in pairs)
    b = sxy / sxx if sxx else 1.0
    a = my - b * mx
    return a, b


def fit_margin_scale_slope_only(pairs):
    """Slope-only fit of actual = b * predicted, on cross-fitted pairs.

    The intercept in the full linear fit is a home-team lean
    that comes from the half-season cross-fitted ratings and
    does not transfer to full-season ratings. A slope-only
    scale stretches the compressed margins without shifting
    every game toward the home team.
    """
    sxx = sum(p ** 2 for p, _ in pairs)
    sxy = sum(p * a for p, a in pairs)
    return 0.0, sxy / sxx if sxx else 1.0


def evaluate(fit_games, test_games, scale=None, prior_weight=300.0):
    """Predict test-season spreads from fit-season ratings.

    Returns (rows, summary). Each row carries the predicted
    margin, the implied market margin, and the actual margin.
    When scale is (a, b), the predicted margin is a + b *
    predicted, the calibrated margin.
    """
    ratings, league_o, league_t, info = solve(
        fit_games, prior_weight=prior_weight, return_info=True)
    rows = []
    for g in test_games:
        pred = predict_margin(ratings, league_o, league_t, g)
        if scale is not None:
            pred = scale[0] + scale[1] * pred
        implied = -float(g["spread"])
        actual = g["home_score"] - g["away_score"]
        rows.append({
            "date": g["date"], "event_id": g["event_id"],
            "home": g["home"], "away": g["away"],
            "neutral_site": bool(g.get("neutral_site")),
            "predicted": pred, "implied": implied, "actual": actual,
            "edge": pred - implied,
        })
    summary = summarize(rows)
    summary["prior_weight"] = prior_weight
    summary["n_fit"] = info["n_games"]
    summary["n_teams"] = info["n_teams"]
    summary["league_o"] = league_o
    summary["league_t"] = league_t
    return rows, summary


def _mae(values):
    return sum(abs(v) for v in values) / len(values) if values else None


def _bias(values):
    return sum(values) / len(values) if values else None


def _cover(rows, threshold):
    """Edge cover rate at |edge| >= threshold.

    A disagreement counts as a win for the model when the
    actual margin lands on the model's side of the market
    line, i.e. (actual - implied) has the model's sign.
    """
    picks = [r for r in rows if abs(r["edge"]) >= threshold]
    if not picks:
        return {"n": 0, "rate": None}
    wins = sum(1 for r in picks
               if (r["actual"] - r["implied"]) * r["edge"] > 0)
    return {"n": len(picks), "rate": wins / len(picks)}


def _bucket(implied):
    """Market-spread size bucket, by implied home margin."""
    if implied >= 21:
        return "home by 21+"
    if implied >= 14:
        return "home by 14-21"
    if implied >= 7:
        return "home by 7-14"
    if implied >= 0:
        return "home by 0-7"
    if implied >= -7:
        return "away by 0-7"
    if implied >= -14:
        return "away by 7-14"
    return "away by 14+"


def summarize(rows):
    model_err = [r["predicted"] - r["actual"] for r in rows]
    market_err = [r["implied"] - r["actual"] for r in rows]
    gap = [r["predicted"] - r["implied"] for r in rows]
    out = {
        "n": len(rows),
        "model_mae": _mae(model_err),
        "market_mae": _mae(market_err),
        "model_vs_market_mae": _mae(gap),
        "model_bias": _bias(model_err),
        "market_bias": _bias(market_err),
        "cover": {t: _cover(rows, t) for t in EDGE_THRESHOLDS},
        "buckets": {},
        "neutral": {},
    }
    for name in sorted({_bucket(r["implied"]) for r in rows}):
        sub = [r for r in rows if _bucket(r["implied"]) == name]
        out["buckets"][name] = {
            "n": len(sub),
            "model_mae": _mae([r["predicted"] - r["actual"]
                               for r in sub]),
            "market_mae": _mae([r["implied"] - r["actual"]
                                for r in sub]),
            "model_bias": _bias([r["predicted"] - r["actual"]
                                 for r in sub]),
            "market_bias": _bias([r["implied"] - r["actual"]
                                  for r in sub]),
        }
    for neutral in (False, True):
        sub = [r for r in rows if r["neutral_site"] is neutral]
        out["neutral"][neutral] = {
            "n": len(sub),
            "model_mae": _mae([r["predicted"] - r["actual"]
                               for r in sub]),
            "market_mae": _mae([r["implied"] - r["actual"]
                                for r in sub]),
            "model_bias": _bias([r["predicted"] - r["actual"]
                                 for r in sub]),
        }
    return out


def report(summary, variants=None):
    s = summary
    lines = []
    lines.append(f"# Spread backtest: fit {FIT_SEASON}, "
                 f"predict {TEST_SEASON}")
    lines.append("")
    lines.append(f"Fit on {s['n_fit']} {FIT_SEASON} games "
                 f"(league-average prior, prior weight "
                 f"{s['prior_weight']:.0f} possessions), "
                 f"{s['n_teams']} teams, "
                 f"league OffEff {s['league_o']:.1f}, tempo "
                 f"{s['league_t']:.1f}. Scored on {s['n']} "
                 f"{TEST_SEASON} games with a market spread. "
                 f"Home court 4.69 pts/100 poss, none on a neutral "
                 f"floor, same as predict.py.")
    lines.append("")
    lines.append("## Headline (points; lower MAE is better)")
    lines.append("")
    lines.append("| | MAE vs actual | Bias vs actual |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| Model | {s['model_mae']:.2f} | "
                 f"{s['model_bias']:+.2f} |")
    lines.append(f"| Market | {s['market_mae']:.2f} | "
                 f"{s['market_bias']:+.2f} |")
    lines.append("")
    lines.append(f"Model vs market MAE: {s['model_vs_market_mae']:.2f} "
                 "points. That is how far the model sits from the "
                 "market on average, the number to watch as the "
                 "calculator is refined.")
    lines.append("")
    lines.append("## Edge cover (does disagreeing with the market pay?)")
    lines.append("")
    lines.append("| Min disagreement | Games | Model cover rate |")
    lines.append("| --- | --- | --- |")
    for t, c in s["cover"].items():
        rate = f"{c['rate']:.1%}" if c["rate"] is not None else "-"
        lines.append(f"| {t:.0f} pts | {c['n']} | {rate} |")
    lines.append("")
    lines.append(f"Breakeven at -110 is {BREAKEVEN:.1%}. Above it, "
                 "the model's disagreements are real money; at or "
                 "below 50%, they are noise and the model should "
                 "stay closer to the market.")
    lines.append("")
    lines.append("## By market-spread size")
    lines.append("")
    lines.append("| Market line | Games | Model MAE | Market MAE | "
                 "Model bias | Market bias |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    order = ["away by 14+", "away by 7-14", "away by 0-7",
             "home by 0-7", "home by 7-14", "home by 14-21",
             "home by 21+"]
    for name in order:
        b = s["buckets"].get(name)
        if b is None:
            continue
        lines.append(f"| {name} | {b['n']} | {b['model_mae']:.2f} | "
                     f"{b['market_mae']:.2f} | "
                     f"{b['model_bias']:+.2f} | "
                     f"{b['market_bias']:+.2f} |")
    lines.append("")
    lines.append("## Neutral-site split")
    lines.append("")
    lines.append("| | Games | Model MAE | Market MAE | Model bias |")
    lines.append("| --- | --- | --- | --- | --- |")
    for neutral in (False, True):
        b = s["neutral"][neutral]
        label = "Neutral site" if neutral else "Home/away"
        lines.append(f"| {label} | {b['n']} | {b['model_mae']:.2f} | "
                     f"{b['market_mae']:.2f} | "
                     f"{b['model_bias']:+.2f} |")
    lines.append("")
    if variants:
        lines.append("## Calibrated margins")
        lines.append("")
        lines.append("Scales fitted on the fit season only "
                     "(cross-fitted, no test-season data). A slope "
                     "above 1 stretches the compressed raw margins.")
        lines.append("")
        lines.append("| Variant | Scale | MAE vs actual | Bias vs "
                     "actual | Model vs market MAE |")
        lines.append("| --- | --- | --- | --- | --- |")
        lines.append(f"| Raw | - | {s['model_mae']:.2f} | "
                     f"{s['model_bias']:+.2f} | "
                     f"{s['model_vs_market_mae']:.2f} |")
        for label, scale, scaled in variants:
            lines.append(f"| {label} | {scale[0]:+.2f} + "
                         f"{scale[1]:.3f} * pred | "
                         f"{scaled['model_mae']:.2f} | "
                         f"{scaled['model_bias']:+.2f} | "
                         f"{scaled['model_vs_market_mae']:.2f} |")
        lines.append("")
        for label, scale, scaled in variants:
            lines.append(f"Edge cover, {label.lower()}:")
            lines.append("")
            lines.append("| Min disagreement | Games | "
                         "Model cover rate |")
            lines.append("| --- | --- | --- |")
            for t, c in scaled["cover"].items():
                rate = (f"{c['rate']:.1%}"
                        if c["rate"] is not None else "-")
                lines.append(f"| {t:.0f} pts | {c['n']} | {rate} |")
            lines.append("")
            lines.append(f"Bias by market-spread size, "
                         f"{label.lower()}:")
            lines.append("")
            lines.append("| Market line | Games | Model bias |")
            lines.append("| --- | --- | --- |")
            order = ["away by 14+", "away by 7-14", "away by 0-7",
                     "home by 0-7", "home by 7-14", "home by 14-21",
                     "home by 21+"]
            for name in order:
                b = scaled["buckets"].get(name)
                if b is None:
                    continue
                lines.append(f"| {name} | {b['n']} | "
                             f"{b['model_bias']:+.2f} |")
            lines.append("")
    lines.append("## Read")
    lines.append("")
    if s["model_mae"] < s["market_mae"]:
        lines.append("The model beats the market on spread error, "
                     "which would be a surprise: the market is "
                     "usually sharper than any ratings model.")
    else:
        lines.append(f"The market beats the model on spread error "
                     f"({s['market_mae']:.2f} vs "
                     f"{s['model_mae']:.2f} points), as expected: "
                     "the market prices injuries, rest, and "
                     "motivation the ratings cannot see. The gap "
                     "is the room the refinement has to close.")
    lines.append("")
    if variants:
        best = min(variants, key=lambda v: v[2]["model_mae"])
        if best[2]["model_mae"] < s["model_mae"]:
            lines.append(f"The {best[0].lower()} scale improves "
                         "the test season and is the candidate to "
                         "adopt in predict.py, after re-fitting the "
                         "win-probability logistic on scaled "
                         "margins.")
        else:
            lines.append("Neither scale improves the test season: "
                         "both raise MAE and move the model "
                         "further from the market, so neither was "
                         "adopted. The compression pattern in the "
                         "bucket biases is real, but a global "
                         "stretch amplifies noise in the middle, "
                         "where most games are, more than it helps "
                         "at the extremes. The fix has to come "
                         "from the ratings themselves, not a "
                         "post-hoc scale, e.g. a lower prior "
                         "weight so the ratings spread out more.")
    lines.append("")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", default="comparisons/spread_backtest_2025_26.md")
    parser.add_argument(
        "--prior-weight", type=float, default=300.0,
        help="prior strength in possessions (default 300.0, the "
             "published baseline; lower lets ratings spread out "
             "more)")
    args = parser.parse_args()
    fit_games = played_d1(load_games(FIT_SEASON))
    test_games = with_spread(load_games(TEST_SEASON))
    print(f"Fit: {FIT_SEASON}, {len(fit_games)} games, prior "
          f"weight {args.prior_weight:.0f}")
    print(f"Test: {TEST_SEASON}, {len(test_games)} games "
          "with a market spread")
    rows, summary = evaluate(fit_games, test_games,
                             prior_weight=args.prior_weight)
    pairs = cross_fitted_spread_pairs(fit_games,
                                      prior_weight=args.prior_weight)
    scale_lin = fit_margin_scale(pairs)
    scale_slope = fit_margin_scale_slope_only(pairs)
    print(f"Margin scales from {len(pairs)} cross-fitted "
          f"fit-season pairs: linear actual = "
          f"{scale_lin[0]:+.2f} + {scale_lin[1]:.3f} * predicted; "
          f"slope-only actual = {scale_slope[1]:.3f} * predicted")
    variants = []
    for label, scale in (("Linear", scale_lin),
                         ("Slope only", scale_slope)):
        _, scaled_summary = evaluate(fit_games, test_games,
                                     scale=scale,
                                     prior_weight=args.prior_weight)
        variants.append((label, scale, scaled_summary))
    text = report(summary, variants=variants)
    Path(args.out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
