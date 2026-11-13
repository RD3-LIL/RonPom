"""Score live predictions after the games finish.

Reads every data/predictions_*.csv file, matches each row to
its final score in data/games_2026_27.json by (date, home,
away), and appends the scored rows to
data/prediction_scores.csv. A prediction is scored once and
never overwritten: the prediction file, margin, win
probability, and market line are the forecast as made, the
actual margin is the outcome. Re-running is safe, it only
adds games that have finished since the last run.

Why this matters: the historical backtests (fit 2024-25,
predict 2025-26) say how the model would have done. This
log says how it is doing now, on the current season, with
the current ratings. Same metrics as the backtests, so the
live numbers can be judged against the same baseline:
accuracy 66.9%, Brier 0.2105, log loss 0.6081 for win/loss,
and the market beating the model on spread MAE. A small
live sample is noisy, so every metric is reported with its
game count, and no conclusion is drawn from a handful of
games.

Metrics per scored row:
  correct_pick: model win prob > 0.5 matches the home winner.
  brier: (prob - home_won)^2. logloss: -log(prob or 1-prob).
  model_abs_err: |predicted home margin - actual|.
  market_abs_err: |implied market home margin - actual|,
    when a market line was in the predictions file.
  edge_cover: 1 when the actual margin lands on the model's
    side of the market line, 0 when it lands the other way,
    blank when there is no market line or no edge.
  trap_dog_covers / trap_dog_wins: only for trap games, the
    underdog covering the market line and winning outright.

Usage:
    python3 score_predictions.py [--out data/prediction_scores.csv]
    python3 score_predictions.py --report comparisons/live_predictions_scorecard.md
"""

import argparse
import csv
import glob
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
GAMES_FILE = DATA / "games_2026_27.json"
SCORES_FILE = DATA / "prediction_scores.csv"
REPORT_FILE = HERE / "comparisons" / "live_predictions_scorecard.md"

SCORE_FIELDS = [
    "prediction_file", "prediction_date", "game_date", "tipoff",
    "home", "away", "home_short", "away_short", "neutral_site",
    "margin", "spread", "home_win_prob", "market_spread", "edge",
    "trap", "trap_score", "trap_flags", "trap_favorite",
    "home_score", "away_score", "actual_home_margin", "home_won",
    "correct_pick", "brier", "logloss", "model_abs_err",
    "market_abs_err", "edge_cover", "trap_dog_covers",
    "trap_dog_wins",
]
BASELINE = {"accuracy": 0.669, "brier": 0.2105, "logloss": 0.6081}
BREAKEVEN = 0.524


def _float(row, key):
    v = row.get(key)
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _bool_str(v):
    return "True" if v else "False"


def prediction_date_from_filename(path):
    """YYYYMMDD from predictions_YYYY_MM_DD.csv, or the stem."""
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", Path(path).name)
    if m:
        return "".join(m.groups())
    return Path(path).stem


def load_games():
    games = json.loads(GAMES_FILE.read_text())
    index = {}
    for g in games:
        if g.get("home_score") == 0 and g.get("away_score") == 0:
            continue
        index[(g["date"], g["home"], g["away"])] = g
    return index


