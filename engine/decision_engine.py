"""
decision_engine.py
Core betting decision engine.
Input:  match_id + current bankroll + decimal odds + estimated win probability
Output: confidence score, Kelly stake, verdict, reason
"""
import sqlite3, os, math
from datetime import date, datetime
from dataclasses import dataclass, field
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")

# ── Factor weights (sum to 1.0) ───────────────────────────────
WEIGHTS = {
    "value_edge":   0.22,
    "form":         0.14,
    "h2h":          0.10,
    "venue":        0.10,
    "weather":      0.10,
    "players":      0.10,
    "market":       0.08,
    "importance":   0.07,
    "volatility":   0.06,
    "toss":         0.03,
}

# ── Verdict thresholds ────────────────────────────────────────
THRESHOLDS = {
    "BET":    72,
    "REDUCE": 52,
    "SKIP":   35,
}

@dataclass
class MatchContext:
    match_id:        str
    date:            str
    label:           str
    team_a:          str
    team_b:          str
    format:          str
    category:        str
    gender:          str
    venue_id:        str
    city:            str
    step:            int
    phase:           int
    bankroll:        float
    decimal_odds:    float
    win_prob:        float          # your estimated probability 0-1
    # optional overrides
    player_status:   str = "unknown"   # full/minor-a/minor-b/major-a/major-b/unknown
    importance:      str = "medium"    # high/medium/low
    toss_impact:     str = "medium"    # high/medium/low/unknown
    notes:           str = ""

@dataclass
class FactorScores:
    value_edge:  float = 0
    form:        float = 0
    h2h:         float = 0
    venue:       float = 0
    weather:     float = 0
    players:     float = 0
    market:      float = 0
    importance:  float = 0
    volatility:  float = 0
    toss:        float = 0

@dataclass
class Decision:
    match_id:          str
    label:             str
    team_a:            str
    team_b:            str
    confidence_score:  float
    ev_pct:            float
    kelly_pct:         float
    recommended_stake: float
    verdict:           str
    verdict_reason:    str
    factor_scores:     FactorScores
    override_applied:  bool = False
    override_reason:   str = ""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ── Individual factor scorers ─────────────────────────────────

def score_value_edge(decimal_odds: float, win_prob: float) -> tuple[float, float]:
    """Returns (factor_score 0-10, ev_pct)"""
    implied = 1 / decimal_odds
    ev = (win_prob * decimal_odds) - 1
    ev_pct = ev * 100
    if ev <= 0:
        return max(0, 3 + ev * 10), ev_pct
    score = min(10, 5 + ev * 15)
    return round(score, 2), round(ev_pct, 2)

def score_form(ctx: MatchContext, conn) -> float:
    fmt_map = {"ODI":"ODI","T20I":"T20I","T20":"T20I","100-ball":"T20I","Test":"Test"}
    fmt = fmt_map.get(ctx.format, "ODI")

    def get_form(team):
        row = conn.execute("""
            SELECT form_score FROM team_form
            WHERE team_id LIKE ? AND format=?
            ORDER BY as_of_date DESC LIMIT 1
        """, (f"%{team.lower().replace(' ','-')}%", fmt)).fetchone()
        if row: return row["form_score"]
        row2 = conn.execute("""
            SELECT form_score FROM team_form
            WHERE LOWER(team_id) LIKE ? ORDER BY as_of_date DESC LIMIT 1
        """, (f"%{team[:4].lower()}%",)).fetchone()
        return row2["form_score"] if row2 else 5.5

    fa = get_form(ctx.team_a)
    fb = get_form(ctx.team_b)
    diff = fa - fb
    # positive = team_a has better form = higher confidence if betting team_a
    score = min(10, max(0, 5 + diff * 0.8))
    return round(score, 2)

