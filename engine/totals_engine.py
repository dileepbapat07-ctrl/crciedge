"""
engine/totals_engine.py
=======================
Over/Under totals betting engine.
Compares our venue-based predicted total vs bookmaker line to find edge.

Strategy from research:
  Bookmakers use generic global averages for total lines.
  Our Cricsheet venue database has ground-specific averages.
  When the gap is >8 runs (T20) or >15 runs (ODI), there's exploitable edge.

USAGE:
  from engine.totals_engine import analyse_totals, TotalsContext
  result = analyse_totals(ctx)

  # Or from command line:
  python totals_engine.py --match-id 20260714-ENG-IND-ODI-2NDODI \
                          --bk-line-first 280 --bk-line-total 570
"""

import sqlite3, os, sys, math
from dataclasses import dataclass, field
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")

# ── Edge thresholds ────────────────────────────────────────────────────────
# Minimum gap between our prediction and bookmaker line to bet
MIN_EDGE_T20  = 7    # runs — T20 scoring variance is high, need bigger gap
MIN_EDGE_ODI  = 12   # runs
MIN_EDGE_TEST = 25   # runs — per innings

# Confidence thresholds
CONF_BET    = 68
CONF_REDUCE = 52

@dataclass
class TotalsContext:
    match_id:       str
    venue_id:       str
    format:         str          # ODI / T20I / T20 / Test
    gender:         str          # male / female
    team_a:         str
    team_b:         str
    bankroll:       float
    phase:          int          # 1 or 2

    # Bookmaker lines (enter from Betfair/Bet365)
    bk_line_first:  Optional[float] = None   # 1st innings over/under line
    bk_line_total:  Optional[float] = None   # match total over/under line
    bk_odds_over:   float = 1.90             # odds for over
    bk_odds_under:  float = 1.90             # odds for under

    # Conditions (optional overrides)
    weather_score:  float = 7.0   # 1-10, higher = better batting conditions
    pitch_type:     str   = "flat" # flat/green/spin/deteriorating
    dew_expected:   bool  = False  # D/N match with dew?
    toss_winner:    Optional[str] = None
    toss_choice:    Optional[str] = None  # bat/field

@dataclass
class TotalsResult:
    match_id:       str
    team_a:         str
    team_b:         str
    format:         str

    # Predictions
    predicted_first:  float = 0
    predicted_total:  float = 0

    # Venue baseline
    venue_avg_first:  float = 0
    venue_avg_total:  float = 0
    venue_matches:    int   = 0

    # Market comparison
    bk_line_first:    Optional[float] = None
    bk_line_total:    Optional[float] = None
    gap_first:        float = 0    # our pred minus bk line (+ = we think higher)
    gap_total:        float = 0

    # Edge
    ev_first_over:    float = 0
    ev_first_under:   float = 0
    ev_total_over:    float = 0
    ev_total_under:   float = 0

    # Output
    best_bet:         str   = "skip"
    best_ev:          float = 0
    best_line:        str   = ""
    confidence:       float = 0
    recommended_stake: float = 0
    verdict:          str   = "SKIP"
    reason:           str   = ""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ── Venue stats lookup ─────────────────────────────────────────────────────
def get_venue_stats(venue_id, fmt, gender):
    conn = get_conn()
    # Map T20I → T20 for venue lookup (same pitches)
    # Try both male/female gender values
    lookup_fmts = ["T20", "T20I"] if fmt in ("T20", "T20I") else [fmt]
    lookup_genders = [gender, "male", "female"]

    row = None
    for lf in lookup_fmts:
        for lg in lookup_genders:
            row = conn.execute("""
                SELECT avg_first_innings, avg_second_innings, matches_played,
                       highest_score, lowest_score, avg_powerplay_score,
                       avg_death_score, toss_win_bat_pct, bat_first_win_pct
                FROM venue_stats
                WHERE venue_id=? AND format=? AND gender=?
                ORDER BY matches_played DESC LIMIT 1
            """, (venue_id, lf, lg)).fetchone()
            if row and row["avg_first_innings"]:
                conn.close()
                return dict(row)

    # Final fallback — any format at this venue
    if not row:
        row = conn.execute("""
            SELECT avg_first_innings, avg_second_innings, matches_played,
                   highest_score, lowest_score, avg_powerplay_score,
                   avg_death_score, toss_win_bat_pct, bat_first_win_pct
            FROM venue_stats
            WHERE venue_id=?
            ORDER BY matches_played DESC LIMIT 1
        """, (venue_id,)).fetchone()

    conn.close()
    return dict(row) if row else None

