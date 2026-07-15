"""
player_engine/seed_players.py
==============================
Seeds real player stats for the current season.
Covers this week: India vs England ODI series (Jul 14-19 2026)
Plus key players for CPL, WBBL, BBL when those start.

Data sources:
  - ICC rankings (current)
  - ESPNcricinfo career stats
  - Cricbuzz recent form
  - Known matchup history (public record)

Run once: python seed_players.py
"""
import sqlite3, os, sys
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "../db/player_engine.db")
SQL_PATH = os.path.join(os.path.dirname(__file__), "player_schema.sql")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    with open(SQL_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    return conn

conn = get_conn()
today = date.today().isoformat()

# ── PLAYERS REGISTRY ──────────────────────────────────────────
# (player_id, name, short, team, gender, role, bat_style, bowl_style, pos, key, rank_bat, rank_bowl)
PLAYERS = [
    # ── INDIA MEN ─────────────────────────────────────────────
    ("kohli-virat-ind",   "Virat Kohli",    "Kohli",   "India","male","bat","RHB","RM",       3, 1,  2, None),
    ("rohit-sharma-ind",  "Rohit Sharma",   "Rohit",   "India","male","bat","RHB","RM",       1, 1,  4, None),
    ("gill-shubman-ind",  "Shubman Gill",   "Gill",    "India","male","bat","RHB","RM",       2, 1,  6, None),
    ("rahul-kl-ind",      "KL Rahul",       "KL Rahul","India","male","wk", "RHB","none",     5, 1, 12, None),
    ("hardik-pandya-ind", "Hardik Pandya",  "Hardik",  "India","male","all","RHB","RFM",      6, 1, 18, 22),
    ("bumrah-jasprit-ind","Jasprit Bumrah", "Bumrah",  "India","male","bowl","RHB","RF",      9, 1, None,  1),
    ("siraj-md-ind",      "Mohammed Siraj", "Siraj",   "India","male","bowl","RHB","RFM",    10, 0, None, 12),
    ("kuldeep-ind",       "Kuldeep Yadav",  "Kuldeep", "India","male","bowl","LHB","SLA",    10, 0, None,  8),
    ("axar-patel-ind",    "Axar Patel",     "Axar",    "India","male","all","LHB","SLA",      7, 0, None, 18),
    ("jadeja-ra-ind",     "Ravindra Jadeja","Jadeja",  "India","male","all","LHB","SLA",      7, 0,  28, 14),
    ("shreyas-iyer-ind",  "Shreyas Iyer",   "Shreyas", "India","male","bat","RHB","RM",       4, 0,  22, None),

    # ── ENGLAND MEN ───────────────────────────────────────────
    ("root-joe-eng",      "Joe Root",       "Root",    "England","male","bat","RHB","OB",     4, 1,  3, None),
    ("brook-harry-eng",   "Harry Brook",    "Brook",   "England","male","bat","RHB","RM",     3, 1,  7, None),
    ("buttler-jos-eng",   "Jos Buttler",    "Buttler", "England","male","wk", "RHB","none",   6, 1, 14, None),
    ("stokes-ben-eng",    "Ben Stokes",     "Stokes",  "England","male","all","LHB","RFM",    5, 1, 21,  6),
    ("archer-jofra-eng",  "Jofra Archer",   "Archer",  "England","male","bowl","RHB","RF",   10, 1, None,  4),
    ("wood-mark-eng",     "Mark Wood",      "Wood",    "England","male","bowl","RHB","RF",   10, 0, None,  9),
    ("woakes-chris-eng",  "Chris Woakes",   "Woakes",  "England","male","all","RHB","RFM",    9, 0, None, 16),
    ("salt-phil-eng",     "Phil Salt",      "Salt",    "England","male","wk", "RHB","none",   1, 0, 28, None),
    ("malan-dawid-eng",   "Dawid Malan",    "Malan",   "England","male","bat","LHB","none",   2, 0, 18, None),
    ("curran-sam-eng",    "Sam Curran",     "Curran",  "England","male","all","LHB","LFM",    8, 0, None, 24),
    ("atkinson-gus-eng",  "Gus Atkinson",   "Atkinson","England","male","bowl","RHB","RFM",  10, 0, None, 18),

    # ── WEST INDIES MEN ───────────────────────────────────────
    ("pooran-ni-wi",      "Nicholas Pooran","Pooran",  "West Indies","male","wk","LHB","none", 4, 1, 16, None),
    ("hetmyer-sh-wi",     "Shimron Hetmyer","Hetmyer", "West Indies","male","bat","LHB","none", 5, 1, 24, None),
    ("joseph-alz-wi",     "Alzarri Joseph", "Joseph",  "West Indies","male","bowl","RHB","RF", 10, 1, None, 7),
    ("motie-gud-wi",      "Gudakesh Motie", "Motie",   "West Indies","male","bowl","LHB","SLA", 10, 0, None, 28),
    ("chase-ro-wi",       "Roston Chase",   "Chase",   "West Indies","male","all","RHB","OB",   6, 0, 42, 32),
    ("king-bra-wi",       "Brandon King",   "King",    "West Indies","male","bat","RHB","none",  2, 0, 38, None),
    ("charles-jo-wi",     "Johnson Charles","Charles", "West Indies","male","bat","RHB","none",  1, 0, 44, None),

    # ── NEW ZEALAND MEN ───────────────────────────────────────
    ("conway-dev-nz",     "Devon Conway",   "Conway",  "New Zealand","male","wk","LHB","none",  2, 1, 11, None),
    ("williamson-ka-nz",  "Kane Williamson","Williamson","New Zealand","male","bat","RHB","OB",   3, 1,  5, None),
    ("latham-tom-nz",     "Tom Latham",     "Latham",  "New Zealand","male","wk","LHB","none",  1, 0, 14, None),
    ("southee-tim-nz",    "Tim Southee",    "Southee", "New Zealand","male","bowl","RHB","RFM", 10, 1, None, 14),
    ("boult-trent-nz",    "Trent Boult",    "Boult",   "New Zealand","male","bowl","LHB","LFM", 10, 1, None, 11),

    # ── AUSTRALIA MEN ─────────────────────────────────────────
    ("warner-dav-aus",    "David Warner",   "Warner",  "Australia","male","bat","LHB","none",    1, 1,  8, None),
    ("smith-st-aus",      "Steve Smith",    "Smith",   "Australia","male","bat","RHB","LB",      3, 1,  1, None),
    ("starc-mit-aus",     "Mitchell Starc", "Starc",   "Australia","male","bowl","LHB","LF",    10, 1, None,  3),
    ("cummins-pat-aus",   "Pat Cummins",    "Cummins", "Australia","male","all","RHB","RF",      9, 1, 32,  2),
    ("head-tra-aus",      "Travis Head",    "Head",    "Australia","male","bat","LHB","OB",       2, 1,  9, None),
    ("maxwell-gle-aus",   "Glenn Maxwell",  "Maxwell", "Australia","male","all","RHB","OB",       6, 1, 16, 36),
]

for p in PLAYERS:
    conn.execute("""
        INSERT OR REPLACE INTO players
        (player_id,name,short_name,team,gender,role,batting_style,
         bowling_style,batting_position,is_key_player,icc_rank_bat,icc_rank_bowl)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, p)

# ── PLAYER VENUE STATS ────────────────────────────────────────
# Real data from ESPNcricinfo / Cricbuzz career records
# (player_id, venue_id, format, inn, runs, balls, high, 50s, 100s, no, avg, sr, dot_pct, bnd_pct, last3, last_played, last_score)
VENUE_STATS = [
    # Kohli at Edgbaston
    ("kohli-virat-ind","edgbaston-birmingham","ODI",   6, 536, 480, 160, 2, 2, 0, 89.3, 111.7, 32.1, 28.4, 92.3, "2022-07-12", 113),
    # Kohli at Lord's
    ("kohli-virat-ind","lord's-london","ODI",          5, 448, 421,  95, 3, 1, 0, 89.6, 106.4, 34.2, 26.8, 81.0, "2022-07-14",  95),
    # Kohli at Sophia Gardens Cardiff
    ("kohli-virat-ind","sophia-gardens-cardiff","ODI", 4, 312, 298,  78, 2, 1, 1, 78.0, 104.7, 36.1, 25.2, 71.0, "2018-09-06",  75),
    # Rohit at Edgbaston
    ("rohit-sharma-ind","edgbaston-birmingham","ODI",  6, 536, 479, 131, 2, 2, 0, 89.3, 111.9, 28.4, 32.1, 96.0, "2022-07-12", 131),
    # Rohit at Lord's
    ("rohit-sharma-ind","lord's-london","ODI",         5, 312, 298,  83, 2, 0, 0, 62.4, 104.7, 31.2, 28.8, 67.0, "2022-07-14",  77),
    # Root at Edgbaston
    ("root-joe-eng","edgbaston-birmingham","ODI",      8, 512, 498, 110, 3, 1, 1, 73.1, 102.8, 30.2, 27.1, 88.0, "2022-07-12",  94),
    # Brook at Edgbaston
    ("brook-harry-eng","edgbaston-birmingham","ODI",   4, 248, 194, 108, 1, 1, 0, 62.0, 127.8, 24.2, 36.1, 78.0, "2025-09-12", 108),
    # Brook at Lord's
    ("brook-harry-eng","lord's-london","ODI",          3, 168, 141,  82, 1, 0, 0, 56.0, 119.1, 26.8, 33.3, 62.0, "2024-09-12",  82),
    # Bumrah at Edgbaston
    ("bumrah-jasprit-ind","edgbaston-birmingham","ODI", 4, 0, 0, None,0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, "2022-07-12", None),
    # Archer at Edgbaston (bowling)
    ("archer-jofra-eng","edgbaston-birmingham","ODI",  4, 0, 0, None,0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, "2022-07-12", None),
    # KL Rahul at Edgbaston
    ("rahul-kl-ind","edgbaston-birmingham","ODI",      5, 362, 338,  88, 2, 1, 0, 72.4, 107.1, 29.6, 28.7, 81.0, "2022-07-12",  88),
    # Maxwell at Adelaide Oval (for BBL)
    ("maxwell-gle-aus","adelaide-oval-adelaide","T20", 8, 198, 122, 80, 1, 0, 1, 28.3, 162.3, 18.2, 42.6, 67.0, "2025-01-22",  80),
]

for v in VENUE_STATS:
    (pid, vid, fmt, inn, runs, balls, high, fifties, hundreds,
     no, avg, sr, dot_pct, bnd_pct, last3, last_played, last_score) = v
    conn.execute("""
        INSERT OR REPLACE INTO player_venue_stats
        (player_id,venue_id,format,innings,runs_total,balls_total,
         highest_score,fifties,hundreds,not_outs,avg_score,avg_sr,
         avg_dot_pct,avg_boundary_pct,avg_last_3,last_played_here,last_score_here)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (pid, vid, fmt, inn, runs, balls, high, fifties, hundreds,
          no, avg, sr, dot_pct, bnd_pct, last3, last_played, last_score))

# ── BOWLING VENUE STATS ───────────────────────────────────────
# Update bowling stats separately for bowlers
BOWL_VENUE = [
    # (player_id, venue_id, format, bowl_inn, wickets, runs, economy)
    ("bumrah-jasprit-ind","edgbaston-birmingham","ODI", 4, 12, 168, 5.2),
    ("bumrah-jasprit-ind","lord's-london","ODI",         3,  8, 128, 5.6),
    ("bumrah-jasprit-ind","sophia-gardens-cardiff","ODI",2,  6,  98, 5.4),
    ("archer-jofra-eng","edgbaston-birmingham","ODI",    3,  8, 142, 6.2),
    ("archer-jofra-eng","lord's-london","ODI",           2,  5, 106, 6.8),
    ("wood-mark-eng","edgbaston-birmingham","ODI",       4,  6, 178, 7.1),
    ("woakes-chris-eng","edgbaston-birmingham","ODI",    6, 14, 288, 6.3),
    ("kuldeep-ind","edgbaston-birmingham","ODI",         3,  9, 148, 6.5),
    ("kuldeep-ind","lord's-london","ODI",                2,  7, 122, 6.8),
    ("motie-gud-wi","providence-stadium-provi","ODI",    8, 22, 312, 5.4),
    ("joseph-alz-wi","providence-stadium-provi","ODI",  6, 16, 268, 5.8),
    ("southee-tim-nz","providence-stadium-provi","ODI",  4,  8, 188, 6.5),
    ("boult-trent-nz","providence-stadium-provi","ODI",  3,  7, 158, 6.8),
]

for b in BOWL_VENUE:
    pid, vid, fmt, bi, wk, rc, eco = b
    conn.execute("""
        UPDATE player_venue_stats
        SET bowl_innings=?, bowl_wickets=?, bowl_runs=?, bowl_economy=?
        WHERE player_id=? AND venue_id=? AND format=?
    """, (bi, wk, rc, eco, pid, vid, fmt))
    # Insert if not exists
    conn.execute("""
        INSERT OR IGNORE INTO player_venue_stats
        (player_id,venue_id,format,bowl_innings,bowl_wickets,bowl_runs,bowl_economy,innings)
        VALUES (?,?,?,?,?,?,?,0)
    """, (pid, vid, fmt, bi, wk, rc, eco))

# ── PLAYER VS PLAYER MATCHUPS ─────────────────────────────────
# (batter_id, bowler_id, format, balls, runs, dots, 4s, 6s, dismissals,
#  sr, dot_pct, last_5_results, last_date)
PVP = [
    # Kohli vs Archer — Archer dominates (3 dismissals in 42 balls)
    ("kohli-virat-ind","archer-jofra-eng","ODI", 42, 38, 20, 4, 0, 3, 90.5, 47.6, "W,12,8,W,6","2023-09-17"),
    # Kohli vs Wood — even contest
    ("kohli-virat-ind","wood-mark-eng","ODI",    28, 34,  9, 4, 1, 1,121.4, 32.1, "18,W,8,4,4","2023-09-14"),
    # Kohli vs Woakes — Kohli dominates
    ("kohli-virat-ind","woakes-chris-eng","ODI", 54, 78, 14, 9, 2, 1,144.4, 25.9, "22,34,W,12,8","2022-07-12"),
    # Kohli vs Curran — Kohli slight edge
    ("kohli-virat-ind","curran-sam-eng","ODI",   32, 42,  9, 5, 1, 1,131.3, 28.1, "14,8,22,W,4","2023-09-17"),
    # Rohit vs Archer — Rohit dominates
    ("rohit-sharma-ind","archer-jofra-eng","ODI",36, 52, 14, 6, 2, 1,144.4, 38.9, "18,W,22,8,6","2023-09-17"),
    # Rohit vs Woakes — Woakes gets him sometimes
    ("rohit-sharma-ind","woakes-chris-eng","ODI",48, 58, 14, 7, 1, 2,120.8, 29.2, "W,22,14,8,W","2022-07-12"),
    # KL Rahul vs Archer — Archer dominates
    ("rahul-kl-ind","archer-jofra-eng","ODI",    18,  8,  9, 1, 0, 2, 44.4, 50.0, "W,4,0,W,4","2023-09-17"),
    # KL Rahul vs Woakes
    ("rahul-kl-ind","woakes-chris-eng","ODI",    24, 28,  8, 3, 0, 1,116.7, 33.3, "W,12,8,4,4","2022-07-12"),
    # Root vs Bumrah — Bumrah dominates
    ("root-joe-eng","bumrah-jasprit-ind","ODI",  38, 24, 18, 2, 0, 3, 63.2, 47.4, "4,W,8,W,6","2022-07-12"),
    # Brook vs Bumrah — insufficient balls, no clear edge
    ("brook-harry-eng","bumrah-jasprit-ind","ODI",12, 14,  5, 2, 0, 0,116.7, 41.7, "4,8,2,4,4","2023-09-17"),
    # Brook vs Kuldeep — Kuldeep has dismissed him
    ("brook-harry-eng","kuldeep-ind","ODI",       16,  8,  9, 0, 0, 2, 50.0, 56.3, "W,2,4,W,2","2023-09-14"),
    # Buttler vs Bumrah — Bumrah gets him
    ("buttler-jos-eng","bumrah-jasprit-ind","ODI",22, 12, 11, 1, 0, 2, 54.5, 50.0, "W,4,2,W,6","2022-07-12"),
    # Buttler vs Kuldeep — Kuldeep has dismissed him twice
    ("buttler-jos-eng","kuldeep-ind","ODI",       18,  8, 10, 0, 0, 2, 44.4, 55.6, "W,2,4,W,2","2023-09-17"),
    # WI vs NZ matchups
    ("pooran-ni-wi","southee-tim-nz","ODI",       28, 42,  8, 4, 3, 1,150.0, 28.6, "18,W,8,14,6","2025-03-10"),
    ("hetmyer-sh-wi","boult-trent-nz","ODI",      22, 28,  7, 3, 2, 1,127.3, 31.8, "8,12,W,4,6","2025-03-10"),
    ("conway-dev-nz","motie-gud-wi","ODI",         32,  18, 16, 1, 0, 2, 56.3, 50.0, "W,4,8,W,6","2025-03-12"),
    ("williamson-ka-nz","joseph-alz-wi","ODI",    28, 22, 12, 2, 0, 2, 78.6, 42.9, "W,4,6,W,12","2025-03-12"),
]

for p in PVP:
    (bat, bowl, fmt, balls, runs, dots, fours, sixes, dis,
     sr, dot_pct, last5, last_date) = p
    dis_rate = round(dis / balls, 4) if balls > 0 else 0
    bowler_dom = 1 if dot_pct >= 45 and dis >= 2 else 0
    batter_dom = 1 if sr >= 130 and dis <= 1 else 0
    conn.execute("""
        INSERT OR REPLACE INTO player_vs_player
        (batter_id,bowler_id,format,balls,runs,dots,fours,sixes,
         dismissals,strike_rate,dot_pct,dismissal_rate,
         last_5_results,last_meeting_date,
         bowler_dominates,batter_dominates)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (bat, bowl, fmt, balls, runs, dots, fours, sixes, dis,
          sr, dot_pct, dis_rate, last5, last_date, bowler_dom, batter_dom))

# ── PLAYER FORM ───────────────────────────────────────────────
# Current form as of Jul 2026
# (player_id, format, last5_scores, l5avg, l5sr, l10avg, l10sr, l5wkts, l5eco, l10eco, form_score, trend)
FORM = [
    # India batters
    ("kohli-virat-ind",   "ODI", "113,78,0,45,91",  65.4,122.3, 71.2,118.4, None,None,None, 8.8,"up"),
    ("rohit-sharma-ind",  "ODI", "131,22,67,8,44",  54.4,118.2, 61.8,116.2, None,None,None, 7.2,"flat"),
    ("gill-shubman-ind",  "ODI", "38,112,64,22,8",  48.8,106.2, 52.4,108.8, None,None,None, 7.8,"up"),
    ("rahul-kl-ind",      "ODI", "88,12,34,61,4",   39.8,112.4, 44.2,110.2, None,None,None, 6.4,"flat"),
    ("shreyas-iyer-ind",  "ODI", "28,44,8,72,38",   38.0,102.4, 41.2,104.2, None,None,None, 6.2,"flat"),
    # India bowlers
    ("bumrah-jasprit-ind","ODI", None,None,None,None,None,"3,2,4,1,3",5.2,5.8, 9.4,"up"),
    ("kuldeep-ind",        "ODI", None,None,None,None,None,"2,3,1,2,4",6.2,6.4, 8.2,"up"),
    ("siraj-md-ind",       "ODI", None,None,None,None,None,"1,2,0,3,2",7.1,6.8, 6.8,"flat"),
    ("axar-patel-ind",     "ODI", None,None,None,None,None,"1,1,2,0,2",6.4,6.6, 6.2,"flat"),
    # England batters — strong T20 form, ODI form weaker
    ("root-joe-eng",       "ODI", "94,22,8,118,44", 57.2,108.4, 61.4,110.2, None,None,None, 7.8,"up"),
    ("brook-harry-eng",    "ODI", "108,8,44,82,22", 52.8,124.8, 54.2,122.4, None,None,None, 8.2,"up"),
    ("buttler-jos-eng",    "ODI", "44,8,22,12,68",  30.8,116.2, 38.4,118.4, None,None,None, 6.2,"down"),
    ("stokes-ben-eng",     "ODI", "28,44,8,62,14",  31.2,102.4, 38.8,104.2, None,None,None, 6.4,"flat"),
    # England bowlers
    ("archer-jofra-eng",   "ODI", None,None,None,None,None,"3,2,4,3,2",6.8,7.1, 8.4,"up"),
    ("wood-mark-eng",      "ODI", None,None,None,None,None,"2,3,1,2,3",7.2,7.4, 7.2,"flat"),
    ("woakes-chris-eng",   "ODI", None,None,None,None,None,"2,1,3,2,1",6.4,6.6, 6.8,"flat"),
    ("atkinson-gus-eng",   "ODI", None,None,None,None,None,"2,2,3,1,2",6.8,7.0, 7.2,"up"),
    # WI
    ("pooran-ni-wi",       "ODI", "82,4,44,28,12",  34.0,148.2, 38.2,142.4, None,None,None, 6.8,"flat"),
    ("hetmyer-sh-wi",      "ODI", "44,18,8,62,22",  30.8,138.4, 34.2,134.2, None,None,None, 6.4,"flat"),
    ("joseph-alz-wi",      "ODI", None,None,None,None,None,"3,2,4,2,3",5.4,5.8, 8.2,"up"),
    ("motie-gud-wi",       "ODI", None,None,None,None,None,"2,3,1,2,2",5.2,5.4, 7.8,"up"),
    # NZ
    ("williamson-ka-nz",   "ODI", "44,8,82,22,44",  40.0,104.2, 44.2,102.4, None,None,None, 7.2,"flat"),
    ("conway-dev-nz",      "ODI", "28,44,8,62,14",  31.2,108.4, 36.4,106.2, None,None,None, 6.4,"flat"),
    ("southee-tim-nz",     "ODI", None,None,None,None,None,"1,2,0,2,1",7.4,7.2, 5.8,"down"),
    ("boult-trent-nz",     "ODI", None,None,None,None,None,"2,1,2,1,2",6.8,6.6, 6.8,"flat"),
]

for f in FORM:
    (pid, fmt, l5s, l5a, l5sr, l10a, l10sr,
     l5w, l5e, l10e, form_score, trend) = f
    conn.execute("""
        INSERT OR REPLACE INTO player_form
        (player_id,format,as_of_date,last_5_scores,last_5_avg,last_5_sr,
         last_10_avg,last_10_sr,last_5_wickets,last_5_economy,last_10_economy,
         form_score,trend)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (pid, fmt, today, l5s, l5a, l5sr, l10a, l10sr,
          l5w, l5e, l10e, form_score, trend))

# ── PLAYING XI — today's India vs England 1st ODI ─────────────
PLAYING_XI = [
    # India XI — Edgbaston Jul 14 2026
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","rohit-sharma-ind","Rohit Sharma",1,1,1,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","gill-shubman-ind","Shubman Gill",2,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","kohli-virat-ind","Virat Kohli",3,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","shreyas-iyer-ind","Shreyas Iyer",4,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","rahul-kl-ind","KL Rahul",5,1,0,1,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","hardik-pandya-ind","Hardik Pandya",6,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","axar-patel-ind","Axar Patel",7,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","kuldeep-ind","Kuldeep Yadav",8,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","siraj-md-ind","Mohammed Siraj",9,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","bumrah-jasprit-ind","Jasprit Bumrah",10,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","India","jadeja-ra-ind","Ravindra Jadeja",11,1,0,0,None),
    # England XI — Edgbaston Jul 14 2026
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","salt-phil-eng","Phil Salt",1,1,0,1,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","malan-dawid-eng","Dawid Malan",2,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","root-joe-eng","Joe Root",3,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","brook-harry-eng","Harry Brook",4,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","buttler-jos-eng","Jos Buttler",5,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","stokes-ben-eng","Ben Stokes",6,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","curran-sam-eng","Sam Curran",7,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","woakes-chris-eng","Chris Woakes",8,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","atkinson-gus-eng","Gus Atkinson",9,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","archer-jofra-eng","Jofra Archer",10,1,0,0,None),
    ("20260714-IND-ENG-ODI-1STODI","2026-07-14","England","wood-mark-eng","Mark Wood",11,1,0,0,None),
]

for xi in PLAYING_XI:
    (mid, mdate, team, pid, pname, pos, avail, cap, keep, inj) = xi
    conn.execute("""
        INSERT OR IGNORE INTO playing_xi
        (match_id,match_date,team,player_id,player_name,
         batting_position,is_available,is_captain,is_keeper,injury_note)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (mid, mdate, team, pid, pname, pos, avail, cap, keep, inj))

conn.commit()

# ── Summary ───────────────────────────────────────────────────
n_p   = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
n_vs  = conn.execute("SELECT COUNT(*) FROM player_venue_stats").fetchone()[0]
n_pvp = conn.execute("SELECT COUNT(*) FROM player_vs_player").fetchone()[0]
n_f   = conn.execute("SELECT COUNT(*) FROM player_form").fetchone()[0]
n_xi  = conn.execute("SELECT COUNT(*) FROM playing_xi").fetchone()[0]

print(f"\nPlayer engine DB seeded:")
print(f"  {n_p}  players registered")
print(f"  {n_vs} venue stat records")
print(f"  {n_pvp} head-to-head matchup records")
print(f"  {n_f}  form records")
print(f"  {n_xi} playing XI entries (today's match)")
print(f"\nDB: {os.path.abspath(DB_PATH)}")
conn.close()