def score_row(pred, pred_file, pred_date, game):
    """One scored row, or None if the game has not finished."""
    margin = _float(pred, "margin")
    prob = _float(pred, "home_win_prob")
    if margin is None or prob is None:
        return None
    actual = game["home_score"] - game["away_score"]
    home_won = 1 if actual > 0 else 0
    correct = 1 if (prob > 0.5) == bool(home_won) else 0
    brier = (prob - home_won) ** 2
    logloss = -math.log(max(1e-9, prob if home_won else 1 - prob))
    market = _float(pred, "market_spread")
    edge = _float(pred, "edge")
    market_abs = None
    edge_cover = None
    if market is not None:
        implied = -market
        market_abs = abs(implied - actual)
        if edge is not None and edge != 0:
            edge_cover = 1 if (actual - implied) * edge > 0 else 0
    is_trap = str(pred.get("trap", "")).strip() in ("True", "true", "1")
    trap_dog_covers = None
    trap_dog_wins = None
    if is_trap:
        fav = pred.get("trap_favorite") or (
            pred["home"] if margin > 0 else pred["away"])
        market_fav = None
        if market is not None:
            implied = -market
            market_fav = implied if fav == pred["home"] else -implied
        actual_fav = actual if fav == pred["home"] else -actual
        if market_fav is not None:
            trap_dog_covers = 1 if actual_fav < market_fav else 0
        trap_dog_wins = 1 if actual_fav < 0 else 0
    return {
        "prediction_file": pred_file,
        "prediction_date": pred_date,
        "game_date": pred.get("date", ""),
        "tipoff": pred.get("tipoff", ""),
        "home": pred.get("home", ""),
        "away": pred.get("away", ""),
        "home_short": pred.get("home_short", ""),
        "away_short": pred.get("away_short", ""),
        "neutral_site": pred.get("neutral_site", ""),
        "margin": pred.get("margin", ""),
        "spread": pred.get("spread", ""),
        "home_win_prob": pred.get("home_win_prob", ""),
        "market_spread": pred.get("market_spread", ""),
        "edge": pred.get("edge", ""),
        "trap": _bool_str(is_trap),
        "trap_score": pred.get("trap_score", ""),
        "trap_flags": pred.get("trap_flags", ""),
        "trap_favorite": pred.get("trap_favorite", ""),
        "home_score": game["home_score"],
        "away_score": game["away_score"],
        "actual_home_margin": actual,
        "home_won": home_won,
        "correct_pick": correct,
        "brier": f"{brier:.4f}",
        "logloss": f"{logloss:.4f}",
        "model_abs_err": f"{abs(margin - actual):.2f}",
        "market_abs_err": (f"{market_abs:.2f}"
                           if market_abs is not None else ""),
        "edge_cover": ("" if edge_cover is None else edge_cover),
        "trap_dog_covers": ("" if trap_dog_covers is None
                            else trap_dog_covers),
        "trap_dog_wins": ("" if trap_dog_wins is None
                          else trap_dog_wins),
    }


def _mean(rows, key):
    vals = [float(r[key]) for r in rows if r.get(key) not in (None, "")]
    return sum(vals) / len(vals) if vals else None


def _rate(rows, key):
    vals = [int(r[key]) for r in rows if r.get(key) not in (None, "")]
    if not vals:
        return None, 0
    return sum(vals) / len(vals), len(vals)


def summarize(rows):
    """Summary dict with a count beside every metric."""
    n = len(rows)
    out = {"n": n}
    if not n:
        return out
    out["accuracy"], _ = _rate(rows, "correct_pick")
    out["brier"] = _mean(rows, "brier")
    out["logloss"] = _mean(rows, "logloss")
    out["model_mae"] = _mean(rows, "model_abs_err")
    market_rows = [r for r in rows if r.get("market_abs_err") != ""]
    out["market_mae"] = _mean(market_rows, "market_abs_err")
    out["n_market"] = len(market_rows)
    out["edge_cover"] = {}
    for t in (2.0, 3.0, 5.0):
        sub = [r for r in rows
               if r.get("edge") not in (None, "")
               and abs(float(r["edge"])) >= t
               and r.get("edge_cover") != ""]
        rate, cnt = _rate(sub, "edge_cover")
        out["edge_cover"][t] = {"n": cnt, "rate": rate}
    traps = [r for r in rows if r.get("trap") == "True"]
    out["n_trap"] = len(traps)
    out["trap_dog_cover"], _ = _rate(traps, "trap_dog_covers")
    out["trap_dog_win"], _ = _rate(traps, "trap_dog_wins")
    return out


def _pct(x):
    return f"{x:.1%}" if x is not None else "-"


