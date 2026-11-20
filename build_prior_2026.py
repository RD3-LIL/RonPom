"""Build the real 2026-27 preseason prior from 2025-26 ratings.

ADOPTED Nov 14, 2026 (comparisons/mend_2026-11-14.md, Ron's
pick: "whatever you think is best"): the no-shrink own-team
prior, base weight 600 possessions.

For each team, the prior VALUE is its own 2025-26 rating,
regressed 0.85 toward the league average:

    prior_o = L_o + 0.85 * (own_last_o - L_o)
    prior_d = L_o + 0.85 * (own_last_d - L_o)

The prior WEIGHT still scales with the informed share
(returning + transfer minutes, from the player profiles):

    prior_weight = 600 * (0.25 + 0.75 * informed_share)

so a rebuilt team gets a weaker anchor, but the anchor value
is the program's own last rating, not a minutes average.

Why this replaced the transfer-blended prior: the old prior
was a minutes-weighted average of the SOURCE teams' ratings,
so a star transfer from a weak team dragged the prior down,
freshmen with no profile counted as league average, and then
the whole thing was faded again by informed share times 0.85.
Arizona was +33.9 last season but its old prior was only
+9.3, with prior defense 104.6 against its own last-season
91.8. That is what put Arizona 35th, Iowa State 40th,
Alabama 39th, and Texas Tech 37th against KenPom's 9th,
15th, 17th, and 16th. The no-shrink prior puts those teams
at 10th, 17th, 21st, and 24th, with KenPom rho 0.779 on
Nov 14 (0.893 on the Nov 10 list) and mean rank gap 4.5,
and it also improved rolling-origin prediction (Brier
-0.0061, accuracy 0.731 to 0.750, spread MAE 10.70 to
10.13 on 308 pooled game-slots, though the Brier CI
includes zero, so the prediction gain is promising, not
confirmed). The old transfer-blended builder is kept below
as build_transfer_prior for reference; main() no longer
calls it. Re-check this prior when the season finishes:
if a genuinely rebuilt team is badly misrated, revisit it.

Known limit, unchanged: DNP players are excluded from the
profiles, so a returning or transfer player who has not
appeared yet in 2026-27 is missed and the shares read low.
With 2-3 games played that is mostly deep-bench players,
but it is a real undercount, not a guess. Minutes weights
are this season's minutes, the best measure of who is
actually on the floor now.

League averages are the 2025-26 solver run's values (league
OffEff 109.3, tempo 68.2), not the mean of the ratings CSV.

Usage:
    python3 build_prior_2026.py
        Writes data/prior_2026_27.json and prints a summary.
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"

LEAGUE_O_2025_26 = 109.3
LEAGUE_T_2025_26 = 68.2
REGRESSION = 0.85
TEMPO_REGRESSION = 0.70
BASE_PRIOR_WEIGHT = 600.0  # adopted Nov 14, 2026, was 300.0


def load_profiles(season):
    path = DATA / f"players_{season.replace('-', '_')}.json"
    return json.loads(path.read_text())["players"]


def build_transfer_prior(last_ratings, profiles_last, profiles_this,
                         league_o=LEAGUE_O_2025_26,
                         league_t=LEAGUE_T_2025_26):
    """Transfer-aware prior, same shape as prior.build_prior output.

    last_ratings: team -> {"adj_o", "adj_d", "adj_t"} from the
    prior season. profiles_last / profiles_this: player profile
    dicts with athlete_id, team, and totals.min. A player
    contributes this season's minutes, weighted by the
    last-season rating of the team he played for (own team for
    a returner, old team for a transfer, league average for a
    player with no prior-season profile). Teams with no current
    roster get the league average with has_prior False.
    """
    last_team = {}
    for p in profiles_last:
        last_team[p["athlete_id"]] = p["team"]
    # This season's minutes by team, split by source.
    teams = {}
    for p in profiles_this:
        team = p["team"]
        mins = float(p["totals"]["min"])
        entry = teams.setdefault(team, {"total": 0.0, "ret": 0.0,
                                        "tr": 0.0, "o": 0.0,
                                        "d": 0.0, "t": 0.0})
        entry["total"] += mins
        src = last_team.get(p["athlete_id"])
        if src is None:
            src_o, src_d, src_t = league_o, league_o, league_t
        elif src == team:
            entry["ret"] += mins
            src_o, src_d, src_t = _rating(last_ratings, team,
                                          league_o, league_t)
        else:
            entry["tr"] += mins
            src_o, src_d, src_t = _rating(last_ratings, src,
                                          league_o, league_t)
        entry["o"] += mins * src_o
        entry["d"] += mins * src_d
        entry["t"] += mins * src_t
    prior = {}
    for team in set(last_ratings) | set(teams):
        entry = teams.get(team)
        if entry is None or entry["total"] <= 0:
            prior[team] = {
                "prior_o": league_o, "prior_d": league_o,
                "prior_t": league_t, "returning_share": None,
                "transfer_share": None, "has_prior": False,
                "prior_weight": BASE_PRIOR_WEIGHT * 0.5,
                "reason": "no current roster in profiles, "
                          "league average",
            }
            continue
        total = entry["total"]
        ret_share = entry["ret"] / total
        tr_share = entry["tr"] / total
        info = ret_share + tr_share
        blended_o = entry["o"] / total
        blended_d = entry["d"] / total
        blended_t = entry["t"] / total
        prior[team] = {
            "prior_o": league_o + info * REGRESSION * (blended_o - league_o),
            "prior_d": league_o + info * REGRESSION * (blended_d - league_o),
            "prior_t": league_t + info * TEMPO_REGRESSION * (blended_t - league_t),
            "returning_share": round(ret_share, 4),
            "transfer_share": round(tr_share, 4),
            "has_prior": info > 0,
            "prior_weight": BASE_PRIOR_WEIGHT * (0.25 + 0.75 * info),
            "reason": (f"returning share {ret_share:.2f}, "
                       f"transfer share {tr_share:.2f}"),
        }
    return prior


def _rating(last_ratings, team, league_o, league_t):
    """A team's last-season rating, or league average if unrated."""
    r = last_ratings.get(team)
    if r is None:
        return league_o, league_o, league_t
    return float(r["adj_o"]), float(r["adj_d"]), float(r["adj_t"])


