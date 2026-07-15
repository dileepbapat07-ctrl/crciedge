"""
elo_engine/ratings.py
======================
Helper functions called by the decision engine.
Provides:
  - get_elo(team, gender, format) → float
  - get_elo_delta(team_a, team_b, gender, format, venue_country) → float
  - get_elo_factor(team_a, team_b, gender, format, venue_country) → float (0-10)
  - get_h2h_factor(team_a, team_b, gender, format) → float (0-10)
  - get_combined_factor(team_a, team_b, gender, format, venue_country) → float (0-10)
"""

import sqlite3, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from elo_config import elo_delta_to_score, expected_score, HOME_ADVANTAGE

DB_PATH = os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_elo(team: str, gender: str = "male", fmt: str = "ODI") -> float:
    """Get current ELO rating for a team. Returns 1500 if not found."""
    conn = _conn()
    row = conn.execute("""
        SELECT rating FROM elo_ratings
        WHERE team_id=? AND gender=? AND format=?
    """, (team, gender, fmt)).fetchone()
    conn.close()
    return row["rating"] if row else 1500.0

def get_elo_delta(team_a: str, team_b: str,
                  gender: str = "male", fmt: str = "ODI",
                  venue_country: str = "") -> dict:
    """
    Returns ELO comparison dict with:
      - delta: team_a ELO minus team_b ELO (adjusted for home advantage)
      - win_prob: probability team_a wins (from ELO)
      - rating_a / rating_b: raw ratings
      - home_team: who has home advantage (if any)
    """
    conn = _conn()

    def get_r(team):
        row = conn.execute("""
            SELECT rating FROM elo_ratings
            WHERE team_id=? AND gender=? AND format=?
        """, (team, gender, fmt)).fetchone()
        return row["rating"] if row else 1500.0

    ra = get_r(team_a)
    rb = get_r(team_b)

    # Detect home advantage
    from elo_config import HOME_COUNTRY_MAP, norm
    home_team = None
    if venue_country:
        for team, countries in HOME_COUNTRY_MAP.items():
            nt = norm(team)
            if venue_country in countries:
                if nt == team_a:
                    home_team = team_a
                elif nt == team_b:
                    home_team = team_b
                break

    win_prob = expected_score(ra, rb, home_team, team_a)
    delta = ra - rb + (HOME_ADVANTAGE if home_team == team_a else
                      -HOME_ADVANTAGE if home_team == team_b else 0)

    conn.close()
    return {
        "rating_a":  round(ra, 1),
        "rating_b":  round(rb, 1),
        "delta":     round(delta, 1),
        "win_prob":  round(win_prob, 4),
        "home_team": home_team,
    }

def get_elo_factor(team_a: str, team_b: str,
                   gender: str = "male", fmt: str = "ODI",
                   venue_country: str = "") -> float:
    """
    ELO-based confidence factor (0–10) for use in decision engine.
    Replaces the old H2H factor.
    5.0 = equal teams, 9.0 = strong favourite, 1.0 = heavy underdog.
    """
    result = get_elo_delta(team_a, team_b, gender, fmt, venue_country)
    return elo_delta_to_score(result["delta"])

def get_h2h_factor(team_a: str, team_b: str,
                   gender: str = "male", fmt: str = "ODI") -> float:
    """
    H2H-based factor from h2h_full table (0–10).
    Weights recent results (last 5) more heavily than overall.
    Returns 5.0 if no H2H data found.
    """
    conn = _conn()
    # Try both orderings
    row = conn.execute("""
        SELECT * FROM h2h_full
        WHERE ((team_a=? AND team_b=?) OR (team_a=? AND team_b=?))
          AND gender=? AND format=?
    """, (team_a, team_b, team_b, team_a, gender, fmt)).fetchone()
    conn.close()

    if not row or row["matches_played"] < 3:
        return 5.0  # Insufficient data — neutral

    # Determine perspective (is team_a our "A" in the table?)
    if row["team_a"] == team_a:
        overall_pct = row["team_a_win_pct"] or 50
        recent_pct  = row["recent_a_pct"] or 50
        l5_wins     = row["last_5_a_wins"] or 0
        l5_played   = len([x for x in (row["last_5_results"] or "").split(",") if x in ("A","B")])
        streak_fav  = row["current_winner"] == team_a
    else:
        overall_pct = 100 - (row["team_a_win_pct"] or 50)
        recent_pct  = 100 - (row["recent_a_pct"] or 50)
        l5_results  = (row["last_5_results"] or "").split(",")
        l5_wins     = l5_results.count("B")
        l5_played   = len([x for x in l5_results if x in ("A","B")])
        streak_fav  = row["current_winner"] == team_a

    l5_pct = (l5_wins / l5_played * 100) if l5_played > 0 else 50

    # Weighted score: recent (40%) + last5 (40%) + overall (20%)
    weighted_pct = (recent_pct * 0.40) + (l5_pct * 0.40) + (overall_pct * 0.20)

    # Streak bonus/penalty
    streak = row["current_streak"] or 0
    streak_bonus = 0.3 * min(streak, 5) if streak_fav else -0.3 * min(streak, 5)

    # Convert to 0-10 scale
    score = (weighted_pct / 10) + streak_bonus
    return round(max(0.5, min(9.5, score)), 2)

