"""Backtest the trap detector: fit 2024-25, test 2025-26.

Same discipline as spread_backtest.py: ratings are frozen
from the fit season only, the test season is run once, and
the trap thresholds were locked in trap.py before this run.
History for each test game uses only test-season games
played before that game's date, so no lookahead.

Metrics, all on test games with a market spread:
  underdog cover vs the market: the actual favorite margin
  is smaller than the market favorite margin.
  underdog outright win: the underdog wins the game.
Both are reported for trap games, for gap-only games
(MARKET_GAP present but not a trap), and for all games,
so a trap result can be judged against its own base rate.
Breakeven for a cover bet at -110 is 52.4%.

Usage:
    python3 trap_backtest.py [--out comparisons/trap_backtest_2025_26.md]
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
from trap import build_history, flags_for_game, rank_map  # noqa: E402

FIT_SEASON = "2024-25"
TEST_SEASON = "2025-26"
BREAKEVEN = 0.524


def _rate(rows, fn):
    if not rows:
        return None
    return sum(1 for r in rows if fn(r)) / len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", default="comparisons/trap_backtest_2025_26.md")
    args = parser.parse_args()
    fit_games = played_d1(load_games(FIT_SEASON))
    test_games = [g for g in played_d1(load_games(TEST_SEASON))
                  if g.get("spread") is not None]
    test_games.sort(key=lambda g: (g["date"], g["event_id"]))
    print(f"Fit: {FIT_SEASON}, {len(fit_games)} games")
    print(f"Test: {TEST_SEASON}, {len(test_games)} games with a spread")
    ratings, league_o, league_t, info = solve(
        fit_games, prior_weight=300.0, return_info=True)
    print(f"Ratings: {info['n_teams']} teams, league OffEff "
          f"{league_o:.1f}, tempo {league_t:.1f}")
    ranks = rank_map(ratings)
    history = build_history(test_games, ranks)
    rows = []
    for g in test_games:
        pred = predict_margin(ratings, league_o, league_t, g)
        implied = -float(g["spread"])
        actual = g["home_score"] - g["away_score"]
        flags = flags_for_game(g, pred, float(g["spread"]),
                               ranks, history)
        if flags["favorite"] is None:
            continue
        fav = flags["favorite"]
        market_fav = implied if fav == g["home"] else -implied
        actual_fav = actual if fav == g["home"] else -actual
        rows.append({
            "date": g["date"], "home": g["home"], "away": g["away"],
            "favorite": fav, "underdog": flags["underdog"],
            "pred": pred, "implied": implied, "actual": actual,
            "market_fav": market_fav, "actual_fav": actual_fav,
            "flags": flags["flags"], "score": flags["score"],
            "trap": flags["trap"],
            "dog_covers": actual_fav < market_fav,
            "dog_wins": actual_fav < 0,
        })
    trap = [r for r in rows if r["trap"]]
    gap_only = [r for r in rows
                if "MARKET_GAP" in r["flags"] and not r["trap"]]
    gap_all = [r for r in rows if "MARKET_GAP" in r["flags"]]
    print(f"Scored {len(rows)} games with a clear favorite")
    print(f"Trap games: {len(trap)}")
    print(f"Gap-only games: {len(gap_only)}")
    for label, sub in (("All", rows), ("Trap", trap),
                       ("Gap only", gap_only), ("Gap all", gap_all)):
        print(f"{label}: n={len(sub)} dog cover="
              f"{_rate(sub, lambda r: r['dog_covers'])} "
              f"dog win={_rate(sub, lambda r: r['dog_wins'])}")

    def pct(x):
        return f"{x:.1%}" if x is not None else "-"

    lines = []
    lines.append(f"# Trap backtest: fit {FIT_SEASON}, test {TEST_SEASON}")
    lines.append("")
    lines.append(f"Fit on {len(fit_games)} {FIT_SEASON} games "
                 f"(league-average prior, prior weight 300), "
                 f"{info['n_teams']} teams. Scored on {len(rows)} "
                 f"{TEST_SEASON} games with a market spread and a "
                 f"clear favorite (|model margin| >= 2). Trap "
                 f"thresholds were locked in trap.py before this "
                 f"run: MARKET_GAP required, total flags >= 3. "
                 f"History uses only games played before each "
                 f"game's date.")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("| Group | Games | Underdog covers market | "
                 "Underdog wins outright |")
    lines.append("| --- | --- | --- | --- |")
    for label, sub in (("All games", rows), ("Trap", trap),
                       ("Gap only", gap_only), ("Gap all", gap_all)):
        lines.append(f"| {label} | {len(sub)} | "
                     f"{pct(_rate(sub, lambda r: r['dog_covers']))} | "
                     f"{pct(_rate(sub, lambda r: r['dog_wins']))} |")
    lines.append("")
    lines.append(f"Breakeven for a cover bet at -110 is "
                 f"{BREAKEVEN:.1%}. Underdog cover is the actual "
                 f"favorite margin falling short of the market "
                 f"favorite margin.")
    lines.append("")
    lines.append("## Read")
    lines.append("")
    trap_cover = _rate(trap, lambda r: r["dog_covers"])
    all_cover = _rate(rows, lambda r: r["dog_covers"])
    if trap and trap_cover is not None and trap_cover > BREAKEVEN:
        lines.append(f"Trap games cover at {trap_cover:.1%} "
                     f"({len(trap)} games), above the "
                     f"{BREAKEVEN:.1%} breakeven and above the "
                     f"{all_cover:.1%} all-game rate. That is a "
                     f"signal worth watching, but the sample is "
                     f"small and the thresholds were set before "
                     f"the run, not tuned to it.")
    elif trap and trap_cover is not None:
        lines.append(f"Trap games cover at {trap_cover:.1%} "
                     f"({len(trap)} games), against "
                     f"{all_cover:.1%} for all games and a "
                     f"{BREAKEVEN:.1%} breakeven. That is no "
                     f"signal: the flags describe letdown "
                     f"context, they do not beat the market. "
                     f"The trap section stays on the page as a "
                     f"watch list, what is weird, not a pick, "
                     f"and the spread magnitudes stay "
                     f"unbacktested.")
    else:
        lines.append("No trap games in the test season, so the "
                     "trap rate cannot be scored. The detector "
                     "stays on the page as a watch list only.")
    lines.append("")
    lines.append("## Flag counts (test season)")
    lines.append("")
    for flag in ("TOP25", "BIG_WIN", "BUSY", "SHORT_REST",
                 "ROAD_FAV", "MARKET_GAP"):
        n = sum(1 for r in rows if flag in r["flags"])
        lines.append(f"- {flag}: {n} games")
    lines.append("")
    lines.append("## Trap games in the test season")
    lines.append("")
    if trap:
        lines.append("| Date | Favorite | Underdog | Flags | "
                     "Dog covered? | Dog won? |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for r in trap[:50]:
            lines.append(f"| {r['date']} | {r['favorite']} | "
                         f"{r['underdog']} | "
                         f"{', '.join(r['flags'])} | "
                         f"{'yes' if r['dog_covers'] else 'no'} | "
                         f"{'yes' if r['dog_wins'] else 'no'} |")
        if len(trap) > 50:
            lines.append(f"({len(trap) - 50} more trap games, "
                         f"not listed)")
    else:
        lines.append("None.")
    lines.append("")
    text = "\n".join(lines)
    Path(args.out).write_text(text)
    print(text)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