def score_h2h(ctx: MatchContext, conn) -> float:
    fmt_map = {"ODI":"ODI","T20I":"T20I","T20":"T20I","100-ball":"T20I","Test":"Test"}
    fmt = fmt_map.get(ctx.format, "ODI")
    gender = "female" if "Women" in ctx.gender else "male"

    row = conn.execute("""
        SELECT team_a_win_pct, last_5_team_a_wins, matches_played
        FROM h2h
        WHERE (team_a=? AND team_b=? OR team_a=? AND team_b=?)
          AND format=? AND gender=?
        ORDER BY last_match_date DESC LIMIT 1
    """, (ctx.team_a, ctx.team_b, ctx.team_b, ctx.team_a, fmt, gender)).fetchone()

    if not row or row["matches_played"] < 5:
        return 5.0  # neutral — insufficient data

    pct = row["team_a_win_pct"] or 50
    l5  = row["last_5_team_a_wins"] or 2
    # scale: 50% pct → 5.0, 80% → 8.0, 20% → 2.0
    score = min(10, max(0, (pct / 10) + (l5 - 2.5) * 0.5))
    return round(score, 2)

def score_venue(ctx: MatchContext, conn) -> float:
    fmt_map = {"ODI":"ODI","T20I":"T20I","T20":"T20","100-ball":"T20","Test":"Test"}
    fmt = fmt_map.get(ctx.format, "T20")
    gender = "female" if "Women" in ctx.gender else "male"

    row = conn.execute("""
        SELECT bat_first_win_pct, toss_advantage_pct, matches_played
        FROM venue_stats
        WHERE venue_id=? AND format=? AND gender=?
        LIMIT 1
    """, (ctx.venue_id, fmt, gender)).fetchone()

    if not row or row["matches_played"] < 5:
        # try any format at venue
        row = conn.execute("""
            SELECT bat_first_win_pct, toss_advantage_pct, matches_played
            FROM venue_stats WHERE venue_id=? LIMIT 1
        """, (ctx.venue_id,)).fetchone()

    if not row:
        return 5.5

    # Venue with more data = more reliable = higher confidence
    data_richness = min(10, row["matches_played"] / 8)
    pct = row["bat_first_win_pct"] or 50
    # Clearer bat-first/second signal = easier to model = higher score
    signal = abs(pct - 50) / 5
    score = min(10, (data_richness * 0.5) + (signal * 0.5) + 4)
    return round(score, 2)

def score_weather(ctx: MatchContext, conn) -> float:
    row = conn.execute("""
        SELECT rain_prob_pct, cloud_cover_pct, wind_kmh, dl_risk, condition
        FROM weather
        WHERE venue_id=? AND match_date=?
        ORDER BY fetched_at DESC LIMIT 1
    """, (ctx.venue_id, ctx.date)).fetchone()

    if not row:
        return 4.0  # unknown = lower confidence

    rain = row["rain_prob_pct"] or 0
    cloud = row["cloud_cover_pct"] or 0
    dl = row["dl_risk"]

    if dl == "high" or rain >= 70:    return 1.0   # near-certain D/L risk
    if dl == "medium" or rain >= 40:  return 3.5
    if cloud >= 70:                   return 5.5   # swing conditions
    if cloud <= 30 and rain <= 10:    return 9.0   # ideal
    return 7.0

def score_players(status: str) -> float:
    return {
        "full":    9.0,
        "minor-a": 7.0,
        "minor-b": 7.5,
        "major-a": 3.5,
        "major-b": 4.5,
        "unknown": 4.0,
    }.get(status, 4.0)

def score_market(ctx: MatchContext) -> float:
    liq = {"International": 8.5, "ICC Event": 9.0,
           "Franchise": 6.5, "Domestic": 5.0, "ACC": 4.5}
    return liq.get(ctx.category, 5.5)

def score_importance(importance: str) -> float:
    return {"high": 8.5, "medium": 6.0, "low": 4.0}.get(importance, 6.0)

