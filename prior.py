"""
Preseason prior for the KenPom-like ratings (solver v2).

Why a prior exists at all
--------------------------
Early in the season every team has 1-2 games. A rating built
only from those games is mostly noise: a 40-point blowout of a
bad team looks like a top-10 team, and a loss to a team that has
only played you looks like you played a great team. KenPom
handles this with a preseason prior built from last season,
and the prior fades as games accumulate. This module is our
version of that idea, with the formula written down so it can
be argued with.

Exact formula
-------------
For a team with last season's adjusted ratings (last_o, last_d,
last_t), league averages (L_o, L_t), returning-minutes share r
in [0, 1], and regression constants a (offense/defense) and
a_t (tempo):

    prior_o = L_o + r * a * (last_o - L_o)
    prior_d = L_o + r * a * (last_d - L_o)
    prior_t = L_t + r * a_t * (last_t - L_t)

Defaults: a = 0.85, a_t = 0.70. Those constants are chosen, not
estimated: even a team that returns everyone regresses a bit
toward the league (seniors leave, freshmen arrive, luck evens
out), and tempo regresses more because it is partly a coaching
choice that changes year to year. If you disagree with 0.85,
pass a different value; the formula stays the same.

The returning share r is the fraction of last season's minutes
played by players who are back this season. r = 1 means the
whole rotation returns, so the prior is almost last season's
rating. r = 0 means nobody returns, so the prior is exactly
the league average. r = 0.5 means half the signal survives.

Prior weight (how much the prior counts in the solver) is
separate from the prior value, and it is per team:

    prior_weight = base_weight * (0.25 + 0.75 * r)

with base_weight = 300 possessions by default (about 4.3 games).
A team with full returners gets the full 300, a team with no
returners gets 75, which is still an anchor but a weak one.
The solver reads "prior_weight" from each entry, so a prior
built here plugs straight into solver.solve().

What happens when data is missing
----------------------------------
- Team in last season's ratings but no returning-minutes data:
  the prior is the league average, has_prior is False, and the
  reason is recorded. We do NOT guess r. If you want to use
  last season's rating without minutes data, pass
  minutes_unknown_shrink explicitly (for example 0.5), which
  applies that shrink in place of r and is labeled as a
  placeholder choice, not a measured value.
- Team not in last season's ratings at all: league average,
  has_prior False. New teams, reclassified teams, and teams
  with no prior season in the input all land here.
- No last season ratings at all (empty input): build_prior
  returns an empty dict, and the solver falls back to a
  league-average prior for every team. That is the graceful
  degradation path, and it is what solver v2 uses today on
  the prototype, because no prior season has been pulled yet.
- League averages: if league_o / league_t are not passed, they
  are the mean of the last season ratings when those exist,
  otherwise the fallbacks below. The fallbacks are typical
  modern D1 values, not measured from this data set, and they
  should be replaced with the real league averages whenever
  those are known.

Roster and minutes join (placeholder, not invented data)
---------------------------------------------------------
The real returning share comes from joining last season's
roster minutes to this season's roster. That join is NOT built
here, because the full roster pull has not landed yet
(fetch_rosters.py is being run separately). compute_returning_
share() and build_prior_from_rosters() define the exact input
shape that join must produce, so the real data can be plugged
in without changing the formula:

    player = {"name": ..., "minutes": <last season minutes>,
              "returning": True/False}

or {"minutes_last": ..., "returning": ...}. No returning
minutes data is invented anywhere in this module: every path
that lacks minutes data says so in the "reason" field.

Usage:
    from prior import build_prior
    prior = build_prior(last_ratings, returning_minutes)
    teams, lo, lt = solve(games, prior=prior)
"""

# Fallbacks, used only when no league average can be computed.
# Typical modern D1 values, not measured from this data set.
LEAGUE_O_FALLBACK = 104.0
LEAGUE_T_FALLBACK = 70.0

# Regression toward the league, even for full returners.
REGRESSION = 0.85
TEMPO_REGRESSION = 0.70

BASE_PRIOR_WEIGHT = 300.0  # possessions, same default as solver.py


def _pick(entry, *keys):
    """First present, non-None value among keys, else None."""
    if not isinstance(entry, dict):
        return None
    for k in keys:
        if k in entry and entry[k] is not None:
            return entry[k]
    return None