def load_last_ratings(season="2025-26"):
    path = DATA / f"ratings_{season.replace('-', '_')}.csv"
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return {r["team"]: {"adj_o": float(r["adj_o"]),
                        "adj_d": float(r["adj_d"]),
                        "adj_t": float(r["adj_t"])} for r in rows}


def build_prior_noshrink(last_ratings, profiles_last, profiles_this,
                         league_o=LEAGUE_O_2025_26,
                         league_t=LEAGUE_T_2025_26,
                         value_shrink=False):
    """Adopted prior (Nov 14, 2026): no-shrink own-team value.

    Prior value: the team's own last-season rating, regressed
    0.85 toward the league average. No minutes fade on the
    value, so freshmen and transfers do not drag it toward
    league average or toward a weak source team.
    Prior weight: BASE_PRIOR_WEIGHT * (0.25 + 0.75 * info),
    where info is the returning + transfer minutes share from
    the profiles, so a rebuilt team still gets a weaker anchor.
    Teams with no last-season rating get the league average.
    Returns the same shape as build_transfer_prior.

    value_shrink (default False, the adopted behavior): when
    True, the prior VALUE is also faded toward the league
    average when info is low, mirroring the weight factor:
    the deviation multiplier becomes 0.85 * (0.25 + 0.75 *
    info) for offense/defense and 0.70 * (0.25 + 0.75 * info)
    for tempo, so a team with info 1.0 is unchanged and a
    team with info 0.0 keeps only a quarter of its deviation.
    This is the Nov 20, 2026 experiment: it is NOT adopted
    yet, because the Nov 14 decision deliberately removed the
    value fade (the old transfer prior faded the value twice,
    by info and by 0.85), and a value fade needs its own
    out-of-sample win first. Info is measured from this
    season's minutes played to date, split by whether the
    player has a last-season profile (returning or transfer)
    or not (new). Minutes to date is the honest measure of
    who is actually on the floor now; full roster membership
    would count deep-bench players who never play and
    overstate how much of last season's team is really back.
    The known undercount (DNP players excluded from the
    profiles) still applies and reads info low, never high.
    """
    last_team = {}
    for p in profiles_last:
        last_team[p["athlete_id"]] = p["team"]
    info_share = {}
    for p in profiles_this:
        team = p["team"]
        mins = float(p["totals"]["min"])
        src = last_team.get(p["athlete_id"])
        entry = info_share.setdefault(team, {"total": 0.0, "info": 0.0,
                                             "ret": 0.0, "tr": 0.0})
        entry["total"] += mins
        if src is None:
            continue
        entry["info"] += mins
        if src == team:
            entry["ret"] += mins
        else:
            entry["tr"] += mins
    prior = {}
    for team in set(last_ratings) | set(info_share):
        entry = info_share.get(team)
        total = entry["total"] if entry else 0.0
        if total <= 0:
            prior[team] = {
                "prior_o": league_o, "prior_d": league_o,
                "prior_t": league_t, "returning_share": None,
                "transfer_share": None, "has_prior": False,
                "prior_weight": BASE_PRIOR_WEIGHT * 0.5,
                "reason": "no current roster in profiles, "
                          "league average",
            }
            continue
        ret_share = entry["ret"] / total
        tr_share = entry["tr"] / total
        info = ret_share + tr_share
        own = last_ratings.get(team)
        if own is None:
            prior[team] = {
                "prior_o": league_o, "prior_d": league_o,
                "prior_t": league_t,
                "returning_share": round(ret_share, 4),
                "transfer_share": round(tr_share, 4),
                "has_prior": False,
                "prior_weight": BASE_PRIOR_WEIGHT * (0.25 + 0.75 * info),
                "reason": "no last season rating, league average",
            }
            continue
        # Value shrink (experiment only, off by default): fade
        # the deviation toward league average when info is low.
        shrink = (0.25 + 0.75 * info) if value_shrink else 1.0
        prior[team] = {
            "prior_o": league_o + REGRESSION * shrink * (float(own["adj_o"]) - league_o),
            "prior_d": league_o + REGRESSION * shrink * (float(own["adj_d"]) - league_o),
            "prior_t": league_t + TEMPO_REGRESSION * shrink * (float(own["adj_t"]) - league_t),
            "returning_share": round(ret_share, 4),
            "transfer_share": round(tr_share, 4),
            "has_prior": True,
            "prior_weight": BASE_PRIOR_WEIGHT * (0.25 + 0.75 * info),
            "reason": (f"noshrink own-team prior, Nov 14 2026: "
                       f"returning share {ret_share:.2f}, "
                       f"transfer share {tr_share:.2f}"),
        }
    return prior


