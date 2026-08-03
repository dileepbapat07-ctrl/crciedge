"""
simulator/match_simulator.py
==============================
Stage 1 — Minimal Monte Carlo match simulator.

Uses ONLY data already in player_engine.db (career avg, SR, bowling
economy, wicket rate, form score). No ball-by-ball history, no ESPN,
no odds API. Goal: team A vs team B -> win probability, from first
principles, using players we already have.

Approach:
  1. For each batter, derive a per-ball outcome distribution from
     their average + strike rate (+ form score adjustment).
  2. For each bowler, derive a per-ball wicket probability from their
     bowling average + economy (+ form score adjustment).
  3. Combine batter and bowler distributions per ball via a simple
     blend (both push the outcome toward their own tendency).
  4. Simulate innings ball-by-ball: batter rotates on wicket/over-end,
     bowler rotates by over, chase logic applies in 2nd innings.
  5. Run N simulations, aggregate into win probability + score dist.

This is deliberately simple -- Stage 2 will add venue/phase realism
once ball_by_ball.db has real historical rates to draw from.
"""

import sqlite3, os, random, math
from dataclasses import dataclass, field
from collections import defaultdict

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB     = os.path.join(ROOT, "db", "player_engine.db")


def _has_column(db_path: str, table: str, column: str) -> bool:
    """
    Check if a column exists in a table -- used to gracefully degrade
    when the deployed DB is an older version than the code (e.g.
    missing cricsheet_name after a schema upgrade), instead of a hard
    crash on every simulation.
    """
    try:
        conn = sqlite3.connect(db_path)
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        conn.close()
        return column in cols
    except Exception:
        return False

# -- League-average baselines (T20) -- used when a player has no stats --
LEAGUE_AVG_SR       = 128.0   # runs per 100 balls
LEAGUE_AVG_BAT_AVG  = 26.0    # runs per dismissal
LEAGUE_AVG_BOWL_ECON = 8.2    # runs per over
LEAGUE_AVG_BOWL_SR   = 22.0   # balls per wicket


@dataclass
class Batter:
    name: str
    avg: float
    sr: float
    form: float = 5.0          # 0-10, 5 = neutral
    position: int = 6
    batting_style: str = ""    # rhb / lhb
    cricsheet_name: str = ""   # e.g. "JJ Roy" -- for real matchup lookup

    def ball_outcome_weights(self) -> dict:
        """
        Return relative weights for {0,1,2,3,4,6,W} for one ball faced,
        derived from this batter's SR (attacking intent) and average
        (dismissal risk), adjusted by current form.
        """
        sr = self.sr or LEAGUE_AVG_SR
        avg = self.avg or LEAGUE_AVG_BAT_AVG
        form_mult = 0.85 + (self.form / 10.0) * 0.30   # 0.85-1.15 range

        # Higher SR -> more boundaries, fewer dots
        boundary_rate = min(0.28, (sr - 80) / 400 * form_mult) if sr > 80 else 0.03
        six_share     = min(0.45, sr / 350)              # of boundary balls, how many are 6s

        # Lower average -> higher effective dismissal risk per ball
        dismiss_p = min(0.06, (LEAGUE_AVG_BAT_AVG / max(avg, 8)) * 0.018 / form_mult)

        four_p = boundary_rate * (1 - six_share)
        six_p  = boundary_rate * six_share
        remaining = max(0.0, 1 - dismiss_p - four_p - six_p)

        # Split remaining across 0/1/2/3 -- weighted toward 0 and 1
        dot_p   = remaining * 0.46
        one_p   = remaining * 0.38
        two_p   = remaining * 0.13
        three_p = remaining * 0.03

        return {0: dot_p, 1: one_p, 2: two_p, 3: three_p, 4: four_p, 6: six_p, "W": dismiss_p}


@dataclass
class Bowler:
    name: str
    econ: float
    bowl_sr: float          # balls per wicket
    form: float = 5.0
    overs_bowled: int = 0
    max_overs: int = 4
    bowling_style: str = ""    # rf / lf / offbreak / legspin / sla
    cricsheet_name: str = ""   # e.g. "Rashid Khan" -- for real matchup lookup

    def wicket_pressure(self) -> float:
        """Return a multiplier (>1 = more wicket-taking than average)."""
        sr = self.bowl_sr or LEAGUE_AVG_BOWL_SR
        form_mult = 0.85 + (self.form / 10.0) * 0.30
        return (LEAGUE_AVG_BOWL_SR / max(sr, 6)) * form_mult

    def economy_pressure(self) -> float:
        """Return a multiplier (>1 = more economical than average, suppresses boundaries)."""
        econ = self.econ or LEAGUE_AVG_BOWL_ECON
        return LEAGUE_AVG_BOWL_ECON / max(econ, 4)


@dataclass
class TeamLineup:
    name: str
    batters: list       # list[Batter], in batting order
    bowlers: list        # list[Bowler], in bowling rotation order


