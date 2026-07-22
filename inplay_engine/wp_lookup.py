"""
inplay_engine/wp_lookup.py
===========================
Queries the win probability lookup table for any live match state.
Blends empirical frequency with ELO team quality adjustment.

Called by verdict.py and the Streamlit in-play page.
"""

import sqlite3, os, sys, math
from dataclasses import dataclass, field
from typing import Optional

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IP_DB    = os.path.join(ROOT, "db", "inplay_engine.db")
MAIN_DB  = os.path.join(ROOT, "db", "cricket_engine.db")

FORMAT_CONFIG = {
    "T20":  {"total_balls": 120, "par_rr": 8.0,  "balls_bin": 5,  "runs_bin": 8,  "max_runs": 240},
    "T20I": {"total_balls": 120, "par_rr": 8.0,  "balls_bin": 5,  "runs_bin": 8,  "max_runs": 240},
    "100b": {"total_balls": 100, "par_rr": 9.6,  "balls_bin": 5,  "runs_bin": 8,  "max_runs": 220},
    "ODI":  {"total_balls": 300, "par_rr": 5.5,  "balls_bin": 12, "runs_bin": 15, "max_runs": 500},
}

ELO_BLEND   = 0.30   # 30% ELO, 70% historical table
MIN_SAMPLE  = 15     # fall back to WASP if fewer observations

@dataclass
class MatchState:
    """Current live match state — what you enter during the game."""
    format:         str          # T20 / T20I / 100b / ODI
    innings:        int          # 1 or 2
    batting_team:   str          # team currently batting
    bowling_team:   str          # team currently bowling
    balls_completed: int         # balls bowled so far this innings
    score:          int          # current runs
    wickets_lost:   int          # wickets down (0-9)
    target:         Optional[int] = None   # 2nd innings only
    # market
    betfair_odds:   float = 2.00           # current Betfair price on batting_team
    # pre-match
    pre_match_stake: float = 0.0           # stake already placed on this match
    pre_match_odds:  float = 2.00          # original odds taken
    pre_match_team:  str   = ""            # which team the pre-match bet is on
    bankroll:        float = 5000.0
    phase:           int   = 1
    gender:          str   = "male"

@dataclass
class WPResult:
    """Win probability result with full breakdown."""
    batting_team:   str
    bowling_team:   str
    format:         str
    innings:        int
    # state summary
    balls_remaining: int
    wickets_in_hand: int
    runs_needed:    Optional[int]
    required_rr:    Optional[float]
    # probabilities
    historical_wp:  float         # raw from lookup table
    elo_wp:         float         # ELO-based probability
    blended_wp:     float         # final blended probability
    implied_wp:     float         # from Betfair odds
    edge:           float         # blended_wp - implied_wp
    # sample info
    sample_size:    int
    confidence:     str
    fallback_used:  bool = False  # True if WASP formula used
    # pressure
    pressure_index: float = 1.0  # RRR / par_rr
    # details
    elo_batting:    float = 1500.0
    elo_bowling:    float = 1500.0

def _get_elo(team: str, gender: str, fmt: str) -> float:
    try:
        conn = sqlite3.connect(MAIN_DB)
        r = conn.execute(
            "SELECT rating FROM elo_ratings WHERE team_id=? AND gender=? AND format=?",
            (team, gender, fmt)
        ).fetchone()
        conn.close()
        return r[0] if r else 1500.0
    except Exception:
        return 1500.0

def _elo_wp(rating_batting: float, rating_bowling: float) -> float:
    """ELO-based win probability for batting team."""
    return 1 / (1 + 10 ** ((rating_bowling - rating_batting) / 400))