def main():
    profiles_last = load_profiles("2025-26")
    profiles_this = load_profiles("2026-27")
    last_ratings = load_last_ratings("2025-26")
    prior = build_prior_noshrink(
        last_ratings, profiles_last, profiles_this,
        league_o=LEAGUE_O_2025_26, league_t=LEAGUE_T_2025_26)
    out = DATA / "prior_2026_27.json"
    out.write_text(json.dumps(prior, indent=1))
    with_prior = [v for v in prior.values() if v["has_prior"]]
    shares = [v["returning_share"] + v["transfer_share"]
              for v in with_prior
              if v["returning_share"] is not None]
    print(f"Wrote {out.name}: {len(prior)} teams, "
          f"{len(with_prior)} with a real prior, "
          f"mean informed share {sum(shares) / len(shares):.2f}, "
          f"min {min(shares):.2f}, max {max(shares):.2f}")
    for team in ["Illinois Fighting Illini", "Duke Blue Devils",
                 "Arizona Wildcats", "Iowa State Cyclones",
                 "Florida Gators", "Houston Cougars",
                 "LSU Tigers", "Texas Longhorns"]:
        p = prior.get(team)
        if p:
            print(f"  {team}: returning {p['returning_share']}, "
                  f"transfer {p['transfer_share']}, "
                  f"prior AdjO {p['prior_o']:.1f}, "
                  f"AdjD {p['prior_d']:.1f}, weight {p['prior_weight']:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
