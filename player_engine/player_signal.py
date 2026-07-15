"""
player_engine/player_signal.py
================================
The bridge between player analytics and the betting decision engine.

Reads player_engine.db and outputs a structured signal for each match:
  - Overall 0-10 factor for team_a advantage (feeds into decision_engine.py)
  - Detailed breakdown: batting, bowling, form, venue, matchups, availability
  - Key insights list (human-readable reasons)
  - EV adjustment % (how much the player edge should shift the EV estimate)

USAGE — from decision engine:
    from player_engine.player_signal import get_player_signal
    signal = get_player_signal(match_id, team_a, team_b, format, venue_id, gender)
    confidence_adjustment = signal.signal_factor  # 0-10, plug in as players factor

USAGE — standalone test:
    python player_signal.py
"""

import sqlite3, os, sys, json, math
from datetime import date, datetime
from dataclasses import dataclass, field
from typing import Optional

PLAYER_DB = os.path.join(os.path.dirname(__file__), "../db/player_engine.db")
CRICKET_DB= os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")

# ── Weights within player signal ─────────────────────────────
WEIGHTS = {
    "batting":      0.25,   # team batting depth and quality
    "bowling":      0.25,   # team bowling attack quality
    "form":         0.20,   # recent form of key players
    "venue":        0.15,   # key players' venue-specific record
    "matchups":     0.10,   # batter vs bowler head-to-head edges
    "availability": 0.05,   # squad completeness (injuries/resting)
}

# ── Key player thresholds ─────────────────────────────────────
KEY_BATTER_POSITIONS  = [1, 2, 3, 4, 5]   # top 5 batting order
KEY_BOWLER_FORM_SCORE = 7.0                # form score threshold for "in form" bowler
VENUE_MIN_INNINGS     = 2                  # min innings to use venue stats

# ── EV adjustment scale ───────────────────────────────────────
# signal_factor 8.0+ → +5% EV for team_a
# signal_factor 5.0  → 0% (neutral)
# signal_factor 2.0- → -5% EV for team_a
MAX_EV_ADJUSTMENT = 6.0  # % maximum EV shift from player signal

@dataclass
class TeamSignal:
    team:           str
    batting_score:  float = 5.0
    bowling_score:  float = 5.0
    form_score:     float = 5.0
    venue_score:    float = 5.0
    matchup_score:  float = 5.0
    avail_score:    float = 5.0
    overall:        float = 5.0
    key_batters:    list  = field(default_factory=list)
    key_bowlers:    list  = field(default_factory=list)
    insights:       list  = field(default_factory=list)
    injuries:       list  = field(default_factory=list)

@dataclass
class PlayerSignal:
    match_id:       str
    team_a:         str
    team_b:         str
    format:         str
    venue_id:       str
    team_a_signal:  TeamSignal = field(default_factory=lambda: TeamSignal(team=""))
    team_b_signal:  TeamSignal = field(default_factory=lambda: TeamSignal(team=""))
    signal_factor:  float = 5.0     # 0-10 for team_a advantage
    signal_ev_adj:  float = 0.0     # EV adjustment %
    key_insights:   list  = field(default_factory=list)
    data_quality:   str   = "low"   # low/medium/high

# ── DB helpers ────────────────────────────────────────────────
def get_conn():
    if not os.path.exists(PLAYER_DB):
        return None
    conn = sqlite3.connect(PLAYER_DB)
    conn.row_factory = sqlite3.Row
    return conn

