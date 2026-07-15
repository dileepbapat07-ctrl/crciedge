"""
elo_engine/updater.py
=====================
Run after each match result to update ELO ratings in real time.

USAGE:
  # After India beat England in the 1st ODI:
  python updater.py --date 2026-07-14 --team-a "India" --team-b "England" \
                    --winner "India" --format ODI --gender male \
                    --venue-country England --match-type bilateral

  # Or interactively:
  python updater.py --interactive
"""

import sqlite3, os, sys, argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from elo_config import (
    TEAM_NAME_MAP, INTERNATIONAL_TEAMS,
    elo_delta_to_score, expected_score, k_factor, update_elo,
    get_match_type, get_home_team, norm
)

DB_PATH = os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def get_rating(conn, team, gender, fmt):
    row = conn.execute("""
        SELECT rating FROM elo_ratings
        WHERE team_id=? AND gender=? AND format=?
    """, (team, gender, fmt)).fetchone()
    return row[0] if row else 1500.0

def update_match(conn, match_date, ta, tb, winner,
                 fmt, gender, venue_country, match_type, series=""):
    ta = norm(ta)
    tb = norm(tb)
    winner = norm(winner) if winner not in ("no_result","nr","no result") else "no_result"

    ra = get_rating(conn, ta, gender, fmt)
    rb = get_rating(conn, tb, gender, fmt)
    home_team = get_home_team(venue_country, ta, tb)

    ra_new, rb_new, k, ea, eb = update_elo(
        ra, rb, winner, ta, tb, home_team, match_type
    )

    now = datetime.now().isoformat()

    # Update ratings
    for team, r_old, r_new, opp, exp in [
        (ta, ra, ra_new, tb, ea),
        (tb, rb, rb_new, ta, eb),
    ]:
        result = ("win" if winner==team else "loss" if winner!="no_result" else "nr")
        team_type = "international" if team in INTERNATIONAL_TEAMS else "franchise"

        # Get current peak
        row = conn.execute("SELECT peak_rating, matches_played, wins, losses FROM elo_ratings WHERE team_id=? AND gender=? AND format=?", (team, gender, fmt)).fetchone()
        peak = max(row["peak_rating"] if row else 1500, r_new)
        played = (row["matches_played"] if row else 0) + 1
        wins   = (row["wins"] if row else 0) + (1 if result=="win" else 0)
        losses = (row["losses"] if row else 0) + (1 if result=="loss" else 0)

        conn.execute("""
            INSERT OR REPLACE INTO elo_ratings
            (team_id, team_type, gender, format, rating, matches_played,
             wins, losses, peak_rating, last_match_date,
             last_opponent, last_result, last_updated)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (team, team_type, gender, fmt, round(r_new,2),
              played, wins, losses, round(peak,2),
              match_date, opp, result, now))

        conn.execute("""
            INSERT INTO elo_history
            (match_date,team_id,gender,format,opponent,venue_country,
             home_away,rating_before,rating_after,rating_change,
             result,k_factor,expected_score,match_type)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (match_date, team, gender, fmt, opp, venue_country,
              "home" if home_team==team else "away" if home_team else "neutral",
              round(r_old,2), round(r_new,2), round(r_new-r_old,2),
              result, k, round(exp,4), match_type))

    # Update H2H
    h2h_key_a, h2h_key_b = sorted([ta, tb])
    row = conn.execute("""
        SELECT * FROM h2h_full
        WHERE team_a=? AND team_b=? AND gender=? AND format=?
    """, (h2h_key_a, h2h_key_b, gender, fmt)).fetchone()

    if row:
        ta_wins = row["team_a_wins"] + (1 if winner==h2h_key_a else 0)
        tb_wins = row["team_b_wins"] + (1 if winner==h2h_key_b else 0)
        nr      = row["no_results"]  + (1 if winner=="no_result" else 0)
        total   = ta_wins + tb_wins + nr
        # Update last 5
        prev_l5 = (row["last_5_results"] or "").split(",")
        new_result = ("A" if winner==h2h_key_a else "B" if winner==h2h_key_b else "N")
        new_l5 = (prev_l5 + [new_result])[-5:]
        l5_str = ",".join(new_l5)
        l5_a   = new_l5.count("A")
        # Streak
        streak = row["current_streak"] or 0
        cur_w  = row["current_winner"]
        if winner == "no_result":
            pass
        elif cur_w == winner:
            streak += 1
        else:
            cur_w = winner; streak = 1

        ta_pct = round(ta_wins/(total-nr)*100,1) if (total-nr)>0 else 50.0

        conn.execute("""
            UPDATE h2h_full SET
              matches_played=?, team_a_wins=?, team_b_wins=?, no_results=?,
              team_a_win_pct=?, last_5_results=?, last_5_a_wins=?,
              current_winner=?, current_streak=?,
              last_match_date=?, last_match_winner=?, last_updated=?
            WHERE team_a=? AND team_b=? AND gender=? AND format=?
        """, (total, ta_wins, tb_wins, nr, ta_pct,
              l5_str, l5_a, cur_w, streak,
              match_date, winner, now,
              h2h_key_a, h2h_key_b, gender, fmt))
    else:
        # New H2H record
        ta_wins = 1 if winner==h2h_key_a else 0
        tb_wins = 1 if winner==h2h_key_b else 0
        new_r = "A" if winner==h2h_key_a else "B" if winner==h2h_key_b else "N"
        conn.execute("""
            INSERT INTO h2h_full
            (team_a, team_b, gender, format, matches_played,
             team_a_wins, team_b_wins, no_results, team_a_win_pct,
             recent_played, recent_a_wins, recent_b_wins, recent_a_pct,
             last_5_results, last_5_a_wins,
             current_winner, current_streak,
             last_match_date, last_match_winner)
            VALUES (?,?,?,?,1,?,?,0,?,1,?,?,?,?,?,?,1,?,?)
        """, (h2h_key_a, h2h_key_b, gender, fmt,
              ta_wins, tb_wins,
              100.0 if ta_wins else 0.0,
              ta_wins, tb_wins,
              100.0 if ta_wins else 0.0,
              new_r, ta_wins,
              "A" if ta_wins else "B",
              match_date, winner))

    conn.commit()
    print(f"\n  ✅ Updated ELO ratings:")
    print(f"     {ta}: {ra:.1f} → {ra_new:.1f} ({ra_new-ra:+.1f})")
    print(f"     {tb}: {rb:.1f} → {rb_new:.1f} ({rb_new-rb:+.1f})")
    print(f"     K={k} | Expected: {ta} {ea:.1%} | {tb} {eb:.1%}")
    return ra_new, rb_new