def score_volatility(ctx: MatchContext, conn) -> float:
    """Lower team volatility = higher score (more predictable)"""
    fmt_map = {"ODI":"ODI","T20I":"T20I","T20":"T20I","100-ball":"T20I","Test":"Test"}
    fmt = fmt_map.get(ctx.format, "ODI")

    def get_vol(team):
        row = conn.execute("""
            SELECT last_5_win_pct, last_10_win_pct FROM team_form
            WHERE team_id LIKE ? AND format=?
            ORDER BY as_of_date DESC LIMIT 1
        """, (f"%{team[:4].lower()}%", fmt)).fetchone()
        if not row: return 5.0
        # consistency = closeness of last5 and last10
        diff = abs((row["last_5_win_pct"] or 50) - (row["last_10_win_pct"] or 50))
        return min(10, max(0, 8 - diff / 8))

    va = get_vol(ctx.team_a)
    vb = get_vol(ctx.team_b)
    return round((va + vb) / 2, 2)

def score_toss(toss_impact: str) -> float:
    return {"low": 8.0, "medium": 6.0, "high": 3.0, "unknown": 4.5}.get(toss_impact, 6.0)

# ── Kelly calculator ──────────────────────────────────────────

def kelly_stake(decimal_odds: float, win_prob: float, bankroll: float, phase: int) -> tuple[float, float]:
    b = decimal_odds - 1
    p = win_prob
    q = 1 - p
    kelly_full = (b * p - q) / b if b > 0 else 0
    fraction = 0.25 if phase == 1 else 0.125
    kelly_frac = max(0, kelly_full * fraction)
    stake = round(bankroll * kelly_frac, 2)
    return round(kelly_frac * 100, 2), stake

# ── Hard override rules ───────────────────────────────────────

def apply_overrides(decision: Decision, ctx: MatchContext, conn) -> Decision:
    reasons = []

    # 1. Rain risk
    row = conn.execute("""
        SELECT rain_prob_pct, dl_risk FROM weather
        WHERE venue_id=? AND match_date=?
        ORDER BY fetched_at DESC LIMIT 1
    """, (ctx.venue_id, ctx.date)).fetchone()
    if row and row["rain_prob_pct"] >= 70:
        decision.verdict = "SKIP"
        reasons.append(f"Rain probability {row['rain_prob_pct']:.0f}% — D/L risk too high")

    # 2. Key player out
    if ctx.player_status in ("major-a", "major-b"):
        team = ctx.team_a if ctx.player_status == "major-a" else ctx.team_b
        decision.recommended_stake = round(decision.recommended_stake * 0.4, 2)
        reasons.append(f"Key player unavailable for {team} — stake reduced 60%")

    # 3. No positive EV
    if decision.ev_pct <= 0:
        decision.verdict = "SKIP"
        reasons.append(f"No positive edge: EV={decision.ev_pct:.1f}% — bookmaker has edge")

    # 4. Low liquidity markets
    if ctx.category in ("ACC", "Domestic") and decision.verdict == "BET":
        decision.verdict = "REDUCE"
        decision.recommended_stake = round(decision.recommended_stake * 0.6, 2)
        reasons.append(f"Low liquidity ({ctx.category}) — stake reduced 40%")

    if reasons:
        decision.override_applied = True
        decision.override_reason = " | ".join(reasons)

    return decision

# ── Master decision function ──────────────────────────────────

