"""Compare our 2026-27 solver ratings to KenPom's public top 25.

The KenPom list below was recorded by hand from the public front
page of kenpom.com, which is visible without a subscription, as
rubric.md allows. No scraping, no paywall, no login, no full
table. Date and source are recorded with the numbers, because an
undated rho is meaningless.

Metrics (rubric.md): Spearman rho on his top 25, overlap at 10
and 25, mean absolute rank difference, Illinois spot check, and
the 5 biggest disagreements with one line each. Net values are
NOT compared: our Net and his Net live on different scales.

Usage:
    python3 compare_kenpom.py
    python3 compare_kenpom.py --out comparisons/2026-11-10.md
"""

import argparse
import csv
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"

# Recorded by hand from https://kenpom.com/ public front page,
# Nov 10, 2026 (page as crawled 22:28 UTC / 4:28 PM CST that day).
# Season 2026-27, teams at 2-0 / 3-0. Our data is through Nov 9.
KENPOM_DATE = "2026-11-10"
KENPOM_SOURCE = "kenpom.com public front page, top 25, recorded by hand"
KENPOM_TOP_25 = [
    "Duke", "Florida", "Houston", "Illinois", "Kansas",
    "Michigan St.", "Vanderbilt", "Texas", "Connecticut", "Virginia",
    "Gonzaga", "Alabama", "Arizona", "Iowa St.", "Nebraska",
    "UCLA", "Texas Tech", "Louisville", "St. John's", "Auburn",
    "BYU", "Miami FL", "Tennessee", "Texas A&M", "Missouri",
]

# KenPom short name -> our ESPN display name.
NAME_MAP = {
    "Duke": "Duke Blue Devils",
    "Florida": "Florida Gators",
    "Houston": "Houston Cougars",
    "Illinois": "Illinois Fighting Illini",
    "Kansas": "Kansas Jayhawks",
    "Michigan St.": "Michigan State Spartans",
    "Vanderbilt": "Vanderbilt Commodores",
    "Texas": "Texas Longhorns",
    "Connecticut": "UConn Huskies",
    "Virginia": "Virginia Cavaliers",
    "Gonzaga": "Gonzaga Bulldogs",
    "Alabama": "Alabama Crimson Tide",
    "Arizona": "Arizona Wildcats",
    "Iowa St.": "Iowa State Cyclones",
    "Nebraska": "Nebraska Cornhuskers",
    "UCLA": "UCLA Bruins",
    "Texas Tech": "Texas Tech Red Raiders",
    "Louisville": "Louisville Cardinals",
    "St. John's": "St. John's Red Storm",
    "Auburn": "Auburn Tigers",
    "BYU": "BYU Cougars",
    "Miami FL": "Miami Hurricanes",
    "Tennessee": "Tennessee Volunteers",
    "Texas A&M": "Texas A&M Aggies",
    "Missouri": "Missouri Tigers",
}


def load_ours(season="2026-27"):
    path = DATA / f"ratings_{season.replace('-', '_')}.csv"
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return {r["team"]: int(r["rank"]) for r in rows}, rows