# ── Team scoring average ───────────────────────────────────────────────────
def get_team_avg_score(team, fmt, gender):
    """Get team's average batting score from ELO match history"""
    conn = get_conn()
    # Use ELO rating as proxy for batting strength
    row = conn.execute("""
        SELECT rating FROM elo_ratings
        WHERE team_id=? AND gender=? AND format=?
    """, (team, gender, fmt)).fetchone()
    conn.close()

    if row:
        # Convert ELO to small batting adjustment
        # 1800 ELO → +5% above venue avg
        # 1500 ELO → neutral (0%)
        # 1200 ELO → -5% below venue avg
        elo = row["rating"]
        return max(0.92, min(1.08, (elo - 1500) / 6000 + 1.0))
    return 1.0  # neutral

# ── Conditions adjustment ──────────────────────────────────────────────────
def conditions_factor(ctx: TotalsContext) -> float:
    """
    Returns a multiplier for predicted score based on conditions.
    1.0 = neutral, >1.0 = higher scores expected, <1.0 = lower
    """
    factor = 1.0

    # Weather
    if ctx.weather_score >= 9:   factor *= 1.04   # hot clear day — good batting
    elif ctx.weather_score <= 4: factor *= 0.94   # overcast/windy — swing bowling

    # Pitch type
    pitch_adj = {
        "flat":         1.06,
        "good":         1.02,
        "neutral":      1.00,
        "spin":         0.96,
        "green":        0.92,
        "deteriorating":0.88,
    }
    factor *= pitch_adj.get(ctx.pitch_type, 1.0)

    # Dew in D/N — benefits batting side in 2nd innings, raises totals
    if ctx.dew_expected:
        factor *= 1.03

    return factor

# ── Win probability from line ──────────────────────────────────────────────
def prob_over(predicted, line, fmt):
    """
    Probability that actual score > line, given predicted score.
    Uses normal distribution with format-appropriate standard deviation.
    """
    std = {"T20": 18, "T20I": 18, "ODI": 28, "Test": 55}.get(fmt, 25)
    z = (predicted - line) / std
    # Approximate CDF
    prob = 1 / (1 + math.exp(-1.7 * z))
    return round(max(0.05, min(0.95, prob)), 4)

def ev_pct(prob, odds):
    return round((prob * odds - 1) * 100, 2)

# ── Kelly stake ────────────────────────────────────────────────────────────
def kelly_stake(prob, odds, bankroll, phase):
    b = odds - 1
    kf = max(0, (b * prob - (1 - prob)) / b)
    frac = 0.25 if phase == 1 else 0.125
    return round(bankroll * kf * frac, 2)

