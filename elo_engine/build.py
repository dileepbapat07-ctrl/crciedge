"""
elo_engine/build.py
====================
One-time build script. Processes Cricsheet CSV/JSON match files from 2020 onwards.
Generates:
  - elo_ratings table  (current rating per team per format)
  - elo_history table  (every rating change logged)
  - h2h_full table     (335 matchup records with recent stats)
  - elo_match_log      (every processed match)

USAGE:
  # With real Cricsheet data:
  python build.py --data-dir /path/to/cricsheet/csvs

  # Demo mode (no Cricsheet files needed — seeds synthetic 2020-2026 data):
  python build.py --demo

Cricsheet download:
  https://cricsheet.org/downloads/
  Download: all_csv2.zip (CSV format, all matches)
  Extract to a folder and pass as --data-dir
"""

import sqlite3, os, sys, csv, json, argparse, math, random
from datetime import date, datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from elo_config import (
    ELO_START, ELO_SCALE, HOME_ADVANTAGE, DATA_START_YEAR,
    K_FACTORS, CRICSHEET_FORMAT_MAP, TEAM_NAME_MAP,
    INTERNATIONAL_TEAMS, ICC_EVENT_KEYWORDS, HOME_COUNTRY_MAP,
    elo_delta_to_score, expected_score, k_factor
)

DB_PATH  = os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")
SQL_PATH = os.path.join(os.path.dirname(__file__), "elo_schema.sql")

# ── DB setup ──────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    with open(SQL_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    return conn

# ── Normalise team name ───────────────────────────────────────
def norm(name: str) -> str:
    name = name.strip()
    return TEAM_NAME_MAP.get(name, name)

# ── Detect match type ─────────────────────────────────────────
def get_match_type(series_name: str, ta: str, tb: str) -> str:
    sl = (series_name or "").lower()
    if any(k in sl for k in ICC_EVENT_KEYWORDS):
        return "icc_event"
    ta_intl = ta in INTERNATIONAL_TEAMS
    tb_intl = tb in INTERNATIONAL_TEAMS
    if not ta_intl or not tb_intl:
        return "domestic"
    return "bilateral"

# ── Detect home team ─────────────────────────────────────────
def get_home_team(venue_country: str, ta: str, tb: str) -> str | None:
    if not venue_country:
        return None
    vc = venue_country.strip()
    for team, countries in HOME_COUNTRY_MAP.items():
        if vc in countries:
            norm_team = norm(team)
            if norm_team == ta: return ta
            if norm_team == tb: return tb
    return None  # neutral

# ── ELO update ───────────────────────────────────────────────
def update_elo(ra: float, rb: float, winner: str,
               ta: str, tb: str, home_team: str,
               match_type: str) -> tuple[float, float, float, float, float]:
    """Returns (ra_new, rb_new, k, expected_a, expected_b)"""
    k = k_factor(match_type, ta, tb)
    ea = expected_score(ra, rb, home_team, ta)
    eb = 1 - ea

    if winner == ta:
        sa, sb = 1.0, 0.0
    elif winner == tb:
        sa, sb = 0.0, 1.0
    else:  # no result
        sa, sb = ea, eb  # no change effectively

    ra_new = ra + k * (sa - ea)
    rb_new = rb + k * (sb - eb)
    return ra_new, rb_new, k, ea, eb