@dataclass
class InningsResult:
    batting_team: str
    runs: int = 0
    wickets: int = 0
    balls_faced: int = 0
    batter_scores: dict = field(default_factory=dict)   # name -> runs
    bowler_figures: dict = field(default_factory=dict)  # name -> (overs, runs, wkts)


# -- Batting-style vs bowling-style matchup heuristic --------------
# Simplified, transparent heuristic based on standard cricket wisdom
# about which way the ball turns relative to the batter's stance.
# This is NOT derived from real matchup data (no ball-by-ball history
# yet) -- it's a small, clearly-labelled directional nudge, not a
# precision model. Values are modifiers on boundary probability;
# positive = easier for batter, negative = harder for batter.
MATCHUP_TABLE = {
    ("rhb", "offbreak"): -0.06,   # turns into RHB -- harder to free arms
    ("rhb", "legspin"):  +0.03,   # turns away from RHB -- slightly easier
    ("rhb", "sla"):      +0.04,   # left-arm orthodox turns away from RHB
    ("lhb", "offbreak"): +0.04,   # turns away from LHB -- slightly easier
    ("lhb", "legspin"):  -0.06,   # turns into LHB -- harder
    ("lhb", "sla"):      -0.04,   # turns into LHB -- harder
    ("rhb", "lf"):        -0.02,
    ("lhb", "rf"):        -0.02,
}

def matchup_modifier(batting_style: str, bowling_style: str) -> float:
    """Return a small boundary-probability modifier for this batter/bowler pairing."""
    return MATCHUP_TABLE.get((batting_style, bowling_style), 0.0)