def _wasp_wp(balls_remaining: int, wickets_lost: int,
             runs_needed: int, fmt: str) -> float:
    """
    WASP-style formula fallback when sample size is too small.
    Based on: required run rate, wickets in hand, balls remaining.
    Calibrated to match known cricket outcomes.
    """
    cfg = FORMAT_CONFIG.get(fmt, FORMAT_CONFIG["T20"])
    if balls_remaining <= 0 or runs_needed <= 0:
        return 0.0 if runs_needed > 0 else 1.0

    rr_needed = (runs_needed / balls_remaining) * 6
    par_rr    = cfg["par_rr"]
    rr_ratio  = rr_needed / par_rr

    wickets_in_hand = 10 - wickets_lost
    # Resource score: wickets × balls remaining (DLS-like)
    resource = (wickets_in_hand / 10) * (balls_remaining / cfg["total_balls"])

    # Sigmoid: higher pressure = lower win prob
    # Tuned so that RRR = par_rr + 50% resources → ~50% win prob
    z = -2.5 * (rr_ratio - 1.0) + 3.0 * (resource - 0.35)
    wp = 1 / (1 + math.exp(-z))
    return round(max(0.02, min(0.98, wp)), 4)

def _bin(val: int, bin_size: int, max_val: int) -> int:
    return (min(int(val), max_val) // bin_size) * bin_size

def lookup(state: MatchState) -> WPResult:
    """
    Main entry point. Returns WPResult for the given match state.
    """
    cfg = FORMAT_CONFIG.get(state.format)
    if not cfg:
        raise ValueError(f"Unsupported format: {state.format}")

    total_balls     = cfg["total_balls"]
    balls_remaining = total_balls - state.balls_completed
    wickets_in_hand = 10 - state.wickets_lost
    runs_needed     = (state.target - state.score) if state.target else None
    required_rr     = None
    pressure        = 1.0

    if runs_needed is not None and balls_remaining > 0:
        required_rr = round((runs_needed / balls_remaining) * 6, 2)
        pressure    = round(required_rr / cfg["par_rr"], 2)

    # ── ELO probabilities ──────────────────────────────────────
    # Map format for ELO lookup (T20 domestic uses same T20 rating)
    elo_fmt = state.format if state.format in ("ODI","Test","T20I") else "T20"
    elo_bat = _get_elo(state.batting_team, state.gender, elo_fmt)
    elo_bowl= _get_elo(state.bowling_team, state.gender, elo_fmt)
    elo_wp  = _elo_wp(elo_bat, elo_bowl)

    # ── Lookup table query ─────────────────────────────────────
    historical_wp = None
    sample_size   = 0
    confidence    = "low"
    fallback      = False

    try:
        ip_conn = sqlite3.connect(IP_DB)
        ip_conn.row_factory = sqlite3.Row

        br_bin = _bin(balls_remaining, cfg["balls_bin"], total_balls)
        rn_bin = _bin(runs_needed, cfg["runs_bin"], cfg["max_runs"]) if runs_needed else None

        row = ip_conn.execute("""
            SELECT win_pct, sample_size, confidence
            FROM wp_lookup
            WHERE format=? AND innings=? AND balls_remaining=?
              AND wickets_lost=? AND runs_needed=?
        """, (state.format, state.innings, br_bin,
              state.wickets_lost, rn_bin)).fetchone()

        if not row or row["sample_size"] < MIN_SAMPLE:
            # Try adjacent bins
            for wk_adj in [0, -1, 1]:
                wk = max(0, min(9, state.wickets_lost + wk_adj))
                row = ip_conn.execute("""
                    SELECT win_pct, sample_size, confidence
                    FROM wp_lookup
                    WHERE format=? AND innings=? AND balls_remaining=?
                      AND wickets_lost=? AND runs_needed=?
                """, (state.format, state.innings, br_bin, wk, rn_bin)).fetchone()
                if row and row["sample_size"] >= MIN_SAMPLE:
                    break

        ip_conn.close()

        if row and row["sample_size"] >= MIN_SAMPLE:
            historical_wp = row["win_pct"] / 100
            sample_size   = row["sample_size"]
            confidence    = row["confidence"]
        else:
            # Fallback to WASP
            historical_wp = _wasp_wp(balls_remaining, state.wickets_lost,
                                     runs_needed or 0, state.format)
            fallback = True
            confidence = "low (WASP fallback)"

    except Exception as e:
        historical_wp = _wasp_wp(balls_remaining, state.wickets_lost,
                                 runs_needed or 0, state.format)
        fallback = True
        confidence = "low (DB error)"

    # ── Blend: 70% historical + 30% ELO ──────────────────────
    blended_wp = round(
        (1 - ELO_BLEND) * historical_wp + ELO_BLEND * elo_wp, 4
    )

    # ── Market comparison ─────────────────────────────────────
    implied_wp = round(1 / state.betfair_odds, 4)
    edge       = round(blended_wp - implied_wp, 4)

    return WPResult(
        batting_team    = state.batting_team,
        bowling_team    = state.bowling_team,
        format          = state.format,
        innings         = state.innings,
        balls_remaining = balls_remaining,
        wickets_in_hand = wickets_in_hand,
        runs_needed     = runs_needed,
        required_rr     = required_rr,
        historical_wp   = round(historical_wp, 4),
        elo_wp          = round(elo_wp, 4),
        blended_wp      = blended_wp,
        implied_wp      = implied_wp,
        edge            = edge,
        sample_size     = sample_size,
        confidence      = confidence,
        fallback_used   = fallback,
        pressure_index  = pressure,
        elo_batting     = elo_bat,
        elo_bowling     = elo_bowl,
    )

def print_result(r: WPResult):
    """Pretty print a lookup result."""
    print(f"\n  {'─'*55}")
    print(f"  {r.batting_team} batting  vs  {r.bowling_team}")
    print(f"  {r.format} {'2nd innings' if r.innings==2 else '1st innings'}")
    print(f"  {'─'*55}")
    print(f"  Balls remaining:   {r.balls_remaining}")
    print(f"  Wickets in hand:   {r.wickets_in_hand}")
    if r.runs_needed:
        print(f"  Runs needed:       {r.runs_needed}")
        print(f"  Required RR:       {r.required_rr}")
        print(f"  Pressure index:    {r.pressure_index:.2f}x  "
              f"({'high' if r.pressure_index>1.4 else 'medium' if r.pressure_index>1.1 else 'manageable'})")
    print(f"  {'─'*55}")
    print(f"  Historical WP:     {r.historical_wp:.1%}  "
          f"(n={r.sample_size}, {r.confidence})"
          + (" [WASP fallback]" if r.fallback_used else ""))
    print(f"  ELO WP:            {r.elo_wp:.1%}  "
          f"({r.batting_team} {r.elo_batting:.0f} vs {r.bowling_team} {r.elo_bowling:.0f})")
    print(f"  BLENDED WP:        {r.blended_wp:.1%}  (70% hist + 30% ELO)")
    print(f"  Betfair implied:   {r.implied_wp:.1%}")
    print(f"  Edge:              {r.edge:+.1%}")
    edge_str = ("SIGNIFICANT EDGE" if abs(r.edge) > 0.06
                else "MODERATE" if abs(r.edge) > 0.03
                else "minimal")
    direction = r.batting_team if r.edge > 0 else r.bowling_team
    print(f"  Assessment:        {edge_str} — {direction} side")

if __name__ == "__main__":
    # Test queries
    tests = [
        # Yesterday's Hundred match — MI London 51/3 chasing 144 in 56 balls
        MatchState("T20", 2, "MI London", "Sunrisers Leeds",
                   44, 51, 3, 144, betfair_odds=3.00,
                   pre_match_stake=199, pre_match_odds=1.95,
                   pre_match_team="MI London", bankroll=5334),

        # India ODI — comfortable chase 50/0 after 30 balls chasing 260
        MatchState("ODI", 2, "India", "England",
                   30, 50, 0, 260, betfair_odds=1.60,
                   pre_match_stake=167, pre_match_odds=2.08,
                   pre_match_team="India", bankroll=5500),

        # T20I — under pressure 80/4 chasing 165 in 40 balls
        MatchState("T20I", 2, "India", "England",
                   80, 80, 4, 165, betfair_odds=2.20,
                   pre_match_stake=150, pre_match_odds=2.05,
                   pre_match_team="India", bankroll=5500),

        # CPL T20 — end of innings, 12/0 needing 14 in 6 balls (win likely)
        MatchState("T20", 2, "Trinbago KR", "Guyana AW",
                   114, 131, 1, 145, betfair_odds=1.15,
                   pre_match_stake=120, pre_match_odds=1.72,
                   pre_match_team="Trinbago KR", bankroll=6000),
    ]

    print("\n" + "="*58)
    print("  WIN PROBABILITY LOOKUP — TEST QUERIES")
    print("="*58)

    for state in tests:
        result = lookup(state)
        print_result(result)
    print()