def decide(ctx: MatchContext) -> Decision:
    conn = get_conn()

    fs = FactorScores()
    fs.value_edge, ev_pct = score_value_edge(ctx.decimal_odds, ctx.win_prob)
    fs.form        = score_form(ctx, conn)
    fs.h2h         = score_h2h(ctx, conn)
    fs.venue       = score_venue(ctx, conn)
    fs.weather     = score_weather(ctx, conn)
    fs.players     = score_players(ctx.player_status)
    fs.market      = score_market(ctx)
    fs.importance  = score_importance(ctx.importance)
    fs.volatility  = score_volatility(ctx, conn)
    fs.toss        = score_toss(ctx.toss_impact)

    raw = sum(getattr(fs, k) * w for k, w in WEIGHTS.items())
    confidence = round(min(100, max(0, raw * 10)), 1)

    kelly_pct, stake = kelly_stake(ctx.decimal_odds, ctx.win_prob, ctx.bankroll, ctx.phase)

    if confidence >= THRESHOLDS["BET"] and ev_pct > 0:
        verdict = "BET"
        reason = f"Strong edge (EV={ev_pct:.1f}%) with confidence {confidence}/100"
    elif confidence >= THRESHOLDS["REDUCE"] and ev_pct > 0:
        verdict = "REDUCE"
        stake   = round(stake * 0.5, 2)
        reason  = f"Positive edge but uncertain conditions — half stake"
    elif confidence >= THRESHOLDS["SKIP"]:
        verdict = "SKIP"
        stake   = 0
        reason  = f"Confidence {confidence}/100 below bet threshold — skip"
    else:
        verdict = "SKIP"
        stake   = 0
        reason  = f"Low confidence {confidence}/100 — insufficient edge"

    decision = Decision(
        match_id=ctx.match_id,
        label=ctx.label,
        team_a=ctx.team_a,
        team_b=ctx.team_b,
        confidence_score=confidence,
        ev_pct=ev_pct,
        kelly_pct=kelly_pct,
        recommended_stake=stake,
        verdict=verdict,
        verdict_reason=reason,
        factor_scores=fs,
    )

    decision = apply_overrides(decision, ctx, conn)

    # Save to DB
    conn.execute("""
        INSERT OR REPLACE INTO confidence_scores
        (match_id, computed_at,
         score_value_edge, score_form, score_h2h, score_venue,
         score_weather, score_toss, score_players, score_market,
         score_importance, score_volatility,
         confidence_score, ev_pct, kelly_pct, recommended_stake,
         verdict, verdict_reason)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (ctx.match_id, datetime.now().isoformat(),
          fs.value_edge, fs.form, fs.h2h, fs.venue,
          fs.weather, fs.toss, fs.players, fs.market,
          fs.importance, fs.volatility,
          confidence, ev_pct, kelly_pct, stake,
          decision.verdict, decision.verdict_reason + (
              f" | OVERRIDE: {decision.override_reason}" if decision.override_applied else ""
          )))
    conn.commit()
    conn.close()

    return decision

if __name__ == "__main__":
    # Quick test with today's first match
    conn = get_conn()
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT * FROM matches WHERE date=? ORDER BY step LIMIT 1", (today,)
    ).fetchone()
    conn.close()

    if not row:
        print(f"No matches today ({today}). Using Jul 14 2026 test match.")
        row_date = "2026-07-14"
        conn2 = get_conn()
        row = conn2.execute(
            "SELECT * FROM matches WHERE date=? ORDER BY step LIMIT 1", (row_date,)
        ).fetchone()
        conn2.close()

    if row:
        ctx = MatchContext(
            match_id=row["match_id"],
            date=row["date"],
            label=row["label"],
            team_a=row["team_a"],
            team_b=row["team_b"],
            format=row["format"],
            category=row["category"],
            gender=row["gender"],
            venue_id=row["venue_id"],
            city=row["city"],
            step=row["step"],
            phase=row["phase"],
            bankroll=5000.0,
            decimal_odds=1.90,
            win_prob=0.55,
            player_status="full",
            importance="medium",
            toss_impact="medium",
        )
        d = decide(ctx)
        print(f"\n{'='*60}")
        print(f"MATCH:      {d.team_a} vs {d.team_b} — {d.label}")
        print(f"CONFIDENCE: {d.confidence_score}/100")
        print(f"EV:         {d.ev_pct:+.1f}%")
        print(f"KELLY:      {d.kelly_pct:.1f}%")
        print(f"STAKE:      €{d.recommended_stake:,.2f}")
        print(f"VERDICT:    {d.verdict}")
        print(f"REASON:     {d.verdict_reason}")
        if d.override_applied:
            print(f"OVERRIDE:   {d.override_reason}")
        print(f"\nFactor breakdown:")
        for k, w in WEIGHTS.items():
            s = getattr(d.factor_scores, k)
            bar = "█" * int(s) + "░" * (10 - int(s))
            print(f"  {k:14s} [{bar}] {s:4.1f}  (weight {w:.0%})")
        print("="*60)