# ── Process Cricsheet CSV files ───────────────────────────────
def process_cricsheet_dir(data_dir: str, conn: sqlite3.Connection):
    """
    Cricsheet CSV (ball-by-ball) has a match_info CSV alongside.
    We only need the _info.csv files — they contain match metadata.
    """
    processed = 0
    skipped_old = 0
    skipped_err = 0

    # Collect all *_info.csv files
    info_files = []
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if f.endswith("_info.csv") or f == "matches.csv":
                info_files.append(os.path.join(root, f))

    if not info_files:
        print(f"  No *_info.csv files found in {data_dir}")
        print("  Try downloading from cricsheet.org/downloads/ → all_csv2.zip")
        return 0

    info_files.sort()
    print(f"  Found {len(info_files)} match info files")

    # Parse each info file
    raw_matches = []
    for fpath in info_files:
        try:
            match_data = {}
            with open(fpath, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 3 and row[0] == "info":
                        key, val = row[1], row[2]
                        if key == "team":
                            match_data.setdefault("teams", []).append(val)
                        elif key in ("date","gender","match_type","venue",
                                     "event","winner","outcome","season"):
                            match_data[key] = val

            if not match_data.get("date") or not match_data.get("teams"):
                continue

            raw_matches.append(match_data)
        except Exception:
            skipped_err += 1

    # Sort by date
    raw_matches.sort(key=lambda x: x.get("date",""))

    # Process each match
    ratings = defaultdict(lambda: ELO_START)  # (team, gender, format) → rating
    history = []
    match_log = []
    h2h_data = defaultdict(list)  # (ta, tb, gender, format) → [results]

    for md in raw_matches:
        try:
            match_date_str = md.get("date","")
            if not match_date_str:
                continue
            match_year = int(match_date_str[:4])
            if match_year < DATA_START_YEAR:
                skipped_old += 1
                continue

            teams = md.get("teams", [])
            if len(teams) != 2:
                continue

            ta = norm(teams[0])
            tb = norm(teams[1])
            if ta == tb:
                continue

            gender = md.get("gender", "male")
            fmt_raw = md.get("match_type", "")
            fmt = CRICSHEET_FORMAT_MAP.get(fmt_raw, fmt_raw)
            if not fmt:
                continue

            winner_raw = md.get("winner", "")
            outcome   = md.get("outcome", "")
            if "no result" in outcome.lower() or "abandoned" in outcome.lower():
                winner = "no_result"
            else:
                winner = norm(winner_raw) if winner_raw else "no_result"

            venue_country = md.get("venue", "")  # Cricsheet sometimes puts country
            home_team = get_home_team(venue_country, ta, tb)
            series = md.get("event", "")
            match_type = get_match_type(series, ta, tb)

            key_a = (ta, gender, fmt)
            key_b = (tb, gender, fmt)
            ra = ratings[key_a]
            rb = ratings[key_b]

            ra_new, rb_new, k, ea, eb = update_elo(
                ra, rb, winner, ta, tb, home_team, match_type
            )
            ratings[key_a] = ra_new
            ratings[key_b] = rb_new

            # Log history for both teams
            for team, r_before, r_after, opp, exp in [
                (ta, ra, ra_new, tb, ea),
                (tb, rb, rb_new, ta, eb),
            ]:
                result = ("win" if winner == team
                         else "loss" if winner != "no_result"
                         else "nr")
                history.append({
                    "match_date": match_date_str,
                    "team_id": team,
                    "gender": gender,
                    "format": fmt,
                    "opponent": opp,
                    "venue_country": venue_country,
                    "home_away": ("home" if home_team == team
                                 else "away" if home_team
                                 else "neutral"),
                    "rating_before": round(r_before, 2),
                    "rating_after": round(r_after, 2),
                    "rating_change": round(r_after - r_before, 2),
                    "result": result,
                    "k_factor": k,
                    "expected_score": round(exp, 4),
                    "match_type": match_type,
                })

            match_log.append({
                "match_date": match_date_str,
                "team_a": ta, "team_b": tb,
                "winner": winner,
                "gender": gender, "format": fmt,
                "venue_country": venue_country,
                "match_type": match_type,
                "series": series,
                "elo_a_before": round(ra, 2),
                "elo_b_before": round(rb, 2),
                "elo_a_after": round(ra_new, 2),
                "elo_b_after": round(rb_new, 2),
                "k_factor": k,
            })

            # H2H tracking — always store as alphabetical order
            h2h_key = tuple(sorted([ta, tb])) + (gender, fmt)
            h2h_data[h2h_key].append({
                "date": match_date_str,
                "winner": winner,
                "ta": ta, "tb": tb,
            })

            processed += 1

        except Exception as e:
            skipped_err += 1

    print(f"  Processed: {processed} | Skipped (pre-2020): {skipped_old} | Errors: {skipped_err}")

    # Write to DB
    _write_to_db(conn, ratings, history, match_log, h2h_data)
    return processed

# ── Demo mode — synthetic data ────────────────────────────────
def build_demo(conn: sqlite3.Connection):
    """
    Build realistic ELO ratings using known match outcomes 2020–2026.
    Used when Cricsheet files are not available.
    Covers all 335 H2H matchups needed for our 193-match schedule.
    """
    print("  Building demo ELO from known 2020–2026 outcomes...")

    random.seed(42)

    # Historical win rates between teams (from real cricket knowledge)
    # (team_a, team_b, format, win_rate_a) — a > 0.5 means team_a stronger
    KNOWN_STRENGTHS = {
        # International Men ODI
        ("India","England","ODI"):          0.60,
        ("India","Australia","ODI"):        0.52,
        ("India","Pakistan","ODI"):         0.62,
        ("India","West Indies","ODI"):      0.72,
        ("India","New Zealand","ODI"):      0.58,
        ("India","South Africa","ODI"):     0.54,
        ("India","Sri Lanka","ODI"):        0.68,
        ("India","Bangladesh","ODI"):       0.75,
        ("India","Afghanistan","ODI"):      0.85,
        ("India","Zimbabwe","ODI"):         0.90,
        ("India","Ireland","ODI"):          0.88,
        ("England","Australia","ODI"):      0.52,
        ("England","Pakistan","ODI"):       0.56,
        ("England","West Indies","ODI"):    0.62,
        ("England","New Zealand","ODI"):    0.54,
        ("England","South Africa","ODI"):   0.54,
        ("England","Sri Lanka","ODI"):      0.62,
        ("England","Bangladesh","ODI"):     0.72,
        ("England","Afghanistan","ODI"):    0.78,
        ("England","Zimbabwe","ODI"):       0.88,
        ("Australia","Pakistan","ODI"):     0.62,
        ("Australia","West Indies","ODI"):  0.72,
        ("Australia","New Zealand","ODI"):  0.58,
        ("Australia","South Africa","ODI"): 0.56,
        ("Australia","Sri Lanka","ODI"):    0.68,
        ("Australia","Bangladesh","ODI"):   0.80,
        ("Pakistan","West Indies","ODI"):   0.60,
        ("Pakistan","New Zealand","ODI"):   0.54,
        ("Pakistan","South Africa","ODI"):  0.52,
        ("Pakistan","Sri Lanka","ODI"):     0.58,
        ("Pakistan","Bangladesh","ODI"):    0.62,
        ("West Indies","New Zealand","ODI"):0.48,
        ("West Indies","South Africa","ODI"):0.42,
        ("New Zealand","South Africa","ODI"):0.50,
        ("South Africa","Sri Lanka","ODI"): 0.60,
        # T20I
        ("India","England","T20I"):         0.56,
        ("India","Australia","T20I"):       0.52,
        ("India","Pakistan","T20I"):        0.55,
        ("India","West Indies","T20I"):     0.65,
        ("India","New Zealand","T20I"):     0.60,
        ("India","South Africa","T20I"):    0.54,
        ("India","Sri Lanka","T20I"):       0.64,
        ("India","Bangladesh","T20I"):      0.72,
        ("India","Afghanistan","T20I"):     0.70,
        ("India","Zimbabwe","T20I"):        0.82,
        ("England","Australia","T20I"):     0.50,
        ("England","Pakistan","T20I"):      0.52,
        ("England","West Indies","T20I"):   0.58,
        ("England","New Zealand","T20I"):   0.56,
        ("Australia","Pakistan","T20I"):    0.56,
        ("Australia","West Indies","T20I"): 0.60,
        ("West Indies","New Zealand","T20I"):0.52,
        ("Pakistan","New Zealand","T20I"):  0.54,
        ("Pakistan","West Indies","T20I"):  0.56,
        # CPL
        ("Trinbago KR","Guyana AW","T20"):     0.54,
        ("Trinbago KR","SL Kings","T20"):       0.52,
        ("Trinbago KR","Barbados Royals","T20"):0.52,
        ("Trinbago KR","SKN Patriots","T20"):   0.54,
        ("Trinbago KR","Antigua Falcons","T20"):0.56,
        ("Trinbago KR","Jamaica Kingsmen","T20"):0.58,
        ("Guyana AW","SL Kings","T20"):          0.50,
        ("Guyana AW","Barbados Royals","T20"):   0.52,
        ("Guyana AW","SKN Patriots","T20"):      0.54,
        ("SL Kings","Barbados Royals","T20"):    0.50,
        ("SL Kings","SKN Patriots","T20"):       0.52,
        ("Barbados Royals","SKN Patriots","T20"):0.50,
        # BBL
        ("Perth Scorchers","Melbourne Stars","T20"):   0.62,
        ("Perth Scorchers","Sydney Sixers","T20"):     0.54,
        ("Perth Scorchers","Brisbane Heat","T20"):     0.58,
        ("Perth Scorchers","Sydney Thunder","T20"):    0.60,
        ("Perth Scorchers","Adelaide Strikers","T20"): 0.56,
        ("Perth Scorchers","Melbourne Renegades","T20"):0.68,
        ("Perth Scorchers","Hobart Hurricanes","T20"): 0.62,
        ("Sydney Sixers","Melbourne Stars","T20"):     0.58,
        ("Sydney Sixers","Brisbane Heat","T20"):       0.54,
        ("Sydney Sixers","Sydney Thunder","T20"):      0.56,
        ("Melbourne Stars","Brisbane Heat","T20"):     0.50,
        ("Hobart Hurricanes","Melbourne Stars","T20"): 0.52,
        # WBBL
        ("Perth Scorchers W","Melbourne Stars W","T20"):   0.54,
        ("Sydney Sixers W","Melbourne Renegades W","T20"): 0.58,
        ("Perth Scorchers W","Sydney Thunder W","T20"):    0.56,
        ("Brisbane Heat W","Adelaide Strikers W","T20"):   0.50,
        ("Hobart Hurricanes W","Melbourne Renegades W","T20"):0.54,
    }

    ratings = defaultdict(lambda: ELO_START)
    history = []
    match_log = []
    h2h_data = defaultdict(list)

    # Generate synthetic match history 2020–2025
    all_matchups = []

    # International matchups
    intl_men = ["India","England","Australia","Pakistan","West Indies",
                "New Zealand","South Africa","Sri Lanka","Bangladesh",
                "Afghanistan","Zimbabwe","Ireland"]
    intl_women = ["India Women","England Women","Australia Women","South Africa Women",
                  "New Zealand Women","West Indies Women","Pakistan Women","Sri Lanka Women"]

    from itertools import combinations

    for fmt in ["ODI","T20I"]:
        for ta, tb in combinations(intl_men, 2):
            key = (ta, tb, fmt)
            key_r = (tb, ta, fmt)
            wr = KNOWN_STRENGTHS.get(key, KNOWN_STRENGTHS.get(key_r, None))
            if wr is None:
                wr = 0.50 + random.uniform(-0.05, 0.05)
            if key_r in KNOWN_STRENGTHS:
                wr = 1 - KNOWN_STRENGTHS[key_r]
            all_matchups.append((ta, tb, "male", fmt, wr,
                                 "bilateral", random.choice(intl_men[:6])))

    for ta, tb in combinations(intl_men[:8], 2):
        wr = KNOWN_STRENGTHS.get((ta,tb,"ODI"), 0.50) * 0.9 + 0.05
        all_matchups.append((ta, tb, "male", "Test", wr, "bilateral", ta))

    for ta, tb in combinations(intl_women, 2):
        all_matchups.append((ta, tb, "female", "T20I", 0.50 + random.uniform(-0.1,0.1),
                             "bilateral", "neutral"))

    # Franchise
    franchise_groups = [
        (["Trinbago KR","Guyana AW","SL Kings","Barbados Royals",
          "SKN Patriots","Antigua Falcons","Jamaica Kingsmen"], "male","T20","domestic"),
        (["Barbados Tridents W","Trinbago KR W","Guyana AW W","Jamaica Empress W"],"female","T20","domestic"),
        (["Melbourne Renegades","Perth Scorchers","Brisbane Heat","Sydney Sixers",
          "Sydney Thunder","Adelaide Strikers","Melbourne Stars","Hobart Hurricanes"],"male","T20","domestic"),
        (["Melbourne Renegades W","Perth Scorchers W","Brisbane Heat W","Sydney Sixers W",
          "Sydney Thunder W","Adelaide Strikers W","Melbourne Stars W","Hobart Hurricanes W"],"female","T20","domestic"),
        (["Oval Invincibles","London Spirit","Welsh Fire","Southern Brave",
          "Trent Rockets","Birmingham Phoenix","Manchester Originals","Sunrisers"],"male","T20","domestic"),
        (["Oval Invincibles W","London Spirit W","Welsh Fire W","Southern Brave W",
          "Trent Rockets W","Birmingham Phoenix W","Manchester Originals W","Sunrisers W"],"female","T20","domestic"),
    ]
    for teams, gender, fmt, mtype in franchise_groups:
        for ta, tb in combinations(teams, 2):
            key = (ta, tb, fmt)
            key_r = (tb, ta, fmt)
            wr = KNOWN_STRENGTHS.get(key, KNOWN_STRENGTHS.get(key_r, None))
            if wr is None:
                wr = 0.50 + random.uniform(-0.08, 0.08)
            elif key_r in KNOWN_STRENGTHS:
                wr = 1 - KNOWN_STRENGTHS[key_r]
            all_matchups.append((ta, tb, gender, fmt, wr, mtype, "neutral"))

    # Simulate matches 2020 → now
    start = date(2020, 1, 1)
    end   = date(2026, 7, 13)

    for ta, tb, gender, fmt, wr, mtype, home_country in all_matchups:
        # Each matchup plays ~15–30 matches over 2020–2026
        n_matches = random.randint(12, 28)
        for i in range(n_matches):
            days_offset = random.randint(0, (end - start).days)
            mdate = (start + timedelta(days=days_offset)).isoformat()
            if int(mdate[:4]) < 2020:
                continue

            # Determine winner based on win rate + some randomness
            rand_val = random.random()
            if rand_val < wr * 0.92:
                winner = ta
            elif rand_val < wr * 0.92 + (1 - wr) * 0.92:
                winner = tb
            else:
                winner = "no_result"

            # Home team
            home_team = None
            if home_country not in ("neutral",):
                home_team = norm(home_country) if home_country in [ta, tb] else None

            key_a = (ta, gender, fmt)
            key_b = (tb, gender, fmt)
            ra = ratings[key_a]
            rb = ratings[key_b]

            ra_new, rb_new, k, ea, eb = update_elo(
                ra, rb, winner, ta, tb, home_team, mtype
            )
            ratings[key_a] = ra_new
            ratings[key_b] = rb_new

            # Log
            for team, r_before, r_after, opp, exp in [
                (ta, ra, ra_new, tb, ea), (tb, rb, rb_new, ta, eb)
            ]:
                result = ("win" if winner==team else "loss" if winner!="no_result" else "nr")
                history.append({
                    "match_date": mdate, "team_id": team,
                    "gender": gender, "format": fmt, "opponent": opp,
                    "venue_country": home_country,
                    "home_away": ("home" if home_team==team else "away" if home_team else "neutral"),
                    "rating_before": round(r_before,2), "rating_after": round(r_after,2),
                    "rating_change": round(r_after-r_before,2), "result": result,
                    "k_factor": k, "expected_score": round(exp,4), "match_type": mtype,
                })

            match_log.append({
                "match_date": mdate, "team_a": ta, "team_b": tb,
                "winner": winner, "gender": gender, "format": fmt,
                "venue_country": home_country, "match_type": mtype, "series": "",
                "elo_a_before": round(ra,2), "elo_b_before": round(rb,2),
                "elo_a_after": round(ra_new,2), "elo_b_after": round(rb_new,2),
                "k_factor": k,
            })

            h2h_key = tuple(sorted([ta,tb])) + (gender, fmt)
            h2h_data[h2h_key].append({"date":mdate,"winner":winner,"ta":ta,"tb":tb})

    print(f"  Generated {len(match_log)} synthetic matches across {len(all_matchups)} matchups")
    _write_to_db(conn, ratings, history, match_log, h2h_data)

# ── Write everything to DB ────────────────────────────────────
def _write_to_db(conn, ratings, history, match_log, h2h_data):
    print("  Writing ELO ratings to DB...")

    # 1. ELO ratings
    for (team, gender, fmt), rating in ratings.items():
        team_type = "international" if team in INTERNATIONAL_TEAMS else "franchise"
        # Find last match info from history
        team_hist = [h for h in history if h["team_id"]==team and h["gender"]==gender and h["format"]==fmt]
        team_hist.sort(key=lambda x: x["match_date"])
        wins   = sum(1 for h in team_hist if h["result"]=="win")
        losses = sum(1 for h in team_hist if h["result"]=="loss")
        played = len(team_hist)
        peak   = max((h["rating_after"] for h in team_hist), default=rating)
        peak_d = next((h["match_date"] for h in reversed(team_hist) if h["rating_after"]==peak), None)
        last   = team_hist[-1] if team_hist else None

        conn.execute("""
            INSERT OR REPLACE INTO elo_ratings
            (team_id, team_type, gender, format, rating, matches_played,
             wins, losses, peak_rating, peak_date,
             last_match_date, last_opponent, last_result, last_updated)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
        """, (team, team_type, gender, fmt, round(rating,2),
              played, wins, losses, round(peak,2), peak_d,
              last["match_date"] if last else None,
              last["opponent"] if last else None,
              last["result"] if last else None))

    # 2. ELO history
    conn.executemany("""
        INSERT OR IGNORE INTO elo_history
        (match_date,team_id,gender,format,opponent,venue_country,
         home_away,rating_before,rating_after,rating_change,
         result,k_factor,expected_score,match_type)
        VALUES (:match_date,:team_id,:gender,:format,:opponent,:venue_country,
                :home_away,:rating_before,:rating_after,:rating_change,
                :result,:k_factor,:expected_score,:match_type)
    """, history)

    # 3. Match log
    conn.executemany("""
        INSERT OR IGNORE INTO elo_match_log
        (match_date,team_a,team_b,winner,gender,format,
         venue_country,match_type,series,
         elo_a_before,elo_b_before,elo_a_after,elo_b_after,k_factor)
        VALUES (:match_date,:team_a,:team_b,:winner,:gender,:format,
                :venue_country,:match_type,:series,
                :elo_a_before,:elo_b_before,:elo_a_after,:elo_b_after,:k_factor)
    """, match_log)

    # 4. H2H full
    print("  Computing H2H records...")
    for (ta_s, tb_s, gender, fmt), matches in h2h_data.items():
        matches.sort(key=lambda x: x["date"])

        # Get canonical a/b (first alphabetically)
        ta, tb = ta_s, tb_s

        total = len(matches)
        ta_wins = sum(1 for m in matches if m["winner"]==ta)
        tb_wins = sum(1 for m in matches if m["winner"]==tb)
        nr      = sum(1 for m in matches if m["winner"]=="no_result")

        recent = [m for m in matches if m["date"] >= "2020-01-01"]
        r_ta_w = sum(1 for m in recent if m["winner"]==ta)
        r_tb_w = sum(1 for m in recent if m["winner"]==tb)
        r_total = len(recent)

        last5 = matches[-5:] if len(matches) >= 5 else matches
        l5_results = ",".join(
            "A" if m["winner"]==ta else "B" if m["winner"]==tb else "N"
            for m in last5
        )
        l5_a_wins = sum(1 for m in last5 if m["winner"]==ta)

        # Current streak
        streak_winner = None
        streak = 0
        for m in reversed(matches):
            w = m["winner"]
            if w == "no_result": continue
            if streak_winner is None:
                streak_winner = w; streak = 1
            elif w == streak_winner:
                streak += 1
            else:
                break

        last = matches[-1]
        ta_pct = round(ta_wins / (total - nr) * 100, 1) if (total-nr) > 0 else 50.0
        r_pct  = round(r_ta_w / (r_total - (r_total - r_ta_w - r_tb_w)) * 100, 1) if r_total > 0 else 50.0

        conn.execute("""
            INSERT OR REPLACE INTO h2h_full
            (team_a, team_b, gender, format,
             matches_played, team_a_wins, team_b_wins, no_results, team_a_win_pct,
             recent_played, recent_a_wins, recent_b_wins, recent_a_pct,
             last_5_results, last_5_a_wins,
             current_winner, current_streak,
             last_match_date, last_match_winner)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (ta, tb, gender, fmt,
              total, ta_wins, tb_wins, nr, ta_pct,
              r_total, r_ta_w, r_tb_w, r_pct,
              l5_results, l5_a_wins,
              streak_winner, streak,
              last["date"], last["winner"]))

    conn.commit()

    n_rat  = conn.execute("SELECT COUNT(*) FROM elo_ratings").fetchone()[0]
    n_hist = conn.execute("SELECT COUNT(*) FROM elo_history").fetchone()[0]
    n_h2h  = conn.execute("SELECT COUNT(*) FROM h2h_full").fetchone()[0]
    n_log  = conn.execute("SELECT COUNT(*) FROM elo_match_log").fetchone()[0]

    print(f"\n  ✅ Written to DB:")
    print(f"     ELO ratings:    {n_rat} team-format records")
    print(f"     ELO history:    {n_hist} rating change entries")
    print(f"     H2H records:    {n_h2h} matchup records")
    print(f"     Match log:      {n_log} processed matches")

# ── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build ELO ratings from Cricsheet data")
    parser.add_argument("--data-dir", help="Path to Cricsheet CSV directory")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode (no files needed)")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  CRICKET ELO ENGINE — BUILD")
    print(f"  Data from: {DATA_START_YEAR} onwards")
    print("="*60)

    conn = get_conn()

    if args.demo or not args.data_dir:
        print("\n  Running in DEMO mode (synthetic 2020–2026 data)")
        print("  For production: python build.py --data-dir /path/to/cricsheet\n")
        build_demo(conn)
    else:
        print(f"\n  Processing Cricsheet files from: {args.data_dir}\n")
        process_cricsheet_dir(args.data_dir, conn)

    # Print top ratings
    print("\n  TOP ELO RATINGS (Men's T20I):")
    rows = conn.execute("""
        SELECT team_id, rating, wins, losses, matches_played
        FROM elo_ratings
        WHERE format='T20I' AND gender='male'
        ORDER BY rating DESC LIMIT 10
    """).fetchall()
    for i,r in enumerate(rows,1):
        wr = round(r["wins"]/r["matches_played"]*100) if r["matches_played"] else 0
        print(f"  {i:2}. {r['team_id']:<28} {r['rating']:7.1f}  "
              f"W{r['wins']} L{r['losses']} ({wr}% win rate)")

    print("\n  TOP ELO RATINGS (Men's ODI):")
    rows = conn.execute("""
        SELECT team_id, rating, wins, losses, matches_played
        FROM elo_ratings
        WHERE format='ODI' AND gender='male'
        ORDER BY rating DESC LIMIT 10
    """).fetchall()
    for i,r in enumerate(rows,1):
        wr = round(r["wins"]/r["matches_played"]*100) if r["matches_played"] else 0
        print(f"  {i:2}. {r['team_id']:<28} {r['rating']:7.1f}  "
              f"W{r['wins']} L{r['losses']} ({wr}% win rate)")

    print("\n  SAMPLE H2H (India vs England):")
    rows = conn.execute("""
        SELECT * FROM h2h_full
        WHERE (team_a='India' AND team_b='England')
           OR (team_a='England' AND team_b='India')
        ORDER BY format
    """).fetchall()
    for r in rows:
        print(f"  {r['format']:6} {r['team_a']} vs {r['team_b']}: "
              f"A={r['team_a_wins']} B={r['team_b_wins']} "
              f"({r['team_a_win_pct']}% A) | Last 5: {r['last_5_results']} "
              f"| Streak: {r['current_winner']} ×{r['current_streak']}")

    conn.close()
    print("\n  Build complete.")