# -- Real batter-vs-bowler matchup history (from ball_by_ball.db, ------
# -- pre-aggregated into player_engine.db's player_matchups table) ----
def build_matchup_cache(
    team_a: "TeamLineup", team_b: "TeamLineup", db_path: str = DB
) -> dict:
    """
    Precompute real head-to-head matchup effects for every batter/bowler
    pairing across both lineups, ONCE before simulation starts (not per
    ball -- this is the expensive DB lookup, done a fixed number of times).

    Returns {(batter_name, bowler_name): {"boundary_mult":.., "wicket_mult":.., "confidence":..}}
    Falls back to the style-based heuristic (confidence=0) when there's
    no real history or too small a sample (<6 balls) to trust.
    """
    cache = {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        all_batters = team_a.batters + team_b.batters
        all_bowlers = team_a.bowlers + team_b.bowlers

        for batter in all_batters:
            if not batter.cricsheet_name:
                continue
            for bowler in all_bowlers:
                if not bowler.cricsheet_name:
                    continue
                row = conn.execute("""
                    SELECT balls, runs, outs, fours, sixes, strike_rate
                    FROM player_matchups
                    WHERE batter_cricsheet=? AND bowler_cricsheet=?
                """, (batter.cricsheet_name, bowler.cricsheet_name)).fetchone()

                if not row or row["balls"] < 6:
                    continue  # not enough sample -- style heuristic will apply instead

                balls, runs, outs = row["balls"], row["runs"], row["outs"]
                m_sr = row["strike_rate"] or 0
                base_sr = batter.sr or LEAGUE_AVG_SR

                # Boundary multiplier: how this matchup's SR compares to the
                # batter's overall SR, scaled and capped to a sane range
                sr_ratio = (m_sr / base_sr) if base_sr > 0 else 1.0
                boundary_mult = 1.0 + max(-0.30, min(0.30, (sr_ratio - 1.0) * 0.6))

                # Wicket multiplier: dismissal rate in this matchup vs a
                # generic expected rate (roughly 1 wicket per 20-25 balls)
                expected_dismiss_rate = 1 / 22.0
                actual_dismiss_rate = outs / balls if balls else 0
                wicket_mult = 1.0 + max(-0.4, min(0.6,
                    (actual_dismiss_rate - expected_dismiss_rate) * 15))

                # Confidence scales with sample size, caps at 1.0 around 20+ balls
                confidence = min(1.0, balls / 20.0)

                cache[(batter.name, bowler.name)] = {
                    "boundary_mult": boundary_mult,
                    "wicket_mult": wicket_mult,
                    "confidence": confidence,
                    "balls": balls, "runs": runs, "outs": outs,
                }
        conn.close()
    except Exception:
        pass  # table may not exist yet -- silently fall back to heuristic

    return cache


def get_bowler_phase_profile(cricsheet_name: str, db_path: str) -> dict:
    """
    Query real historical phase distribution (powerplay/middle/death) for
    a bowler from the pre-aggregated bowler_phase_profile table (lives in
    player_engine.db -- the small, shippable DB -- NOT the 245MB raw
    ball_by_ball.db, which isn't deployed to production).

    Returns {"powerplay":pct,"middle":pct,"death":pct,"total_balls":n}
    or None if no data / table doesn't exist yet (older DB version).
    """
    if not cricsheet_name or not db_path:
        return None
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT powerplay_pct, middle_pct, death_pct, total_balls "
            "FROM bowler_phase_profile WHERE bowler_cricsheet=?",
            (cricsheet_name,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "powerplay": row[0], "middle": row[1], "death": row[2],
            "total_balls": row[3],
        }
    except Exception:
        return None  # table may not exist on an older/unmigrated DB


def build_realistic_bowling_sequence(
    bowlers: list, total_sets: int = 10, db_path: str = "",
) -> list:
    """
    Build a bowling sequence (one bowler per set) using REAL historical
    phase preferences (from the pre-aggregated bowler_phase_profile
    table) when available, falling back to a sensible default (pace
    early/late, spin middle) otherwise.

    total_sets: number of sets/overs in the innings (10 for Hundred, 20 for T20).
    """
    n_sets_pp    = max(1, round(total_sets * 0.2))   # powerplay ~ first 20%
    n_sets_death = max(1, round(total_sets * 0.3))   # death ~ last 30%

    profiles = {}
    for b in bowlers:
        prof = get_bowler_phase_profile(b.cricsheet_name, db_path) if b.cricsheet_name and db_path else None
        if not prof:
            if b.bowling_style in ("legspin", "offbreak", "sla"):
                prof = {"powerplay": 0.15, "middle": 0.65, "death": 0.20, "total_balls": 0}
            else:
                prof = {"powerplay": 0.35, "middle": 0.25, "death": 0.40, "total_balls": 0}
        profiles[b.name] = prof

    max_per_bowler = 2 if total_sets == 10 else 4
    usage = {b.name: 0 for b in bowlers}
    sequence = []

    for set_idx in range(total_sets):
        if set_idx < n_sets_pp:
            phase = "powerplay"
        elif set_idx >= total_sets - n_sets_death:
            phase = "death"
        else:
            phase = "middle"

        available = [b for b in bowlers if usage[b.name] < max_per_bowler]
        if not available:
            available = bowlers

        available.sort(key=lambda b: profiles[b.name][phase], reverse=True)
        chosen = available[0]
        sequence.append(chosen)
        usage[chosen.name] += 1

    return sequence



# -- Venue registry -- now backed by REAL first-innings scoring data ---
# Built from 672,014 real deliveries across 1,755 matches (parsed from
# Cricsheet). See db table `venue_scores` for the underlying stats
# (avg/median/std/min/max score, chase-win%, scoring tier -- all
# computed within-competition so Hundred/T20I/ODI aren't compared
# unfairly against each other's different ball counts).

# venue_id -> display name (kept for the dropdown; real stats come
# from the DB lookup below, not from a hardcoded number anymore)
VENUE_DISPLAY_NAMES = {
    "the-oval-london": "Kennington Oval, London",
    "lords-london": "Lord's, London",
    "old-trafford-manchester": "Old Trafford, Manchester",
    "edgbaston-birmingham": "Edgbaston, Birmingham",
    "headingley-leeds": "Headingley, Leeds",
    "sophia-gardens-cardiff": "Sophia Gardens, Cardiff",
    "the-rose-bowl-southampton": "The Rose Bowl, Southampton",
    "trent-bridge-nottingham": "Trent Bridge, Nottingham",
}

# League-baseline first-innings score to compute venue_scale against
# (Hundred competition average across all 8 grounds, from real data)
LEAGUE_BASELINE_100B_SCORE = 135.0


def get_venue_stats(venue_id: str, competition: str = "The Hundred", db_path: str = DB) -> dict:
    """
    Look up REAL venue scoring stats from the venue_scores table
    (built from actual ball-by-ball history). Falls back to league
    baseline (scale=1.0, no adjustment) if the venue isn't in the DB
    yet or has too small a sample.

    Returns {"name":, "avg_first_innings":, "median_first_innings":,
             "std_dev":, "matches":, "chase_win_pct":, "scoring_tier":,
             "venue_scale":}
    """
    display_name = VENUE_DISPLAY_NAMES.get(venue_id, venue_id)
    fallback = {
        "name": display_name, "avg_first_innings": None, "median_first_innings": None,
        "std_dev": None, "matches": 0, "chase_win_pct": None,
        "scoring_tier": "Unknown", "venue_scale": 1.0,
    }
    if not venue_id or not display_name:
        return fallback

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT * FROM venue_scores
            WHERE venue=? AND competition=? AND innings=1
        """, (display_name, competition)).fetchone()
        conn.close()

        if not row or row["matches"] < 5:
            return fallback

        venue_scale = round(row["avg_score"] / LEAGUE_BASELINE_100B_SCORE, 3)

        return {
            "name": display_name,
            "avg_first_innings": row["avg_score"],
            "median_first_innings": row["median_score"],
            "std_dev": row["std_dev"],
            "matches": row["matches"],
            "chase_win_pct": row["chase_win_pct"],
            "scoring_tier": row["scoring_tier"] or "Average",
            "venue_scale": venue_scale,
        }
    except Exception:
        return fallback


# Backward-compat: VENUE_STATS dict still available for UI dropdowns,
# now populated from real data on import rather than hand-typed.
def _build_venue_stats_dict(db_path: str = DB) -> dict:
    result = {}
    for vid in VENUE_DISPLAY_NAMES:
        v = get_venue_stats(vid, "The Hundred", db_path)
        result[vid] = {
            "name": v["name"],
            "avg_first_innings_100b": v["avg_first_innings"] or 135,
            "chase_win_pct": v["chase_win_pct"] or 50,
            "venue_scale": v["venue_scale"],
            "scoring_tier": v["scoring_tier"],
            "matches": v["matches"],
        }
    return result

try:
    VENUE_STATS = _build_venue_stats_dict()
except Exception:
    VENUE_STATS = {vid: {"name": name, "avg_first_innings_100b": 135,
                          "chase_win_pct": 50, "venue_scale": 1.0,
                          "scoring_tier": "Unknown", "matches": 0}
                   for vid, name in VENUE_DISPLAY_NAMES.items()}


def simulate_ball(
    batter: Batter, bowler: Bowler, rng: random.Random,
    venue_scale: float = 1.0,
    matchup_cache: dict = None,
) -> tuple:
    """
    Simulate one delivery. Returns (runs_scored, is_wicket).
    Blends batter's natural outcome distribution with bowler's pressure,
    the batting/bowling style matchup (fallback), REAL historical
    batter-vs-bowler matchup data (when available, via matchup_cache),
    and venue scoring scale.
    """
    weights = batter.ball_outcome_weights()

    wicket_mult = bowler.wicket_pressure()
    econ_mult   = bowler.economy_pressure()

    w = dict(weights)
    w["W"] = min(0.15, w["W"] * wicket_mult)
    w[4]   = w[4] / econ_mult
    w[6]   = w[6] / econ_mult

    # Batting-style vs bowling-style matchup nudge (fallback heuristic)
    style_mm = matchup_modifier(batter.batting_style, bowler.bowling_style)

    # Real historical matchup (takes over proportionally to confidence)
    real = (matchup_cache or {}).get((batter.name, bowler.name))
    if real:
        conf = real["confidence"]
        # Blend: confidence=1 -> fully real data; confidence=0 -> fully style heuristic
        boundary_boost = (real["boundary_mult"] - 1.0) * conf + style_mm * (1 - conf)
        wicket_boost = (real["wicket_mult"] - 1.0) * conf
    else:
        boundary_boost = style_mm
        wicket_boost = 0.0

    if boundary_boost != 0.0:
        boost = 1.0 + boundary_boost
        w[4] = max(0.0, w[4] * boost)
        w[6] = max(0.0, w[6] * boost)

    if wicket_boost != 0.0:
        w["W"] = min(0.20, max(0.0, w["W"] * (1.0 + wicket_boost)))

    # Venue scoring scale (pushes boundary rate toward venue's real average)
    if venue_scale != 1.0:
        w[4] = max(0.0, w[4] * venue_scale)
        w[6] = max(0.0, w[6] * venue_scale)

    # Redistribute the difference into dots/singles to keep probabilities sane
    total = sum(w.values())
    if total <= 0:
        return 0, False
    for k in w:
        w[k] = max(0.0, w[k] / total)

    outcomes = list(w.keys())
    probs    = list(w.values())
    choice = rng.choices(outcomes, weights=probs, k=1)[0]

    if choice == "W":
        return 0, True
    return choice, False


def simulate_innings(
    batting: TeamLineup,
    bowling: TeamLineup,
    total_balls: int,
    target: int = None,
    rng: random.Random = None,
    venue_scale: float = 1.0,
    matchup_cache: dict = None,
    db_path: str = "",
    bowling_sequence: list = None,
) -> InningsResult:
    rng = rng or random.Random()
    result = InningsResult(batting_team=batting.name)

    # Strike rotation: striker_idx / non_striker_idx point into batting.batters
    # (the fixed batting order). next_in tracks the next fresh batter to come
    # to the crease on a wicket -- independent of who's currently on strike.
    striker_idx = 0
    non_striker_idx = 1
    next_in = 2

    balls_in_over = 0
    balls_per_over = 10 if total_balls in (100,) else 6
    total_sets = total_balls // balls_per_over

    # Use a REAL phase-aware bowling sequence (who bowls when, based on
    # actual historical powerplay/middle/death tendencies) if provided,
    # or build one on the fly as a fallback for direct calls to this
    # function (run_monte_carlo normally precomputes and passes it in
    # once per match, not per-ball, for performance).
    if bowling_sequence is None and db_path:
        bowling_sequence = build_realistic_bowling_sequence(
            bowling.bowlers, total_sets=total_sets, db_path=db_path
        )

    if bowling_sequence:
        set_idx = 0
        current_bowler = bowling_sequence[0] if bowling_sequence else bowling.bowlers[0]
    else:
        # Fallback: original round-robin behaviour
        bowlers_available = [b for b in bowling.bowlers if b.max_overs > 0]
        if not bowlers_available:
            bowlers_available = bowling.bowlers[:5]
        bowler_idx = 0
        current_bowler = bowlers_available[0]

    while result.balls_faced < total_balls and result.wickets < 10:
        if striker_idx >= len(batting.batters):
            break  # ran out of batters

        batter = batting.batters[striker_idx]

        if balls_in_over == 0:
            if bowling_sequence:
                set_idx = result.balls_faced // balls_per_over
                if set_idx < len(bowling_sequence):
                    current_bowler = bowling_sequence[set_idx]
            else:
                attempts = 0
                while bowlers_available[bowler_idx % len(bowlers_available)].overs_bowled >= \
                      bowlers_available[bowler_idx % len(bowlers_available)].max_overs and attempts < len(bowlers_available):
                    bowler_idx += 1
                    attempts += 1
                current_bowler = bowlers_available[bowler_idx % len(bowlers_available)]

        runs, is_wicket = simulate_ball(batter, current_bowler, rng, venue_scale=venue_scale, matchup_cache=matchup_cache)

        result.balls_faced += 1
        balls_in_over += 1

        if is_wicket:
            result.wickets += 1
            result.batter_scores.setdefault(batter.name, 0)
            # New batter comes in at the striker's position
            if next_in < len(batting.batters):
                striker_idx = next_in
                next_in += 1
            else:
                striker_idx = len(batting.batters)  # no batters left -> loop will break
        else:
            result.runs += runs
            result.batter_scores[batter.name] = result.batter_scores.get(batter.name, 0) + runs
            # Odd runs -> batters cross, strike rotates mid-over
            if runs % 2 == 1:
                striker_idx, non_striker_idx = non_striker_idx, striker_idx

        bf = current_bowler.name
        ov, rn, wk = result.bowler_figures.get(bf, (0, 0, 0))
        result.bowler_figures[bf] = (ov, rn + runs, wk + (1 if is_wicket else 0))

        if balls_in_over >= balls_per_over:
            balls_in_over = 0
            current_bowler.overs_bowled += 1
            if not bowling_sequence:
                bowler_idx += 1
            # End of over -> ends change, non-striker becomes striker
            if striker_idx < len(batting.batters) and non_striker_idx < len(batting.batters):
                striker_idx, non_striker_idx = non_striker_idx, striker_idx

        # Chase logic -- stop if target reached
        if target is not None and result.runs >= target:
            break

    # finalize bowler overs count
    final_figures = {}
    for name, (ov, rn, wk) in result.bowler_figures.items():
        b = next((x for x in bowling.bowlers if x.name == name), None)
        actual_overs = b.overs_bowled if b else 0
        final_figures[name] = (actual_overs, rn, wk)
    result.bowler_figures = final_figures

    return result


def run_match(
    team_a: TeamLineup,
    team_b: TeamLineup,
    total_balls: int = 120,
    rng: random.Random = None,
    venue_scale: float = 1.0,
    matchup_cache: dict = None,
    team_a_bowling_seq: list = None,
    team_b_bowling_seq: list = None,
) -> dict:
    """Simulate one full match (2 innings). Returns result dict."""
    rng = rng or random.Random()

    # team_a bats first, bowled at by team_b's sequence; then team_b
    # chases, bowled at by team_a's sequence
    inn1 = simulate_innings(team_a, team_b, total_balls, rng=rng, venue_scale=venue_scale,
                             matchup_cache=matchup_cache, bowling_sequence=team_b_bowling_seq)
    target = inn1.runs + 1
    inn2 = simulate_innings(team_b, team_a, total_balls, target=target, rng=rng, venue_scale=venue_scale,
                             matchup_cache=matchup_cache, bowling_sequence=team_a_bowling_seq)

    if inn2.runs >= target:
        winner = team_b.name
        margin = f"{10 - inn2.wickets} wickets"
    elif inn2.runs < inn1.runs:
        winner = team_a.name
        margin = f"{inn1.runs - inn2.runs} runs"
    else:
        winner = "Tie"
        margin = ""

    return {
        "winner": winner, "margin": margin,
        "team_a_score": inn1.runs, "team_a_wickets": inn1.wickets,
        "team_b_score": inn2.runs, "team_b_wickets": inn2.wickets,
        "innings1": inn1, "innings2": inn2,
    }


def run_monte_carlo(
    team_a: TeamLineup,
    team_b: TeamLineup,
    total_balls: int = 120,
    n_sims: int = 2000,
    seed: int = 42,
    venue_id: str = "",
    use_real_matchups: bool = True,
    db_path: str = DB,
) -> dict:
    """
    Run N simulations, return aggregated win probability + score
    distributions for both teams. If venue_id matches an entry in
    VENUE_STATS, applies that venue's real scoring scale. If
    use_real_matchups, precomputes real batter-vs-bowler history from
    player_matchups (falls back to style heuristic per-pair as needed).
    """
    venue_info = get_venue_stats(venue_id, "The Hundred", db_path) if venue_id else {}
    venue_scale = venue_info.get("venue_scale", 1.0)

    matchup_cache = build_matchup_cache(team_a, team_b, db_path) if use_real_matchups else {}

    # Precompute REAL phase-aware bowling sequences ONCE (not per
    # simulation -- this is the expensive DB-backed step, same pattern
    # as matchup_cache above).
    balls_per_over = 10 if total_balls in (100,) else 6
    total_sets = total_balls // balls_per_over
    team_a_bowling_seq = build_realistic_bowling_sequence(team_a.bowlers, total_sets, db_path)
    team_b_bowling_seq = build_realistic_bowling_sequence(team_b.bowlers, total_sets, db_path)

    rng = random.Random(seed)
    a_wins = 0
    b_wins = 0
    ties = 0
    a_scores = []
    b_scores = []

    for i in range(n_sims):
        result = run_match(team_a, team_b, total_balls, rng=rng, venue_scale=venue_scale,
                            matchup_cache=matchup_cache,
                            team_a_bowling_seq=team_a_bowling_seq,
                            team_b_bowling_seq=team_b_bowling_seq)
        a_scores.append(result["team_a_score"])
        b_scores.append(result["team_b_score"])
        if result["winner"] == team_a.name:
            a_wins += 1
        elif result["winner"] == team_b.name:
            b_wins += 1
        else:
            ties += 1

        # reset bowler over counts between simulations
        for b in team_a.bowlers: b.overs_bowled = 0
        for b in team_b.bowlers: b.overs_bowled = 0

    a_scores.sort()
    b_scores.sort()

    def pct(lst, p):
        idx = int(len(lst) * p)
        return lst[min(idx, len(lst)-1)]

    return {
        "n_sims": n_sims,
        "team_a": team_a.name,
        "venue_id": venue_id,
        "venue_name": venue_info.get("name", ""),
        "venue_scale": venue_scale,
        "venue_scoring_tier": venue_info.get("scoring_tier", ""),
        "venue_real_avg": venue_info.get("avg_first_innings"),
        "venue_real_chase_pct": venue_info.get("chase_win_pct"),
        "venue_sample_matches": venue_info.get("matches", 0),
        "real_matchup_pairs": len(matchup_cache),
        "real_phase_bowlers": sum(1 for b in (team_a.bowlers + team_b.bowlers)
                                   if b.cricsheet_name and get_bowler_phase_profile(b.cricsheet_name, db_path)),
        "team_b": team_b.name,
        "team_a_win_pct": round(a_wins / n_sims * 100, 1),
        "team_b_win_pct": round(b_wins / n_sims * 100, 1),
        "tie_pct": round(ties / n_sims * 100, 1),
        "team_a_score_median": pct(a_scores, 0.5),
        "team_a_score_p10": pct(a_scores, 0.10),
        "team_a_score_p90": pct(a_scores, 0.90),
        "team_b_score_median": pct(b_scores, 0.5),
        "team_b_score_p10": pct(b_scores, 0.10),
        "team_b_score_p90": pct(b_scores, 0.90),
    }


# -- Build a TeamLineup from the player_engine.db --
def build_lineup_from_db(team_name: str, fmt: str = "T20", db_path: str = DB) -> TeamLineup:
    """
    Pull top players for a team/franchise from player_engine.db and
    build a TeamLineup ready for simulation. Uses batting_position for
    order and is_key_player + stats for selection when XI isn't confirmed.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    has_cs = _has_column(db_path, "players", "cricsheet_name")
    cs_col = "cricsheet_name" if has_cs else "NULL as cricsheet_name"

    rows = conn.execute(f"""
        SELECT name, batting_position, role, is_key_player, batting_style, bowling_style, {cs_col},
               t20_avg, t20_sr, t20_wkts, t20_bowl_avg, t20_bowl_econ, t20_bowl_sr
        FROM players
        WHERE current_franchise=? OR team=?
        ORDER BY is_key_player DESC, batting_position ASC
        LIMIT 11
    """, (team_name, team_name)).fetchall()
    conn.close()

    # Get form scores separately (may not exist for all)
    conn2 = sqlite3.connect(db_path)
    conn2.row_factory = sqlite3.Row
    form_map = {}
    for r in conn2.execute("""
        SELECT p.name, pf.form_score
        FROM players p JOIN player_form pf ON pf.player_id = p.player_id
        WHERE (p.current_franchise=? OR p.team=?) AND pf.format IN ('T20','T20I')
    """, (team_name, team_name)).fetchall():
        form_map[r["name"]] = r["form_score"]
    conn2.close()

    batters = []
    bowlers = []
    for i, r in enumerate(rows):
        pos = r["batting_position"] or (i + 1)
        form = form_map.get(r["name"], 5.0)

        batters.append(Batter(
            name=r["name"], avg=r["t20_avg"] or 0, sr=r["t20_sr"] or 0,
            form=form, position=pos, batting_style=r["batting_style"] or "",
            cricsheet_name=r["cricsheet_name"] or ""
        ))

        if r["role"] in ("bowl", "all") or r["bowling_style"]:
            bowlers.append(Bowler(
                name=r["name"],
                econ=r["t20_bowl_econ"] or 0,
                bowl_sr=r["t20_bowl_sr"] or 0,
                form=form,
                max_overs=4 if fmt != "100b" else 5,
                bowling_style=r["bowling_style"] or "",
                cricsheet_name=r["cricsheet_name"] or "",
            ))

    batters.sort(key=lambda b: b.position)

    # Ensure at least 5 bowling options (fill with part-timers if short)
    while len(bowlers) < 5 and len(bowlers) < len(batters):
        candidates = [b for b in batters if b.name not in [bo.name for bo in bowlers]]
        if not candidates:
            break
        c = candidates[-1]
        bowlers.append(Bowler(name=c.name, econ=LEAGUE_AVG_BOWL_ECON * 1.15,
                               bowl_sr=LEAGUE_AVG_BOWL_SR * 1.3, form=c.form, max_overs=2))

    return TeamLineup(name=team_name, batters=batters, bowlers=bowlers)


def parse_pasted_xi_text(raw_text: str, db_path: str = DB, max_players: int = 11) -> tuple:
    """
    Parse messy pasted text (e.g. copied straight from ESPNcricinfo) into
    a clean list of player names, by extracting candidate lines and
    keeping only the ones that fuzzy-match a real player in the DB.

    Handles:
      - Numbered lists ("1. Will Jacks", "1) Will Jacks", "1 Will Jacks")
      - Captain/keeper markers ("James Vince (c)", "Pooran (wk)", "Roy*")
      - Comma-separated names on one line
      - Trailing scorecard stats ("Will Jacks 32(24)", "Boult 2/24 (4)")
      - Boilerplate noise ("Playing XI", "Toss:", "Squad", team names,
        dates, "elected to bat" etc) -- these simply won't match any
        player and get silently dropped, not treated as an error

    Returns (ordered_list_of_matched_names, log: list[str])
    """
    import re
    from difflib import SequenceMatcher

    def _norm(s):
        return re.sub(r'\s+', ' ', s.lower()).strip()

    def _sim(a, b):
        return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

    def _last_name(s):
        parts = _norm(s).split()
        return parts[-1] if parts else ""

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    all_players = conn.execute("SELECT name, name_aliases FROM players").fetchall()
    conn.close()

    def match_player(candidate: str):
        best_name, best_score = None, 0.0
        cand_first_initial = candidate.strip()[0].upper() if candidate.strip() else ""
        for row in all_players:
            names_to_check = [row["name"]]
            if row["name_aliases"]:
                names_to_check += [a.strip() for a in row["name_aliases"].split(",")]
            for cand_db in names_to_check:
                if not cand_db:
                    continue
                if _norm(cand_db) == _norm(candidate):
                    return row["name"], 1.0
                # Surname-only match: require first-initial agreement too,
                # otherwise same-surname players (e.g. Tom Curran vs Sam
                # Curran) can collide and silently pick the wrong one.
                same_surname = _last_name(cand_db) == _last_name(candidate) and _last_name(cand_db)
                if same_surname:
                    db_first_initial = cand_db.strip()[0].upper() if cand_db.strip() else ""
                    score = 0.92 if db_first_initial == cand_first_initial else 0.60
                else:
                    score = _sim(cand_db, candidate)
                if score > best_score:
                    best_score, best_name = score, row["name"]
        return (best_name, best_score) if best_score >= 0.78 else (None, best_score)

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    if len(lines) <= 2 and "," in raw_text:
        lines = [l.strip() for l in raw_text.split(",") if l.strip()]

    log = []
    matched_names = []
    seen = set()

    for raw_line in lines:
        if len(matched_names) >= max_players:
            break

        cleaned = raw_line
        cleaned = re.sub(r'^\s*\d{1,2}[.)]?\s+', '', cleaned)
        cleaned = re.sub(r'\s*\([^)]*\)\s*', ' ', cleaned)
        cleaned = re.sub(r'[*†]', '', cleaned)
        cleaned = re.sub(r'\s+\d+/\d+.*$', '', cleaned)
        cleaned = re.sub(r'\s+\d+\s*$', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        if len(cleaned) < 3 or len(cleaned) > 40:
            continue
        if re.match(r'^\d+$', cleaned):
            continue
        if any(kw in cleaned.lower() for kw in
               ["playing xi", "squad", "toss", "elected", "scorecard",
                "innings", "report", "live score", "match ", "vs ", " v "]):
            continue

        name, score = match_player(cleaned)
        if name and name not in seen:
            matched_names.append(name)
            seen.add(name)
            log.append(f"✅ '{raw_line.strip()}' → {name} (match {score:.2f})")
        elif name and name in seen:
            log.append(f"⚠ '{raw_line.strip()}' → {name} (duplicate, skipped)")
        else:
            log.append(f"— '{raw_line.strip()}' → no match, discarded as noise")

    return matched_names, log


def build_lineup_from_xi(
    team_name: str,
    player_names: list,
    db_path: str = DB,
    fmt: str = "T20",
) -> tuple:
    """
    Build a TeamLineup from an EXPLICIT list of 11 player names (the
    actual confirmed playing XI), in batting order as given.

    Each name is fuzzy-matched against player_engine.db (using name +
    name_aliases, same convention as fetch_playingxi.py). Players not
    found in the DB get league-average stats so the simulation can
    still run, but are flagged in the returned match log.

    Returns (TeamLineup, match_log: list[str])
    """
    from difflib import SequenceMatcher
    import re

    def _norm(s):
        return re.sub(r'\s+', ' ', s.lower()).strip()

    def _sim(a, b):
        return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

    def _last_name(s):
        parts = _norm(s).split()
        return parts[-1] if parts else ""

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    has_cs = _has_column(db_path, "players", "cricsheet_name")
    cs_col = "cricsheet_name" if has_cs else "NULL as cricsheet_name"

    all_players = conn.execute(f"""
        SELECT name, role, name_aliases, is_key_player, batting_style, bowling_style, {cs_col},
               t20_avg, t20_sr, t20_wkts, t20_bowl_avg, t20_bowl_econ, t20_bowl_sr
        FROM players
    """).fetchall()

    form_map = {}
    for r in conn.execute("""
        SELECT p.name, pf.form_score FROM players p
        JOIN player_form pf ON pf.player_id = p.player_id
        WHERE pf.format IN ('T20','T20I')
    """).fetchall():
        form_map[r["name"]] = r["form_score"]
    conn.close()

    def match_player(input_name):
        best_row, best_score = None, 0.0
        for row in all_players:
            candidates = [row["name"]]
            if row["name_aliases"]:
                candidates += [a.strip() for a in row["name_aliases"].split(",")]
            for cand in candidates:
                if not cand:
                    continue
                if _norm(cand) == _norm(input_name):
                    return row, 1.0
                score = 0.90 if _last_name(cand) == _last_name(input_name) and _last_name(cand) else _sim(cand, input_name)
                if score > best_score:
                    best_score, best_row = score, row
        return (best_row, best_score) if best_score >= 0.72 else (None, best_score)

    batters, bowlers, log = [], [], []

    for i, name in enumerate(player_names[:11]):
        row, score = match_player(name)
        pos = i + 1

        if row:
            form = form_map.get(row["name"], 5.0)
            log.append(f"✅ {name} → {row['name']} (match {score:.2f})")
            batters.append(Batter(
                name=row["name"], avg=row["t20_avg"] or 0, sr=row["t20_sr"] or 0,
                form=form, position=pos, batting_style=row["batting_style"] or "",
                cricsheet_name=row["cricsheet_name"] or ""
            ))
            if row["role"] in ("bowl", "all") or row["bowling_style"]:
                bowlers.append(Bowler(
                    name=row["name"], econ=row["t20_bowl_econ"] or 0,
                    bowl_sr=row["t20_bowl_sr"] or 0, form=form,
                    max_overs=4 if fmt != "100b" else 5,
                    bowling_style=row["bowling_style"] or "",
                    cricsheet_name=row["cricsheet_name"] or "",
                ))
        else:
            log.append(f"⚠ {name} → not found in DB, using league-average stats")
            batters.append(Batter(name=name, avg=LEAGUE_AVG_BAT_AVG, sr=LEAGUE_AVG_SR,
                                    form=5.0, position=pos))
            if pos >= 7:
                bowlers.append(Bowler(name=name, econ=LEAGUE_AVG_BOWL_ECON,
                                        bowl_sr=LEAGUE_AVG_BOWL_SR, form=5.0,
                                        max_overs=4 if fmt != "100b" else 5))

    # Ensure at least 5 bowling options
    while len(bowlers) < 5 and len(bowlers) < len(batters):
        candidates = [b for b in batters if b.name not in [bo.name for bo in bowlers]]
        if not candidates:
            break
        c = candidates[-1]
        bowlers.append(Bowler(name=c.name, econ=LEAGUE_AVG_BOWL_ECON * 1.15,
                               bowl_sr=LEAGUE_AVG_BOWL_SR * 1.3, form=c.form, max_overs=2))

    lineup = TeamLineup(name=team_name, batters=batters, bowlers=bowlers)
    return lineup, log


if __name__ == "__main__":
    ta = build_lineup_from_db("MI London")
    tb = build_lineup_from_db("Manchester Super Giants")
    print(f"Team A ({ta.name}): {len(ta.batters)} batters, {len(ta.bowlers)} bowlers")
    print(f"Team B ({tb.name}): {len(tb.batters)} batters, {len(tb.bowlers)} bowlers")

    result = run_monte_carlo(ta, tb, total_balls=100, n_sims=2000)
    print(f"\n{result['team_a']}: {result['team_a_win_pct']}% win  "
          f"(median {result['team_a_score_median']}, "
          f"p10-p90: {result['team_a_score_p10']}-{result['team_a_score_p90']})")
    print(f"{result['team_b']}: {result['team_b_win_pct']}% win  "
          f"(median {result['team_b_score_median']}, "
          f"p10-p90: {result['team_b_score_p10']}-{result['team_b_score_p90']})")
    print(f"Tie: {result['tie_pct']}%")