def interactive():
    print("\n  ELO UPDATER — Interactive mode")
    print("  Enter match result to update ratings\n")
    conn = get_conn()
    date   = input("  Match date (YYYY-MM-DD): ").strip() or datetime.today().strftime("%Y-%m-%d")
    ta     = input("  Team A: ").strip()
    tb     = input("  Team B: ").strip()
    winner = input("  Winner (team name or 'no_result'): ").strip()
    fmt    = input("  Format (ODI/T20I/T20/Test): ").strip()
    gender = input("  Gender (male/female) [male]: ").strip() or "male"
    vc     = input("  Venue country: ").strip()
    mtype  = input("  Match type (bilateral/icc_event/domestic) [bilateral]: ").strip() or "bilateral"
    update_match(conn, date, ta, tb, winner, fmt, gender, vc, mtype)
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--date")
    parser.add_argument("--team-a")
    parser.add_argument("--team-b")
    parser.add_argument("--winner")
    parser.add_argument("--format")
    parser.add_argument("--gender", default="male")
    parser.add_argument("--venue-country", default="")
    parser.add_argument("--match-type", default="bilateral")
    parser.add_argument("--series", default="")
    args = parser.parse_args()

    if args.interactive:
        interactive()
    else:
        conn = get_conn()
        update_match(conn,
            args.date, args.team_a, args.team_b, args.winner,
            args.format, args.gender, args.venue_country,
            args.match_type, args.series)
        conn.close()
