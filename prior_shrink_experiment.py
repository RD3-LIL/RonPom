"""Validate the prior value shrink out of sample, before adopting.

Design: build 2025-26 priors from the 2024-25 final ratings
(league OffEff 107.0, tempo 67.9), three variants: the adopted
noshrink value, the value shrink (deviation times
0.25 + 0.75 * info), and the guard (info below 0.25 gets the
league-average value with has_prior False). Then rolling
origin on 2025-26: at each cutoff date, solve the games
played so far with each prior and predict the next 7 days of
games. Same logistic for all three (a=0.150, b=0.148, the
2024-25 crossfit), same home court (predict_margin, 4.69,
none on neutral floors), so the only difference is the prior.
Pooled accuracy, Brier, log loss, and spread MAE decide.

Also reports the live 2026-27 snapshot effect of the shrink
on the top 10, for the record, not as the decision.

Usage:
    python3 prior_shrink_experiment.py
"""

import json, math, sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from build_prior_2026 import (  # noqa: E402
    build_prior_noshrink, load_last_ratings, load_profiles)
from solver import solve, is_d1_game  # noqa: E402
from predict import predict_margin  # noqa: E402
from backtest import win_prob  # noqa: E402

LEAGUE_O_2024_25 = 107.0
LEAGUE_T_2024_25 = 67.9
CUTOFFS = ["20251110", "20251117", "20251124", "20251201"]
LOGISTIC_A, LOGISTIC_B = 0.150, 0.148
GUARD_INFO = 0.25


def guard_variant(prior, league_o, league_t):
    """Copy of a prior with low-info teams reset to league
    average, has_prior False. Weight is left as built."""
    out = {}
    for team, v in prior.items():
        v = dict(v)
        info = 0.0
        if v.get("returning_share") is not None:
            info = (v["returning_share"] or 0.0) + \
                (v["transfer_share"] or 0.0)
        if v.get("has_prior") and info < GUARD_INFO:
            v["prior_o"] = league_o
            v["prior_d"] = league_o
            v["prior_t"] = league_t
            v["has_prior"] = False
            v["reason"] = (f"guard: info {info:.2f} below "
                           f"{GUARD_INFO}, league average")
        out[team] = v
    return out


def played(games):
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


def score_preds(rows):
    n = len(rows)
    acc = sum(1 for _, y, p, _ in rows if (p > 0.5) == bool(y)) / n
    brier = sum((p - y) ** 2 for _, y, p, _ in rows) / n
    ll = sum(-math.log(max(1e-9, p if y else 1 - p))
             for _, y, p, _ in rows) / n
    mae = sum(abs(m - a) for m, _, _, a in rows) / n
    return n, acc, brier, ll, mae


def main():
    last = load_last_ratings("2024-25")
    pl = load_profiles("2024-25")
    pt = load_profiles("2025-26")
    base = build_prior_noshrink(last, pl, pt,
                                league_o=LEAGUE_O_2024_25,
                                league_t=LEAGUE_T_2024_25)
    shrunk = build_prior_noshrink(last, pl, pt,
                                  league_o=LEAGUE_O_2024_25,
                                  league_t=LEAGUE_T_2024_25,
                                  value_shrink=True)
    guarded = guard_variant(base, LEAGUE_O_2024_25, LEAGUE_T_2024_25)
    variants = {"noshrink (adopted)": base,
                "value shrink": shrunk,
                f"guard info<{GUARD_INFO}": guarded}
    for label, pr in variants.items():
        n_low = sum(1 for v in pr.values()
                    if v.get("has_prior") is False)
        print(f"{label}: {len(pr)} teams, "
              f"{n_low} with has_prior False")

    games = played(json.loads(
        (HERE / "data" / "games_2025_26.json").read_text()))
    results = {label: [] for label in variants}
    for cutoff in CUTOFFS:
        nxt = (datetime.strptime(cutoff, "%Y%m%d")
               + timedelta(days=7)).strftime("%Y%m%d")
        train = [g for g in games if g["date"] <= cutoff]
        test = [g for g in games if cutoff < g["date"] <= nxt]
        for label, pr in variants.items():
            teams, lo, lt, info = solve(train, prior=pr,
                                        return_info=True)
            for g in test:
                m = predict_margin(teams, lo, lt, g)
                p = win_prob(m, LOGISTIC_A, LOGISTIC_B)
                y = 1 if g["home_score"] > g["away_score"] else 0
                results[label].append(
                    (m, y, p, g["home_score"] - g["away_score"]))
        print(f"cutoff {cutoff}: {len(train)} train games, "
              f"{len(test)} test games")
    print("Pooled next-7-days predictions (4 cutoffs):")
    for label in variants:
        n, acc, brier, ll, mae = score_preds(results[label])
        print(f"  {label:<22} n={n} acc {acc:.3f} Brier {brier:.4f} "
              f"logloss {ll:.4f} spread MAE {mae:.2f}")

    # Live snapshot effect of the shrink on 2026-27.
    last26 = load_last_ratings("2025-26")
    pl26 = load_profiles("2025-26")
    pt26 = load_profiles("2026-27")
    live_base = build_prior_noshrink(last26, pl26, pt26)
    live_shrunk = build_prior_noshrink(last26, pl26, pt26,
                                       value_shrink=True)
    sgames = json.load(open(
        "/tmp/ronpom-solver-snapshot/games_2026_27.json"))
    print("Live snapshot prior Net (noshrink vs value shrink):")
    for t in ["Illinois Fighting Illini", "Duke Blue Devils",
              "Houston Cougars", "Michigan Wolverines",
              "St. John's Red Storm"]:
        b = live_base[t]
        s = live_shrunk[t]
        print(f"  {t}: {b['prior_o'] - b['prior_d']:.1f} -> "
              f"{s['prior_o'] - s['prior_d']:.1f} "
              f"(info {(b['returning_share'] + b['transfer_share']):.3f})")
    print("Live snapshot top 10 Net under value shrink:")
    teams, lo, lt, info = solve(sgames, prior=live_shrunk,
                                return_info=True)
    ranked = sorted(teams.items(), key=lambda kv: kv[1]["net"],
                    reverse=True)
    for r, (n, t) in enumerate(ranked[:10], 1):
        print(f"  {r:>2} {n:<32} Net {t['net']:>6.1f} "
              f"AdjO {t['adj_o']:>6.1f} AdjD {t['adj_d']:>6.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