# ── Main analysis function ─────────────────────────────────────────────────
def analyse_totals(ctx: TotalsContext) -> TotalsResult:
    result = TotalsResult(
        match_id=ctx.match_id,
        team_a=ctx.team_a,
        team_b=ctx.team_b,
        format=ctx.format,
    )

    # 1. Get venue baseline
    vs = get_venue_stats(ctx.venue_id, ctx.format, ctx.gender)
    if not vs or not vs.get("avg_first_innings"):
        result.reason = f"Insufficient venue data for {ctx.venue_id} — skip totals market"
        return result

    venue_avg_first = vs["avg_first_innings"]
    venue_avg_second = vs.get("avg_second_innings") or venue_avg_first * 0.90
    venue_avg_total  = venue_avg_first + venue_avg_second
    venue_matches    = vs.get("matches_played", 0)

    result.venue_avg_first  = venue_avg_first
    result.venue_avg_total  = round(venue_avg_total, 1)
    result.venue_matches    = venue_matches

    # 2. Team batting adjustments
    ta_bat = get_team_avg_score(ctx.team_a, ctx.format, ctx.gender)
    tb_bat = get_team_avg_score(ctx.team_b, ctx.format, ctx.gender)
    combined_batting = (ta_bat + tb_bat) / 2

    # 3. Conditions factor
    cond = conditions_factor(ctx)

    # 4. Predict scores
    # Blend venue average (70%) with team strength adjustment (30%)
    pred_first  = venue_avg_first  * (0.70 + combined_batting * 0.30) * cond
    pred_second = venue_avg_second * (0.70 + combined_batting * 0.30) * cond
    # Dew in 2nd innings boosts chasing team score
    if ctx.dew_expected:
        pred_second *= 1.05
    pred_total = pred_first + pred_second

    result.predicted_first = round(pred_first, 1)
    result.predicted_total = round(pred_total, 1)

    # 5. Confidence from data richness
    data_conf = min(85, 40 + venue_matches * 0.8)

    # 6. Compare to bookmaker lines and find best bet
    bets = []

    if ctx.bk_line_first is not None:
        gap_f = pred_first - ctx.bk_line_first
        result.bk_line_first = ctx.bk_line_first
        result.gap_first     = round(gap_f, 1)

        p_over  = prob_over(pred_first, ctx.bk_line_first, ctx.format)
        p_under = 1 - p_over

        ev_over  = ev_pct(p_over,  ctx.bk_odds_over)
        ev_under = ev_pct(p_under, ctx.bk_odds_under)

        result.ev_first_over  = ev_over
        result.ev_first_under = ev_under

        min_edge = MIN_EDGE_T20 if ctx.format in ("T20","T20I") else MIN_EDGE_ODI

        if abs(gap_f) >= min_edge:
            if ev_over > 0:
                bets.append(("1st innings OVER",   ev_over,  p_over,  ctx.bk_odds_over,
                             f"Venue avg {venue_avg_first:.0f} vs line {ctx.bk_line_first:.0f} — gap {gap_f:+.0f}"))
            if ev_under > 0:
                bets.append(("1st innings UNDER", ev_under, p_under, ctx.bk_odds_under,
                             f"Venue avg {venue_avg_first:.0f} vs line {ctx.bk_line_first:.0f} — gap {gap_f:+.0f}"))

    if ctx.bk_line_total is not None:
        gap_t = pred_total - ctx.bk_line_total
        result.bk_line_total = ctx.bk_line_total
        result.gap_total     = round(gap_t, 1)

        p_over  = prob_over(pred_total, ctx.bk_line_total, ctx.format)
        p_under = 1 - p_over

        ev_over  = ev_pct(p_over,  ctx.bk_odds_over)
        ev_under = ev_pct(p_under, ctx.bk_odds_under)

        result.ev_total_over  = ev_over
        result.ev_total_under = ev_under

        min_edge = (MIN_EDGE_T20 * 2) if ctx.format in ("T20","T20I") else (MIN_EDGE_ODI * 2)

        if abs(gap_t) >= min_edge:
            if ev_over > 0:
                bets.append(("Match total OVER",  ev_over,  p_over,  ctx.bk_odds_over,
                             f"Predicted total {pred_total:.0f} vs line {ctx.bk_line_total:.0f}"))
            if ev_under > 0:
                bets.append(("Match total UNDER", ev_under, p_under, ctx.bk_odds_under,
                             f"Predicted total {pred_total:.0f} vs line {ctx.bk_line_total:.0f}"))

    # 7. Pick best bet
    if bets:
        bets.sort(key=lambda x: -x[1])  # sort by EV descending
        best_name, best_ev, best_prob, best_odds, best_reason = bets[0]

        stake = kelly_stake(best_prob, best_odds, ctx.bankroll, ctx.phase)
        conf  = round(min(90, data_conf * (1 + best_ev / 100)), 1)
        verdict = "BET" if conf >= CONF_BET else "REDUCE" if conf >= CONF_REDUCE else "SKIP"
        if best_ev <= 0:
            verdict = "SKIP"

        result.best_bet          = best_name
        result.best_ev           = best_ev
        result.best_line         = best_reason
        result.confidence        = conf
        result.recommended_stake = stake
        result.verdict           = verdict
        result.reason = (
            f"{best_name} — EV {best_ev:+.1f}% · Conf {conf:.0f}/100 · "
            f"Model: {pred_first:.0f} predicted vs {ctx.bk_line_first or ctx.bk_line_total:.0f} line. "
            f"{best_reason}"
        )
    else:
        min_e = MIN_EDGE_T20 if ctx.format in ("T20","T20I") else MIN_EDGE_ODI
        result.reason = (
            f"No value found. Predicted 1st innings: {pred_first:.0f}. "
            f"Gap to line must be >{min_e} runs for T20 or >{MIN_EDGE_ODI} for ODI. "
            f"Skip totals market this match."
        )

    # 8. Save to DB
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO totals_analysis
        (match_id, venue_id, format, gender,
         venue_avg_first, venue_avg_total, venue_matches,
         team_a_avg_score, team_b_avg_score, weather_factor,
         predicted_first_innings, predicted_match_total,
         bookmaker_line_first, bookmaker_line_total,
         first_ev_over, first_ev_under, total_ev_over, total_ev_under,
         best_bet, best_ev, confidence, recommended_stake)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (ctx.match_id, ctx.venue_id, ctx.format, ctx.gender,
          venue_avg_first, round(venue_avg_total,1), venue_matches,
          round(ta_bat,3), round(tb_bat,3), round(cond,3),
          result.predicted_first, result.predicted_total,
          ctx.bk_line_first, ctx.bk_line_total,
          result.ev_first_over, result.ev_first_under,
          result.ev_total_over, result.ev_total_under,
          result.best_bet, result.best_ev, result.confidence,
          result.recommended_stake))
    conn.commit()
    conn.close()

    return result