def get_combined_factor(team_a: str, team_b: str,
                        gender: str = "male", fmt: str = "ODI",
                        venue_country: str = "") -> tuple[float, dict]:
    """
    Combined ELO + H2H factor for the decision engine.
    Returns (factor_score 0-10, details_dict)

    Weights: ELO 60% + H2H 40%
    (ELO dominates because it's more current and covers all matchups)
    """
    elo_f  = get_elo_factor(team_a, team_b, gender, fmt, venue_country)
    h2h_f  = get_h2h_factor(team_a, team_b, gender, fmt)
    elo_d  = get_elo_delta(team_a, team_b, gender, fmt, venue_country)

    combined = round(elo_f * 0.60 + h2h_f * 0.40, 2)

    return combined, {
        "elo_factor":    elo_f,
        "h2h_factor":    h2h_f,
        "combined":      combined,
        "rating_a":      elo_d["rating_a"],
        "rating_b":      elo_d["rating_b"],
        "elo_delta":     elo_d["delta"],
        "elo_win_prob":  elo_d["win_prob"],
        "home_team":     elo_d["home_team"],
    }

def print_matchup(team_a: str, team_b: str,
                  gender: str = "male", fmt: str = "ODI",
                  venue_country: str = ""):
    """Print a full matchup summary for debugging / daily brief."""
    factor, details = get_combined_factor(team_a, team_b, gender, fmt, venue_country)
    conn = _conn()
    h2h = conn.execute("""
        SELECT * FROM h2h_full
        WHERE ((team_a=? AND team_b=?) OR (team_a=? AND team_b=?))
          AND gender=? AND format=?
    """, (team_a, team_b, team_b, team_a, gender, fmt)).fetchone()
    conn.close()

    print(f"\n  ┌─────────────────────────────────────────────────┐")
    print(f"  │  {team_a} vs {team_b}  [{fmt}]")
    print(f"  │  Venue: {venue_country or 'neutral'}")
    print(f"  ├─────────────────────────────────────────────────┤")
    print(f"  │  ELO ratings:  {team_a} {details['rating_a']:.0f}  |  {team_b} {details['rating_b']:.0f}")
    print(f"  │  ELO delta:    {details['elo_delta']:+.0f}  →  {team_a} wins {details['elo_win_prob']:.1%}")
    if details['home_team']:
        print(f"  │  Home adv:     {details['home_team']} (+{HOME_ADVANTAGE} pts)")
    print(f"  │  ELO factor:   {details['elo_factor']:.1f}/10")
    if h2h:
        if h2h['team_a'] == team_a:
            print(f"  │  H2H overall:  {team_a} {h2h['team_a_wins']}–{h2h['team_b_wins']} {team_b}  ({h2h['team_a_win_pct']}%)")
            print(f"  │  Last 5:       {h2h['last_5_results']}  ({h2h['last_5_a_wins']}/5 {team_a})")
        else:
            print(f"  │  H2H overall:  {team_a} {h2h['team_b_wins']}–{h2h['team_a_wins']} {team_b}  ({100-(h2h['team_a_win_pct'] or 50):.1f}%)")
        print(f"  │  Streak:       {h2h['current_winner']} × {h2h['current_streak']}")
        print(f"  │  H2H factor:   {details['h2h_factor']:.1f}/10")
    else:
        print(f"  │  H2H:          No data — using neutral 5.0")
    print(f"  ├─────────────────────────────────────────────────┤")
    print(f"  │  COMBINED FACTOR: {factor:.1f}/10  (ELO 60% + H2H 40%)")
    print(f"  └─────────────────────────────────────────────────┘")

if __name__ == "__main__":
    # Quick test
    print_matchup("India", "England", "male", "ODI", "England")
    print_matchup("Trinbago KR", "Guyana AW", "male", "T20", "Trinidad")
    print_matchup("Perth Scorchers", "Melbourne Stars", "male", "T20", "Australia")
    print_matchup("Perth Scorchers W", "Sydney Sixers W", "female", "T20", "Australia")