def report_text(summary, n_new):
    s = summary
    lines = []
    lines.append("# Live predictions scorecard")
    lines.append("")
    lines.append(f"Scored {s['n']} live predictions so far. "
                 f"Each row is one "
                 f"forecast from a dated predictions file, matched "
                 f"to its final score after the game. Predictions "
                 f"are never overwritten, so this log only grows.")
    lines.append("")
    if not s["n"]:
        lines.append("No games have finished yet.")
        lines.append("")
        return "\n".join(lines) + "\n"
    lines.append("## Headline (live, vs the 2025-26 backtest baseline)")
    lines.append("")
    lines.append("| Metric | Live | Backtest baseline |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| Accuracy | {_pct(s['accuracy'])} "
                 f"(n={s['n']}) | "
                 f"{BASELINE['accuracy']:.1%} |")
    lines.append(f"| Brier | {s['brier']:.4f} | "
                 f"{BASELINE['brier']:.4f} |")
    lines.append(f"| Log loss | {s['logloss']:.4f} | "
                 f"{BASELINE['logloss']:.4f} |")
    lines.append(f"| Spread MAE, model | {s['model_mae']:.2f} | - |")
    lines.append(f"| Spread MAE, market | {s['market_mae']:.2f} "
                 f"(n={s['n_market']}) | - |")
    lines.append("")
    lines.append("## Edge cover (does disagreeing with the market pay?)")
    lines.append("")
    lines.append("| Min disagreement | Games | Model cover rate |")
    lines.append("| --- | --- | --- |")
    for t, c in s["edge_cover"].items():
        lines.append(f"| {t:.0f} pts | {c['n']} | "
                     f"{_pct(c['rate'])} |")
    lines.append("")
    lines.append(f"Breakeven at -110 is {BREAKEVEN:.1%}.")
    lines.append("")
    lines.append("## Trap games")
    lines.append("")
    lines.append(f"{s['n_trap']} trap games scored. Underdog cover "
                 f"{_pct(s['trap_dog_cover'])}, underdog win "
                 f"{_pct(s['trap_dog_win'])}.")
    lines.append("")
    lines.append("## Read")
    lines.append("")
    if s["n"] < 100:
        lines.append(f"Only {s['n']} games scored so far. Do not "
                     "draw a conclusion from this sample, it is a "
                     "log being built, not a verdict. The numbers "
                     "above are the running tally, and they will "
                     "move a lot until the sample is in the "
                     "hundreds.")
    elif s["accuracy"] is not None and s["accuracy"] < 0.60:
        lines.append("Accuracy is below 60% on a real sample. That "
                     "would be a flag to investigate, not a tweak "
                     "to make on the spot: check calibration first, "
                     "then whether the misses cluster in one kind "
                     "of game.")
    else:
        lines.append("Live accuracy is in line with the backtest "
                     "so far. Keep collecting, the value is in the "
                     "trend over hundreds of games, not in any one "
                     "night.")
    lines.append("")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(SCORES_FILE))
    parser.add_argument("--report", default=str(REPORT_FILE))
    args = parser.parse_args()
    out_path = Path(args.out)
    existing = []
    seen = set()
    if out_path.exists():
        with open(out_path, newline="") as f:
            existing = list(csv.DictReader(f))
        for r in existing:
            seen.add((r["prediction_file"], r["game_date"],
                      r["home"], r["away"]))
    games = load_games()
    print(f"Games in file: {len(games)} finished")
    new_rows = []
    for path in sorted(glob.glob(str(DATA / "predictions_*.csv"))):
        pred_file = Path(path).name
        pred_date = prediction_date_from_filename(path)
        with open(path, newline="") as f:
            preds = list(csv.DictReader(f))
        scored_here = 0
        for p in preds:
            key = (pred_file, p.get("date", ""), p.get("home", ""),
                   p.get("away", ""))
            if key in seen:
                continue
            game = games.get((p.get("date", ""), p.get("home", ""),
                              p.get("away", "")))
            if game is None:
                continue
            row = score_row(p, pred_file, pred_date, game)
            if row is None:
                continue
            new_rows.append(row)
            seen.add(key)
            scored_here += 1
        print(f"{pred_file}: {len(preds)} predictions, "
              f"{scored_here} newly scored")
    all_rows = existing + new_rows
    all_rows.sort(key=lambda r: (r["prediction_date"], r["game_date"],
                                 r["home"], r["away"]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SCORE_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    summary = summarize(all_rows)
    print(f"Total scored: {summary['n']} "
          f"({len(new_rows)} new)")
    if summary["n"]:
        print(f"Accuracy {_pct(summary['accuracy'])}, "
              f"Brier {summary['brier']:.4f}, "
              f"model MAE {summary['model_mae']:.2f}, "
              f"market MAE {summary['market_mae']:.2f} "
              f"(n={summary['n_market']})")
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text(summary, len(new_rows)))
        print(f"Wrote {report_path}")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