# ── Quick test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("TOTALS ENGINE — TEST CASES")
    print("="*60)

    # Test 1: England vs India ODI at Edgbaston today
    ctx1 = TotalsContext(
        match_id    = "20260714-ENG-IND-ODI-1STODI",
        venue_id    = "edgbaston-birmingham",
        format      = "ODI",
        gender      = "male",
        team_a      = "England",
        team_b      = "India",
        bankroll    = 5000.0,
        phase       = 1,
        bk_line_first = 285,    # bookmaker's 1st innings line
        bk_line_total = 580,    # both teams combined
        bk_odds_over  = 1.90,
        bk_odds_under = 1.90,
        weather_score = 9.0,    # hot clear day
        pitch_type  = "flat",
        dew_expected= False,    # day match
    )
    r1 = analyse_totals(ctx1)
    print(f"\n1. {r1.team_a} vs {r1.team_b} [{r1.format}] — Edgbaston")
    print(f"   Venue avg 1st innings: {r1.venue_avg_first:.0f} ({r1.venue_matches} matches)")
    print(f"   Predicted 1st innings: {r1.predicted_first:.0f}")
    print(f"   Predicted match total: {r1.predicted_total:.0f}")
    if r1.bk_line_first:
        print(f"   Bk line (1st innings): {r1.bk_line_first:.0f}  Gap: {r1.gap_first:+.0f}")
        print(f"   EV Over: {r1.ev_first_over:+.1f}%  EV Under: {r1.ev_first_under:+.1f}%")
    print(f"   Best bet: {r1.best_bet}")
    print(f"   Verdict: {r1.verdict}  EV: {r1.best_ev:+.1f}%  Conf: {r1.confidence:.0f}/100")
    print(f"   Stake: €{r1.recommended_stake:.2f}")
    print(f"   Reason: {r1.reason}")

    # Test 2: BBL T20 at Adelaide Oval
    ctx2 = TotalsContext(
        match_id    = "20261223-ADE-SYT-T20-BBL10",
        venue_id    = "adelaide-oval-adelaide",
        format      = "T20",
        gender      = "male",
        team_a      = "Adelaide Strikers",
        team_b      = "Sydney Thunder",
        bankroll    = 80000.0,
        phase       = 2,
        bk_line_first = 162,    # bk line 1st innings T20
        bk_odds_over  = 1.88,
        bk_odds_under = 1.92,
        weather_score = 8.0,
        pitch_type  = "flat",
    )
    r2 = analyse_totals(ctx2)
    print(f"\n2. {r2.team_a} vs {r2.team_b} [{r2.format}] — Adelaide Oval (BBL)")
    print(f"   Venue avg 1st innings: {r2.venue_avg_first:.0f}")
    print(f"   Predicted 1st innings: {r2.predicted_first:.0f}")
    if r2.bk_line_first:
        print(f"   Bk line: {r2.bk_line_first:.0f}  Gap: {r2.gap_first:+.0f}")
        print(f"   EV Over: {r2.ev_first_over:+.1f}%  EV Under: {r2.ev_first_under:+.1f}%")
    print(f"   Verdict: {r2.verdict}  EV: {r2.best_ev:+.1f}%")
    print(f"   Reason: {r2.reason}")

    # Test 3: WBBL at Junction Oval
    ctx3 = TotalsContext(
        match_id    = "20261112-MRS-BRH-T20-WBBLM19",
        venue_id    = "junction-oval-melbourne",
        format      = "T20",
        gender      = "female",
        team_a      = "Melbourne Renegades W",
        team_b      = "Brisbane Heat W",
        bankroll    = 60000.0,
        phase       = 2,
        bk_line_first = 148,
        bk_odds_over  = 1.90,
        bk_odds_under = 1.90,
        weather_score = 7.0,
    )
    r3 = analyse_totals(ctx3)
    print(f"\n3. {r3.team_a} vs {r3.team_b} [{r3.format}] — Junction Oval (WBBL)")
    print(f"   Venue avg 1st innings: {r3.venue_avg_first:.0f}")
    print(f"   Predicted 1st innings: {r3.predicted_first:.0f}")
    if r3.bk_line_first:
        print(f"   Bk line: {r3.bk_line_first:.0f}  Gap: {r3.gap_first:+.0f}")
    print(f"   Verdict: {r3.verdict}  EV: {r3.best_ev:+.1f}%")
    print(f"   Reason: {r3.reason}")