def spearman(pairs):
    """Spearman rho from (his_rank, our_rank) pairs. Stdlib only."""
    n = len(pairs)
    d2 = sum((h - o) ** 2 for h, o in pairs)
    return 1 - 6 * d2 / (n * (n ** 2 - 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    ours, rows = load_ours()
    pairs = []
    missing = []
    for i, name in enumerate(KENPOM_TOP_25, 1):
        full = NAME_MAP[name]
        if full not in ours:
            missing.append(name)
            continue
        pairs.append((name, i, ours[full]))
    if missing:
        print(f"WARNING: not in our ratings: {missing}")

    # Spearman needs both lists ranked 1..n on the SAME 25 teams.
    # His rank already is 1..25; ours is a rank out of 358, so
    # re-rank our 25 by our full rank before computing rho. Using
    # full ranks directly in the formula gives nonsense (rho outside
    # -1..1), because the two scales differ. The table below still
    # shows our full rank, and the mean absolute difference uses
    # full ranks, as the rubric defines it.
    by_ours = sorted(pairs, key=lambda p: p[2])
    subrank = {name: i + 1 for i, (name, _, _) in enumerate(by_ours)}
    rho = spearman([(h, subrank[name]) for name, h, _ in pairs])
    overlap_10 = sum(1 for _, h, o in pairs if h <= 10 and o <= 10)
    overlap_25 = sum(1 for _, h, o in pairs if o <= 25)
    mad = sum(abs(h - o) for _, h, o in pairs) / len(pairs)
    ill = next((h, o) for n, h, o in pairs if n == "Illinois")
    disagreements = sorted(pairs, key=lambda p: abs(p[1] - p[2]),
                           reverse=True)[:5]

    lines = []
    lines.append(f"# KenPom comparison, {KENPOM_DATE}")
    lines.append("")
    lines.append(f"Source: {KENPOM_SOURCE}. Our ratings: solver v2 on "
                 f"2026-27 through Nov 11, 2026 (590 D1 games, 2-3 per "
                 f"team, transfer-aware preseason prior: 2025-26 final "
                 f"ratings faded by returning plus transfer minutes). "
                 f"His table is the Nov 10 top 25, so the game sets "
                 f"differ by a day and his list has moved since.")
    lines.append("")
    lines.append("## Metrics (rank-based only, per rubric.md)")
    lines.append("")
    lines.append(f"- Spearman rho, top 25: **{rho:.3f}** "
                 f"(target above 0.7; n = {len(pairs)}; rho is computed "
                 f"on both lists re-ranked 1..25 on the same 25 teams, "
                 f"since our full rank runs to 358)")
    lines.append(f"- Overlap at 10: **{overlap_10} of 10** "
                 f"(his top 10 that are in our top 10)")
    lines.append(f"- Overlap at 25: **{overlap_25} of 25** "
                 f"(target at least 18)")
    lines.append(f"- Mean absolute rank difference: **{mad:.1f}** ranks")
    lines.append(f"- Illinois: his rank {ill[0]}, our rank {ill[1]} "
                 f"(target within 10 ranks)")
    lines.append("")
    lines.append("## His top 25 vs ours")
    lines.append("")
    lines.append("| KenPom | Team | Our rank | Diff |")
    lines.append("| --- | --- | --- | --- |")
    for name, h, o in pairs:
        lines.append(f"| {h} | {name} | {o} | {o - h:+d} |")
    lines.append("")
    lines.append("## Biggest disagreements")
    lines.append("")
    # Hand-written for this snapshot; re-check the ranks and shares
    # if this script is re-run on a later date.
    reasons = {
        "Arizona": "1-1: lost 75-84 at UCLA, then beat Cal Poly 104-84. "
                   "Their prior is middling (returning 0.30, transfer "
                   "0.36, prior Net +8.9, weight 223), so one early "
                   "loss still drops them to 50th in ours; his prior "
                   "keeps them 13th.",
        "Iowa St.": "1-1: lost 76-80 at home to Memphis, then beat "
                    "Southern Miss 83-57. Their prior is strong now "
                    "(returning 0.48, transfer 0.50, prior Net +15.0, "
                    "weight 296), but the home loss still puts them "
                    "34th in ours, 14th in his.",
        "Miami FL": "2-1: lost 67-77 at Florida, then beat Wagner and "
                    "North Florida. The loss plus a thin 2-game sample "
                    "puts them 40th in ours, 22nd in his.",
        "Tennessee": "Returning 0.22, transfer 0.75, so their prior "
                     "is strong now (prior Net +9.5, weight 293), but "
                     "their 2 games still leave them 46th in ours, "
                     "23rd in his.",
        "Texas Tech": "Returning 0.26, transfer 0.59, prior Net +8.6, "
                      "weight 266. A middling prior plus 2-3 games of "
                      "data: ours 33rd, his 17th.",
    }
    for name, h, o in disagreements:
        lines.append(f"- **{name}**: his {h}, ours {o}. "
                     f"{reasons.get(name, 'Early-season noise: 2 games '
                                    'on our side, a prior on his.')}")
    lines.append("")
    lines.append("## Read")
    lines.append("")
    if rho < 0.7:
        lines.append("Below the 0.7 rho target, as the rubric expects in "
                     "week one. The prior keeps moving it: with the "
                     "league-average prior rho was 0.342, overlap at "
                     "25 was 12 of 25, and mean rank difference was 21.9. "
                     "With the returning-only prior those are 0.542, 15 "
                     "of 25, and 14.8. With the transfer-aware prior "
                     "(returning plus transfer minutes) they are 0.592, "
                     "15 of 25, and 11.7. LSU is the clearest win: "
                     "our No. 1 at Net +34.7 on three blowouts with a "
                     "zero returning share, now No. 5 at Net +26.5, "
                     "still above his ~27th but no longer the artifact. "
                     "The remaining gap is mostly 2-3 games of data per "
                     "team: the gap should keep closing as games "
                     "accumulate. If it has not closed by mid-season on "
                     "a full game log, the solver or the prior is wrong.")
    else:
        lines.append("Above the 0.7 rho target.")
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        out = HERE / args.out
        out.parent.mkdir(exist_ok=True)
        out.write_text(text)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