def safe_float(val, default=5.0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default

# ── Individual scorers ────────────────────────────────────────

def score_batting(conn, team, fmt, match_id) -> tuple[float, list, list]:
    """
    Score a team's batting strength 0-10.
    Returns (score, key_batters_list, insights)
    """
    insights = []

    # Get confirmed playing XI
    xi = conn.execute("""
        SELECT p.player_id, p.name, p.short_name, p.batting_position,
               p.is_key_player, p.role,
               pf.form_score, pf.trend, pf.last_5_avg, pf.last_5_sr
        FROM playing_xi xi
        JOIN players p ON xi.player_id = p.player_id
        LEFT JOIN player_form pf ON pf.player_id = p.player_id AND pf.format=?
        WHERE xi.match_id=? AND xi.team=? AND xi.is_available=1
          AND p.role IN ('bat','wk','all')
        ORDER BY COALESCE(xi.batting_position, p.batting_position, 11)
    """, (fmt, match_id, team)).fetchall()

    if not xi:
        # No XI entered — use team's known players from form table
        xi = conn.execute("""
            SELECT p.player_id, p.name, p.short_name, p.batting_position,
                   p.is_key_player, p.role,
                   pf.form_score, pf.trend, pf.last_5_avg, pf.last_5_sr
            FROM players p
            LEFT JOIN player_form pf ON pf.player_id = p.player_id AND pf.format=?
            WHERE p.team=? AND p.role IN ('bat','wk','all')
            ORDER BY p.batting_position
            LIMIT 7
        """, (fmt, team)).fetchall()

    if not xi:
        return 5.0, [], ["No batting data available — using neutral score"]

    total_score = 0
    weight_sum  = 0
    key_batters = []

    for i, batter in enumerate(xi):
        # Weight by position — opener and #3 most important
        pos_weight = {0: 2.0, 1: 2.0, 2: 2.2, 3: 1.8, 4: 1.6}.get(i, 1.0)
        form = safe_float(batter["form_score"], 5.0)

        total_score += form * pos_weight
        weight_sum  += pos_weight

        if batter["is_key_player"] or i < 4:
            name  = batter["short_name"] or batter["name"]
            trend = batter["trend"] or "flat"
            l5avg = batter["last_5_avg"]
            arrow = {"up":"↑","flat":"→","down":"↓"}.get(trend, "→")

            key_batters.append({
                "name":  name,
                "form":  round(form, 1),
                "trend": trend,
                "l5avg": round(l5avg, 1) if l5avg else None,
            })

            if form >= 8.5:
                insights.append(f"{name} in exceptional form (score {form:.1f}/10) {arrow}")
            elif form >= 7.5:
                insights.append(f"{name} in good form {arrow}")
            elif form <= 4.0:
                insights.append(f"{name} out of form ({form:.1f}/10) {arrow} — concern")

    batting_score = (total_score / weight_sum) if weight_sum > 0 else 5.0
    return round(min(10, max(0, batting_score)), 2), key_batters, insights

def score_bowling(conn, team, fmt, match_id) -> tuple[float, list, list]:
    """
    Score a team's bowling attack strength 0-10.
    Returns (score, key_bowlers_list, insights)
    """
    insights = []

    xi = conn.execute("""
        SELECT p.player_id, p.name, p.short_name, p.is_key_player, p.role,
               p.bowling_style, p.icc_rank_bowl,
               pf.form_score, pf.trend, pf.last_5_economy, pf.last_5_wickets
        FROM playing_xi xi
        JOIN players p ON xi.player_id = p.player_id
        LEFT JOIN player_form pf ON pf.player_id = p.player_id AND pf.format=?
        WHERE xi.match_id=? AND xi.team=? AND xi.is_available=1
          AND p.role IN ('bowl','all') AND p.bowling_style != 'none'
        ORDER BY p.icc_rank_bowl ASC
    """, (fmt, match_id, team)).fetchall()

    if not xi:
        xi = conn.execute("""
            SELECT p.player_id, p.name, p.short_name, p.is_key_player, p.role,
                   p.bowling_style, p.icc_rank_bowl,
                   pf.form_score, pf.trend, pf.last_5_economy, pf.last_5_wickets
            FROM players p
            LEFT JOIN player_form pf ON pf.player_id = p.player_id AND pf.format=?
            WHERE p.team=? AND p.role IN ('bowl','all') AND p.bowling_style != 'none'
            ORDER BY p.icc_rank_bowl ASC NULLS LAST
            LIMIT 5
        """, (fmt, team)).fetchall()

    if not xi:
        return 5.0, [], ["No bowling data available — using neutral score"]

    total_score = 0
    count = 0
    key_bowlers = []

    for bowler in xi:
        form = safe_float(bowler["form_score"], 5.0)
        # Boost for ranked bowlers
        rank_boost = 0
        if bowler["icc_rank_bowl"]:
            if bowler["icc_rank_bowl"] <= 5:  rank_boost = 1.5
            elif bowler["icc_rank_bowl"] <= 15: rank_boost = 0.8
            elif bowler["icc_rank_bowl"] <= 30: rank_boost = 0.3

        adjusted = min(10, form + rank_boost)
        total_score += adjusted
        count += 1

        name  = bowler["short_name"] or bowler["name"]
        trend = bowler["trend"] or "flat"
        arrow = {"up":"↑","flat":"→","down":"↓"}.get(trend, "→")

        key_bowlers.append({
            "name":   name,
            "form":   round(adjusted, 1),
            "style":  bowler["bowling_style"],
            "rank":   bowler["icc_rank_bowl"],
        })

        if adjusted >= 9.0:
            insights.append(f"{name} (ranked #{bowler['icc_rank_bowl']}) in top form {arrow}")
        elif adjusted >= 7.5:
            insights.append(f"{name} bowling well {arrow}")
        elif adjusted <= 4.0:
            insights.append(f"{name} poor bowling form — exploitable {arrow}")

    bowl_score = (total_score / count) if count > 0 else 5.0
    return round(min(10, max(0, bowl_score)), 2), key_bowlers, insights

def score_venue(conn, team, fmt, venue_id, match_id) -> tuple[float, list]:
    """
    Score key players' venue-specific records 0-10.
    If Rohit averages 89 at Edgbaston — strong positive signal.
    """
    insights = []

    xi = conn.execute("""
        SELECT p.player_id, p.short_name, p.name, p.role, p.is_key_player
        FROM playing_xi xi
        JOIN players p ON xi.player_id = p.player_id
        WHERE xi.match_id=? AND xi.team=? AND xi.is_available=1
    """, (match_id, team)).fetchall()

    if not xi:
        xi = conn.execute("""
            SELECT player_id, short_name, name, role, is_key_player
            FROM players WHERE team=? LIMIT 11
        """, (team,)).fetchall()

    if not xi:
        return 5.0, insights

    venue_scores = []

    for p in xi:
        vs = conn.execute("""
            SELECT avg_score, avg_sr, innings, highest_score,
                   fifties, hundreds, avg_last_3,
                   bowl_wickets, bowl_economy
            FROM player_venue_stats
            WHERE player_id=? AND venue_id=? AND format=?
        """, (p["player_id"], venue_id, fmt)).fetchone()

        if not vs or vs["innings"] < VENUE_MIN_INNINGS:
            continue

        name = p["short_name"] or p["name"]

        if p["role"] in ("bat","wk","all") and vs["avg_score"]:
            avg = vs["avg_score"]
            # Compare to format average benchmarks
            fmt_bench = {"ODI": 35.0, "T20I": 28.0, "T20": 28.0, "Test": 42.0}
            bench = fmt_bench.get(fmt, 35.0)
            ratio = avg / bench
            v_score = min(10, max(0, 5 * ratio))
            venue_scores.append(v_score)

            if avg >= bench * 1.5:
                insights.append(f"{name} avg {avg:.0f} here ({vs['innings']} innings) — outstanding venue record")
            elif avg >= bench * 1.2:
                insights.append(f"{name} avg {avg:.0f} here — strong venue record")
            elif avg < bench * 0.6:
                insights.append(f"{name} avg {avg:.0f} here — struggles at this ground")

        if p["role"] in ("bowl","all") and vs["bowl_wickets"] and vs["bowl_wickets"] >= 3:
            eco = vs["bowl_economy"]
            eco_bench = {"ODI": 6.0, "T20I": 8.0, "T20": 8.0, "Test": 2.8}
            bench = eco_bench.get(fmt, 6.0)
            v_score = min(10, max(0, 5 * (bench / eco))) if eco else 5.0
            venue_scores.append(v_score)

            if eco and eco < bench * 0.85:
                insights.append(f"{name} economy {eco:.1f} here — very effective at this ground")

    if not venue_scores:
        return 5.0, insights

    return round(sum(venue_scores) / len(venue_scores), 2), insights

def score_matchups(conn, team_a, team_b, fmt, match_id) -> tuple[float, list]:
    """
    Score head-to-head player matchups 0-10 from team_a's perspective.
    High score = team_a batters have edge over team_b bowlers AND
                 team_a bowlers have edge over team_b batters.
    """
    insights = []

    # Get team_a batters vs team_b bowlers
    matchups = conn.execute("""
        SELECT pvp.*,
               bp.short_name AS batter_name,
               bwp.short_name AS bowler_name
        FROM player_vs_player pvp
        JOIN players bp  ON pvp.batter_id = bp.player_id
        JOIN players bwp ON pvp.bowler_id = bwp.player_id
        WHERE bp.team=? AND bwp.team=? AND pvp.format=?
          AND pvp.balls >= 12
    """, (team_a, team_b, fmt)).fetchall()

    # Get team_b batters vs team_a bowlers (for team_a bowling edge)
    reverse_matchups = conn.execute("""
        SELECT pvp.*,
               bp.short_name AS batter_name,
               bwp.short_name AS bowler_name
        FROM player_vs_player pvp
        JOIN players bp  ON pvp.batter_id = bp.player_id
        JOIN players bwp ON pvp.bowler_id = bwp.player_id
        WHERE bp.team=? AND bwp.team=? AND pvp.format=?
          AND pvp.balls >= 12
    """, (team_b, team_a, fmt)).fetchall()

    if not matchups and not reverse_matchups:
        return 5.0, insights

    a_edge = 0    # positive = team_a advantage
    count  = 0

    # Team_a batting vs team_b bowling
    for m in matchups:
        bat = m["batter_name"] or "batter"
        bowl= m["bowler_name"] or "bowler"

        if m["bowler_dominates"]:
            a_edge -= 1
            insights.append(f"{bowl} (ENG) dominates {bat}: {m['dismissals']} dismissals in {m['balls']} balls")
        elif m["batter_dominates"]:
            a_edge += 1
            insights.append(f"{bat} (IND) has edge over {bowl}: SR {m['strike_rate']:.0f}")
        count += 1

    # Team_a bowling vs team_b batting (reversed)
    for m in reverse_matchups:
        bat = m["batter_name"] or "batter"
        bowl= m["bowler_name"] or "bowler"

        if m["bowler_dominates"]:
            a_edge += 1  # team_a bowler dominates team_b batter = good for team_a
            insights.append(f"{bowl} (IND) dominates {bat}: {m['dismissals']} dismissals in {m['balls']} balls")
        elif m["batter_dominates"]:
            a_edge -= 1
            insights.append(f"{bat} (ENG) has edge over {bowl}: SR {m['strike_rate']:.0f}")
        count += 1

    if count == 0:
        return 5.0, insights

    # Convert edge to 0-10 score
    ratio = a_edge / count                     # -1 to +1 range
    score = 5.0 + (ratio * 2.5)               # 2.5 to 7.5 range
    return round(min(9.5, max(0.5, score)), 2), insights

def score_availability(conn, team, match_id) -> tuple[float, list]:
    """
    Score team availability 0-10.
    Full squad = 9.0. Missing key player(s) = significant drop.
    """
    insights = []

    xi_all = conn.execute("""
        SELECT xi.*, p.is_key_player, p.short_name, p.name, p.role
        FROM playing_xi xi
        JOIN players p ON xi.player_id = p.player_id
        WHERE xi.match_id=? AND xi.team=?
    """, (match_id, team)).fetchall()

    if not xi_all:
        return 4.0, ["Playing XI not confirmed yet — defaulting to 4.0"]

    unavailable = [p for p in xi_all if not p["is_available"]]
    key_missing = [p for p in unavailable if p["is_key_player"]]

    score = 9.0  # start high — confirmed XI

    for p in key_missing:
        name = p["short_name"] or p["name"]
        note = p["injury_note"] or "unavailable"
        score -= 2.5  # key player missing = -2.5
        insights.append(f"⚠ {name} OUT — {note}")

    for p in [p for p in unavailable if not p["is_key_player"]]:
        name = p["short_name"] or p["name"]
        score -= 0.8
        insights.append(f"{name} not playing")

    if not unavailable:
        insights.append("Full squad available ✓")

    return round(max(0.5, min(10.0, score)), 2), insights

def score_form(conn, team, fmt, match_id) -> tuple[float, list]:
    """
    Score team's overall recent form 0-10.
    Weighted average of key players' form scores.
    """
    insights = []

    xi = conn.execute("""
        SELECT p.player_id, p.short_name, p.name, p.is_key_player, p.role,
               pf.form_score, pf.trend, pf.peak_recent
        FROM playing_xi xi
        JOIN players p ON xi.player_id = p.player_id
        LEFT JOIN player_form pf ON pf.player_id = p.player_id AND pf.format=?
        WHERE xi.match_id=? AND xi.team=? AND xi.is_available=1
    """, (fmt, match_id, team)).fetchall()

    if not xi:
        xi = conn.execute("""
            SELECT p.player_id, p.short_name, p.name, p.is_key_player, p.role,
                   pf.form_score, pf.trend, pf.peak_recent
            FROM players p
            LEFT JOIN player_form pf ON pf.player_id = p.player_id AND pf.format=?
            WHERE p.team=?
        """, (fmt, team)).fetchall()

    if not xi:
        return 5.0, insights

    total = 0
    count = 0
    hot_players = []
    cold_players = []

    for p in xi:
        fs = safe_float(p["form_score"], 5.0)
        total += fs
        count += 1
        name = p["short_name"] or p["name"]
        trend= p["trend"] or "flat"

        if fs >= 8.5 and p["is_key_player"]:
            hot_players.append(f"{name}({fs:.1f})")
        elif fs <= 4.0 and p["is_key_player"]:
            cold_players.append(f"{name}({fs:.1f})")

    if hot_players:
        insights.append(f"In-form key players: {', '.join(hot_players)}")
    if cold_players:
        insights.append(f"Out of form: {', '.join(cold_players)}")

    form_avg = (total / count) if count > 0 else 5.0
    return round(min(10, max(0, form_avg)), 2), insights

# ── Master signal function ────────────────────────────────────

def get_player_signal(
    match_id:  str,
    team_a:    str,
    team_b:    str,
    fmt:       str,
    venue_id:  str,
    gender:    str = "male",
) -> PlayerSignal:
    """
    Main entry point. Returns PlayerSignal with all scores and insights.
    Called by decision_engine.py to get the players factor.
    """
    signal = PlayerSignal(
        match_id = match_id,
        team_a   = team_a,
        team_b   = team_b,
        format   = fmt,
        venue_id = venue_id,
    )

    conn = get_conn()
    if conn is None:
        signal.key_insights = ["Player DB not found — using neutral score 5.0"]
        signal.data_quality = "none"
        return signal

    # ── Score Team A ──────────────────────────────────────────
    ta = TeamSignal(team=team_a)
    ta.batting_score,  ta.key_batters,  bat_ins  = score_batting(conn, team_a, fmt, match_id)
    ta.bowling_score,  ta.key_bowlers,  bowl_ins = score_bowling(conn, team_a, fmt, match_id)
    ta.form_score,     form_ins_a                = score_form(conn, team_a, fmt, match_id)
    ta.venue_score,    venue_ins_a               = score_venue(conn, team_a, fmt, venue_id, match_id)
    ta.avail_score,    ta.injuries               = score_availability(conn, team_a, match_id)
    ta.matchup_score,  matchup_ins               = score_matchups(conn, team_a, team_b, fmt, match_id)
    ta.insights = bat_ins + bowl_ins + form_ins_a + venue_ins_a + ta.injuries
    ta.overall  = round(
        ta.batting_score  * WEIGHTS["batting"]  +
        ta.bowling_score  * WEIGHTS["bowling"]  +
        ta.form_score     * WEIGHTS["form"]     +
        ta.venue_score    * WEIGHTS["venue"]    +
        ta.matchup_score  * WEIGHTS["matchups"] +
        ta.avail_score    * WEIGHTS["availability"],
        2
    )
    signal.team_a_signal = ta

    # ── Score Team B ──────────────────────────────────────────
    tb = TeamSignal(team=team_b)
    tb.batting_score, tb.key_batters, _   = score_batting(conn, team_b, fmt, match_id)
    tb.bowling_score, tb.key_bowlers, _   = score_bowling(conn, team_b, fmt, match_id)
    tb.form_score,    _                   = score_form(conn, team_b, fmt, match_id)
    tb.venue_score,   venue_ins_b         = score_venue(conn, team_b, fmt, venue_id, match_id)
    tb.avail_score,   tb.injuries         = score_availability(conn, team_b, match_id)
    tb.matchup_score  = 10.0 - ta.matchup_score   # mirror of team_a matchup
    tb.insights = venue_ins_b + tb.injuries
    tb.overall  = round(
        tb.batting_score  * WEIGHTS["batting"]  +
        tb.bowling_score  * WEIGHTS["bowling"]  +
        tb.form_score     * WEIGHTS["form"]     +
        tb.venue_score    * WEIGHTS["venue"]    +
        tb.matchup_score  * WEIGHTS["matchups"] +
        tb.avail_score    * WEIGHTS["availability"],
        2
    )
    signal.team_b_signal = tb

    # ── Compute final signal factor (team_a perspective) ──────
    # 5.0 = even, >5 = team_a has player advantage
    delta = ta.overall - tb.overall          # -10 to +10
    signal.signal_factor = round(5.0 + delta * 0.45, 2)
    signal.signal_factor = max(1.0, min(9.5, signal.signal_factor))

    # ── EV adjustment ─────────────────────────────────────────
    # Scales linearly from -MAX to +MAX based on how far from 5.0
    ev_scale = (signal.signal_factor - 5.0) / 5.0   # -1 to +1
    signal.signal_ev_adj = round(ev_scale * MAX_EV_ADJUSTMENT, 2)

    # ── Data quality ──────────────────────────────────────────
    has_xi     = conn.execute(
        "SELECT COUNT(*) FROM playing_xi WHERE match_id=?", (match_id,)
    ).fetchone()[0] > 0
    has_pvp    = conn.execute(
        "SELECT COUNT(*) FROM player_vs_player WHERE format=?", (fmt,)
    ).fetchone()[0] > 0
    has_venue  = conn.execute(
        "SELECT COUNT(*) FROM player_venue_stats WHERE venue_id=?", (venue_id,)
    ).fetchone()[0] > 0
    quality_score = sum([has_xi, has_pvp, has_venue])
    signal.data_quality = ["low","medium","medium","high"][quality_score]

    # ── Compile key insights ───────────────────────────────────
    all_insights = matchup_ins + ta.insights[:4] + tb.insights[:2]
    signal.key_insights = all_insights[:8]   # max 8 insights

    # ── Save to DB ────────────────────────────────────────────
    try:
        conn.execute("""
            INSERT OR REPLACE INTO player_signal
            (match_id, computed_at,
             team_a, team_b, format, venue_id,
             team_a_batting_score, team_a_bowling_score, team_a_venue_score,
             team_a_form_score, team_a_matchup_score, team_a_availability, team_a_overall,
             team_b_batting_score, team_b_bowling_score, team_b_venue_score,
             team_b_form_score, team_b_matchup_score, team_b_availability, team_b_overall,
             signal_factor, signal_ev_adj, key_insights)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            match_id, datetime.now().isoformat(),
            team_a, team_b, fmt, venue_id,
            ta.batting_score, ta.bowling_score, ta.venue_score,
            ta.form_score, ta.matchup_score, ta.avail_score, ta.overall,
            tb.batting_score, tb.bowling_score, tb.venue_score,
            tb.form_score, tb.matchup_score, tb.avail_score, tb.overall,
            signal.signal_factor, signal.signal_ev_adj,
            json.dumps(signal.key_insights)
        ))
        conn.commit()
    except Exception:
        pass

    conn.close()
    return signal

# ── Pretty print ──────────────────────────────────────────────

def print_signal(s: PlayerSignal):
    ta = s.team_a_signal
    tb = s.team_b_signal
    bar = lambda v: "█"*int(v) + "░"*(10-int(v))

    print(f"\n{'='*62}")
    print(f"  PLAYER SIGNAL: {s.team_a} vs {s.team_b} [{s.format}]")
    print(f"  Data quality: {s.data_quality.upper()}")
    print(f"{'='*62}")

    print(f"\n  {'Factor':<22} {s.team_a:<18} {s.team_b}")
    print(f"  {'─'*58}")
    factors = [
        ("Batting",      ta.batting_score,  tb.batting_score),
        ("Bowling",      ta.bowling_score,  tb.bowling_score),
        ("Form",         ta.form_score,     tb.form_score),
        ("Venue record", ta.venue_score,    tb.venue_score),
        ("Matchups",     ta.matchup_score,  tb.matchup_score),
        ("Availability", ta.avail_score,    tb.avail_score),
        ("OVERALL",      ta.overall,        tb.overall),
    ]
    for name, a_v, b_v in factors:
        winner = "◀" if a_v > b_v else "▶" if b_v > a_v else "="
        sep = "═" if name == "OVERALL" else " "
        print(f"  {name:<22} {a_v:>4.1f}  {sep*12}  {b_v:>4.1f}  {winner}")

    print(f"\n  SIGNAL FACTOR:   {s.signal_factor:.1f}/10  "
          f"({'advantage ' + s.team_a if s.signal_factor > 5.5 else 'advantage ' + s.team_b if s.signal_factor < 4.5 else 'even'})")
    print(f"  EV ADJUSTMENT:   {s.signal_ev_adj:+.1f}% for {s.team_a}")

    if s.key_insights:
        print(f"\n  KEY INSIGHTS:")
        for ins in s.key_insights:
            print(f"    • {ins}")

    if ta.key_batters:
        print(f"\n  {s.team_a} key batters:")
        for b in ta.key_batters[:4]:
            arr = {"up":"↑","flat":"→","down":"↓"}.get(b["trend"],"→")
            avg = f"avg {b['l5avg']}" if b['l5avg'] else ""
            print(f"    {b['name']:<16} form {b['form']}/10 {arr}  {avg}")

    if ta.key_bowlers:
        print(f"\n  {s.team_a} bowling attack:")
        for b in ta.key_bowlers[:3]:
            rank = f"rank #{b['rank']}" if b['rank'] else ""
            print(f"    {b['name']:<16} {b['style']:<6} form {b['form']}/10  {rank}")

    if tb.injuries:
        print(f"\n  {s.team_b} availability:")
        for ins in tb.injuries:
            print(f"    {ins}")

    print(f"{'='*62}\n")

# ── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nRunning player signal engine...")

    # Test 1 — Today's match: India vs England 1st ODI
    s1 = get_player_signal(
        match_id = "20260714-IND-ENG-ODI-1STODI",
        team_a   = "India",
        team_b   = "England",
        fmt      = "ODI",
        venue_id = "edgbaston-birmingham",
    )
    print_signal(s1)

    # Test 2 — Jul 16 Cardiff (no playing XI entered yet)
    s2 = get_player_signal(
        match_id = "20260716-IND-ENG-ODI-2NDODI",
        team_a   = "India",
        team_b   = "England",
        fmt      = "ODI",
        venue_id = "sophia-gardens-cardiff",
    )
    print_signal(s2)

    # Test 3 — WI vs NZ today
    s3 = get_player_signal(
        match_id = "20260714-WI-NZ-ODI-2NDODI",
        team_a   = "West Indies",
        team_b   = "New Zealand",
        fmt      = "ODI",
        venue_id = "providence-stadium-provi",
    )
    print_signal(s3)
