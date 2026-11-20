"""Cap experiments that spread_backtest.py cannot run: the
per-possession cap (spread_backtest.py has no flag for it) and
the live 2026-27 effect of each cap on the snapshot ratings.

Win/loss backtests for the caps live in backtest.py
(--blowout-cap, --margin-cap-per-poss); this script covers
the spread MAE side for the per-possession cap and the live
snapshot effect, both of which need a custom solve.

Usage:
    python3 cap_experiment.py
        Prints spread MAE (fit 2024-25, test 2025-26, market
        games only) for no cap, cap 20, cap 15, and per-poss
        0.30, then the live snapshot top-5 under each cap.
"""

import json, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from solver import solve  # noqa: E402
from backtest import played_d1, load_games  # noqa: E402
from predict import predict_margin  # noqa: E402
from spread_backtest import with_spread  # noqa: E402


def spread_mae(margin_cap=None, margin_cap_per_poss=None):
    fit = played_d1(load_games("2024-25"))
    test = with_spread(load_games("2025-26"))
    ratings, lo, lt, info = solve(
        fit, prior_weight=300.0, margin_cap=margin_cap,
        margin_cap_per_poss=margin_cap_per_poss, return_info=True)
    errs = []
    for g in test:
        pred = predict_margin(ratings, lo, lt, g)
        errs.append(abs(pred - (g["home_score"] - g["away_score"])))
    return sum(errs) / len(errs), len(errs), info


def live_top5(margin_cap=None, margin_cap_per_poss=None):
    games = json.load(open("/tmp/ronpom-solver-snapshot/games_2026_27.json"))
    prior = json.load(open("/tmp/ronpom-solver-snapshot/prior_2026_27.json"))
    teams, lo, lt, info = solve(
        games, prior=prior, margin_cap=margin_cap,
        margin_cap_per_poss=margin_cap_per_poss, return_info=True)
    ranked = sorted(teams.items(), key=lambda kv: kv[1]["net"],
                    reverse=True)
    top = {n: t["net"] for n, t in ranked}
    return top, info


def main():
    print("Spread MAE, fit 2024-25, test 2025-26 (market games):")
    for label, kw in (("no cap", {}),
                      ("cap 20", {"margin_cap": 20}),
                      ("cap 15", {"margin_cap": 15}),
                      ("per-poss 0.30", {"margin_cap_per_poss": 0.30})):
        mae, n, info = spread_mae(**kw)
        print(f"  {label:<14} MAE {mae:.2f} on {n} games "
              f"(fit {info['n_games']} games, {info['n_teams']} teams)")
    print("Live snapshot top 5 Net under each cap (no cap is live):")
    for label, kw in (("no cap", {}),
                      ("cap 20", {"margin_cap": 20}),
                      ("cap 15", {"margin_cap": 15}),
                      ("per-poss 0.30", {"margin_cap_per_poss": 0.30})):
        top, info = live_top5(**kw)
        names = ["Illinois Fighting Illini", "Duke Blue Devils",
                 "Houston Cougars", "Michigan Wolverines",
                 "St. John's Red Storm"]
        vals = ", ".join(f"{n.split()[0]} {top[n]:.1f}" for n in names)
        print(f"  {label:<14} {vals}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