def _normalize_rating(entry):
    """Last-season rating entry -> (adj_o, adj_d, adj_t) or None.

    Accepts the ratings.py keys (adj_o, adj_d, adj_t), the
    CamelCase keys (AdjO, AdjD, AdjT), and the prior keys
    (prior_o, prior_d, prior_t). A team needs at least an
    offense and a defense value to count as having a prior.
    Tempo falls back to the league average when missing.
    """
    if not isinstance(entry, dict):
        return None
    adj_o = _pick(entry, "adj_o", "AdjO", "prior_o", "off", "offense")
    adj_d = _pick(entry, "adj_d", "AdjD", "prior_d", "def", "defense")
    adj_t = _pick(entry, "adj_t", "AdjT", "prior_t", "tempo")
    if adj_o is None or adj_d is None:
        return None
    return float(adj_o), float(adj_d), (None if adj_t is None else float(adj_t))


def _normalize_share(value):
    """Returning-minutes input -> share in [0, 1], or None.

    Accepts a plain float, or a dict with one of:
      {"returning_share": x}, {"share": x}, {"fraction": x},
      {"returning_minutes": r, "total_minutes": t} (ratio r/t),
      {"returning": r, "total": t}.
    Returns None when the input is missing or unparseable, so
    the caller can degrade to league average instead of guessing.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, dict):
        share = _pick(value, "returning_share", "share", "fraction")
        if share is not None:
            return max(0.0, min(1.0, float(share)))
        ret = _pick(value, "returning_minutes", "returning")
        tot = _pick(value, "total_minutes", "total")
        if ret is not None and tot is not None and float(tot) > 0:
            return max(0.0, min(1.0, float(ret) / float(tot)))
    return None


def compute_returning_share(players):
    """Returning-minutes share from a roster list, or None.

    players: list of dicts, each with last season minutes and a
    returning flag, for example:
        {"name": "A", "minutes": 1200, "returning": True}
        {"name": "B", "minutes": 800, "returning": False}
    Accepts "minutes_last" in place of "minutes". Returns the
    returning minutes divided by total minutes, or None when
    the list is empty or total minutes are zero. This is the
    function the real roster join should call once the full
    roster pull lands; it invents no players and no minutes.
    """
    if not players:
        return None
    total = 0.0
    returning = 0.0
    for p in players:
        if not isinstance(p, dict):
            continue
        minutes = _pick(p, "minutes", "minutes_last", "min")
        if minutes is None:
            continue
        minutes = float(minutes)
        total += minutes
        if p.get("returning") is True:
            returning += minutes
    if total <= 0:
        return None
    return returning / total


def league_average_prior(teams, league_o=None, league_t=None,
                         prior_weight=BASE_PRIOR_WEIGHT):
    """League-average priors for a list of teams.

    The explicit fallback used when no prior data exists at all.
    Every team gets the league average, has_prior False, and the
    reason recorded, so downstream code can tell a real prior
    from a placeholder.
    """
    lo = LEAGUE_O_FALLBACK if league_o is None else float(league_o)
    lt = LEAGUE_T_FALLBACK if league_t is None else float(league_t)
    return {
        team: {"prior_o": lo, "prior_d": lo, "prior_t": lt,
               "returning_share": None, "has_prior": False,
               "prior_weight": float(prior_weight),
               "reason": "no prior data, league average"}
        for team in teams
    }


def build_prior(last_season_ratings, returning_minutes=None,
                league_o=None, league_t=None,
                regression=REGRESSION, tempo_regression=TEMPO_REGRESSION,
                base_prior_weight=BASE_PRIOR_WEIGHT,
                minutes_unknown_shrink=None):
    """Build a preseason prior from last season's ratings.

    last_season_ratings: dict team -> rating entry (see
        _normalize_rating). Empty or None means no prior data:
        returns {} and the solver falls back to league average.
    returning_minutes: optional dict team -> share (float 0..1)
        or dict (see _normalize_share). Teams missing from it
        are treated as having no minutes data, not as r = 0.
    league_o, league_t: league averages for the prior season.
        When omitted, the mean of last season's ratings is used,
        else the module fallbacks (104.0 / 70.0).
    regression, tempo_regression: shrink constants, see the
        module docstring. Pass 1.0 to turn regression off.
    base_prior_weight: prior strength in possessions, before
        the per-team (0.25 + 0.75 * r) scaling.
    minutes_unknown_shrink: optional explicit placeholder. When
        set (for example 0.5), teams with a last season rating
        but no minutes data use that value in place of r, and
        the reason says so. When None (default), those teams
        get the league average and has_prior False.

    Returns dict team -> {"prior_o", "prior_d", "prior_t",
        "returning_share", "has_prior", "prior_weight", "reason"}.
    """
    if not last_season_ratings:
        return {}
    ratings = {}
    for team, entry in last_season_ratings.items():
        norm = _normalize_rating(entry)
        if norm is not None:
            ratings[team] = norm
    if not ratings:
        return {}

    if league_o is None:
        league_o = sum(v[0] for v in ratings.values()) / len(ratings)
    if league_t is None:
        known_tempo = [v[2] for v in ratings.values() if v[2] is not None]
        league_t = (sum(known_tempo) / len(known_tempo)
                    if known_tempo else LEAGUE_T_FALLBACK)
    league_o = float(league_o)
    league_t = float(league_t)

    prior = {}
    for team, (last_o, last_d, last_t) in ratings.items():
        if last_t is None:
            last_t = league_t
        share = None
        if returning_minutes is not None and team in returning_minutes:
            share = _normalize_share(returning_minutes[team])
        if share is None and minutes_unknown_shrink is not None:
            prior_o = league_o + minutes_unknown_shrink * regression * (last_o - league_o)
            prior_d = league_o + minutes_unknown_shrink * regression * (last_d - league_o)
            prior_t = league_t + minutes_unknown_shrink * tempo_regression * (last_t - league_t)
            prior[team] = {
                "prior_o": prior_o, "prior_d": prior_d, "prior_t": prior_t,
                "returning_share": None, "has_prior": True,
                "prior_weight": base_prior_weight * 0.5,
                "reason": ("no returning-minutes data, using explicit "
                           f"minutes_unknown_shrink={minutes_unknown_shrink}, "
                           "not a measured value"),
            }
        elif share is None:
            prior[team] = {
                "prior_o": league_o, "prior_d": league_o, "prior_t": league_t,
                "returning_share": None, "has_prior": False,
                "prior_weight": base_prior_weight * 0.5,
                "reason": "no returning-minutes data, league average",
            }
        else:
            prior_o = league_o + share * regression * (last_o - league_o)
            prior_d = league_o + share * regression * (last_d - league_o)
            prior_t = league_t + share * tempo_regression * (last_t - league_t)
            prior[team] = {
                "prior_o": prior_o, "prior_d": prior_d, "prior_t": prior_t,
                "returning_share": share, "has_prior": share > 0,
                "prior_weight": base_prior_weight * (0.25 + 0.75 * share),
                "reason": f"returning share {share:.2f}",
            }

    # Teams with minutes data but no last season rating: league average.
    if returning_minutes:
        for team in returning_minutes:
            if team not in prior:
                share = _normalize_share(returning_minutes[team])
                prior[team] = {
                    "prior_o": league_o, "prior_d": league_o,
                    "prior_t": league_t, "returning_share": share,
                    "has_prior": False,
                    "prior_weight": base_prior_weight * 0.5,
                    "reason": "no last season rating, league average",
                }
    return prior


def build_prior_from_rosters(last_season_ratings, rosters_by_team,
                             **kwargs):
    """Build a prior from rosters: the join point for real data.

    rosters_by_team: dict team -> list of player dicts, each with
        last season minutes and a returning flag (see
        compute_returning_share). Teams missing from it get no
        minutes data, which build_prior handles as league average
        unless minutes_unknown_shrink is passed through kwargs.

    This function is a placeholder join, not a data source. It
    invents no rosters: when the full ESPN roster pull lands,
    wire its output to this function unchanged. Until then,
    callers should pass rosters only for teams whose rosters
    were actually pulled.
    """
    shares = {}
    for team, players in (rosters_by_team or {}).items():
        share = compute_returning_share(players)
        if share is not None:
            shares[team] = share
    return build_prior(last_season_ratings, returning_minutes=shares,
                       **kwargs)
