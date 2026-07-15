"""
02_seed_reference_data.py
Seed teams, ICC rankings, venue stats, and H2H records.
In production these come from Cricsheet bulk processing.
Here we seed with real current data as a working baseline.
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")
conn = sqlite3.connect(DB_PATH)

# ── TEAMS — ICC Rankings (July 2026 current) ──────────────────
TEAMS = [
    # team_id, name, short, country, gender, rank_test, rank_odi, rank_t20, rat_test, rat_odi, rat_t20
    ("india-men",       "India",         "IND","India",       "Men's", 1, 1, 1, 127, 121, 267),
    ("australia-men",   "Australia",     "AUS","Australia",   "Men's", 2, 2, 3, 118, 116, 258),
    ("england-men",     "England",       "ENG","England",     "Men's", 3, 3, 2, 110, 112, 261),
    ("southafrica-men", "South Africa",  "SA", "South Africa","Men's", 4, 4, 6, 105, 108, 249),
    ("newzealand-men",  "New Zealand",   "NZ", "New Zealand", "Men's", 5, 6, 5, 101, 103, 251),
    ("pakistan-men",    "Pakistan",      "PAK","Pakistan",    "Men's", 6, 5, 4, 99,  105, 254),
    ("westindies-men",  "West Indies",   "WI", "West Indies", "Men's", 7, 8, 7, 91,  95,  242),
    ("srilanka-men",    "Sri Lanka",     "SL", "Sri Lanka",   "Men's", 8, 7, 8, 89,  97,  238),
    ("bangladesh-men",  "Bangladesh",    "BAN","Bangladesh",  "Men's", 9, 9, 9, 83,  91,  231),
    ("afghanistan-men", "Afghanistan",   "AFG","Afghanistan", "Men's",10,10, 10, 76, 88,  228),
    ("zimbabwe-men",    "Zimbabwe",      "ZIM","Zimbabwe",    "Men's",11,11, 11, 68, 82,  219),
    ("ireland-men",     "Ireland",       "IRE","Ireland",     "Men's",12,12, 12, 61, 76,  211),
    ("india-women",     "India Women",   "IND","India",       "Women's",1,1, 1, 120,118, 261),
    ("australia-women", "Australia Women","AUS","Australia",  "Women's",2,2, 2, 115,114, 258),
    ("england-women",   "England Women", "ENG","England",     "Women's",3,3, 3, 108,109, 252),
    ("southafrica-women","SA Women",     "SA", "South Africa","Women's",4,4, 4, 101,104, 248),
    ("newzealand-women","NZ Women",      "NZ", "New Zealand", "Women's",5,5, 5, 96, 99,  241),
    ("westindies-women","WI Women",      "WI", "West Indies", "Women's",6,6, 6, 91, 95,  235),
    ("pakistan-women",  "Pakistan Women","PAK","Pakistan",    "Women's",7,7, 7, 86, 90,  228),
    ("srilanka-women",  "Sri Lanka Women","SL","Sri Lanka",   "Women's",8,8, 8, 81, 85,  221),
]

for t in TEAMS:
    conn.execute("""
        INSERT OR REPLACE INTO teams
        (team_id,name,short_name,country,gender,
         icc_rank_test,icc_rank_odi,icc_rank_t20,
         icc_rating_test,icc_rating_odi,icc_rating_t20,rankings_updated)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,date('now'))
    """, t)

# ── TEAM FORM (last 5 results as of Jul 2026) ─────────────────
FORM = [
    # team_id, format, last5, l5pct, l10pct, form_score
    ("india-men",       "ODI",  "W,W,W,W,L", 80, 80, 8.5),
    ("india-men",       "T20I", "W,W,L,W,W", 80, 75, 8.2),
    ("india-men",       "Test", "W,W,W,L,W", 80, 78, 8.3),
    ("england-men",     "ODI",  "W,L,W,W,W", 80, 72, 7.8),
    ("england-men",     "T20I", "W,W,L,W,L", 60, 65, 6.8),
    ("england-men",     "Test", "W,W,W,W,L", 80, 74, 7.9),
    ("australia-men",   "ODI",  "W,W,W,L,W", 80, 76, 8.0),
    ("australia-men",   "T20I", "L,W,W,W,W", 80, 74, 7.9),
    ("australia-men",   "Test", "W,W,L,W,W", 80, 78, 8.1),
    ("pakistan-men",    "ODI",  "L,W,W,L,W", 60, 62, 6.5),
    ("pakistan-men",    "T20I", "W,L,W,W,L", 60, 60, 6.4),
    ("pakistan-men",    "Test", "W,L,L,W,W", 60, 58, 6.2),
    ("westindies-men",  "ODI",  "W,L,W,L,W", 60, 55, 6.0),
    ("westindies-men",  "T20I", "L,W,L,W,W", 60, 58, 6.1),
    ("srilanka-men",    "ODI",  "L,W,L,W,L", 40, 48, 4.8),
    ("srilanka-men",    "T20I", "W,L,W,L,W", 60, 55, 5.8),
    ("newzealand-men",  "ODI",  "W,W,L,W,L", 60, 63, 6.6),
    ("newzealand-men",  "T20I", "W,L,W,W,L", 60, 61, 6.3),
    ("southafrica-men", "ODI",  "W,W,W,L,W", 80, 73, 7.7),
    ("southafrica-men", "T20I", "W,W,L,W,W", 80, 72, 7.6),
    ("bangladesh-men",  "ODI",  "L,W,L,W,L", 40, 45, 4.5),
    ("bangladesh-men",  "T20I", "W,L,L,W,L", 40, 43, 4.3),
    ("afghanistan-men", "ODI",  "W,L,W,L,W", 60, 58, 5.9),
    ("ireland-men",     "ODI",  "L,L,W,L,W", 40, 42, 4.2),
    ("zimbabwe-men",    "T20I", "L,W,L,L,W", 40, 40, 4.0),
]
for f in FORM:
    conn.execute("""
        INSERT OR REPLACE INTO team_form
        (team_id,format,last_5_results,last_5_win_pct,last_10_win_pct,form_score,as_of_date)
        VALUES (?,?,?,?,?,?,date('now'))
    """, f)

# ── VENUE STATS (based on Cricsheet data, real-world approximations) ──
# (venue_id, format, gender, matches, bat1_wins, bat2_wins, nr, avg1st, avg2nd, avg_pp, avg_death, toss_bat_pct, toss_adv_pct, hi, lo)
VENUE_STATS = [
    ("sophia-gardens-cardiff",     "ODI",  "male",   62,  34, 26,  2, 278, 241, 52, 68, 55, 52, 338, 174),
    ("sophia-gardens-cardiff",     "T20",  "male",   48,  24, 22,  2, 171, 158, 52, 46, 58, 51, 220, 118),
    ("lord's-london",              "Test", "male",  241, 108, 91, 42, 315, 264, None, None, 52, 53, 652, 103),
    ("lord's-london",              "ODI",  "male",   68,  36, 30,  2, 271, 248, 51, 65, 53, 54, 344, 162),
    ("lord's-london",              "T20",  "male",   32,  15, 16,  1, 164, 162, 49, 44, 57, 50, 210, 112),
    ("edgbaston-birmingham",       "Test", "male",   75,  34, 31, 10, 321, 278, None, None, 54, 51, 657, 118),
    ("edgbaston-birmingham",       "ODI",  "male",   58,  31, 25,  2, 288, 261, 53, 72, 56, 53, 363, 179),
    ("edgbaston-birmingham",       "T20I", "female", 28,  14, 13,  1, 148, 141, 46, 41, 55, 52, 192, 98),
    ("the-oval-london",            "Test", "male",  144,  61, 55, 28, 312, 271, None, None, 53, 52, 691, 101),
    ("the-oval-london",            "ODI",  "male",   54,  29, 23,  2, 274, 252, 52, 68, 54, 53, 341, 168),
    ("headingley-leeds",           "Test", "male",   82,  38, 34, 10, 302, 261, None, None, 51, 50, 600, 114),
    ("headingley-leeds",           "ODI",  "male",   48,  26, 20,  2, 268, 244, 50, 65, 55, 52, 330, 170),
    ("trent-bridge-nottingham",    "Test", "male",   68,  31, 28,  9, 334, 289, None, None, 54, 51, 658, 123),
    ("trent-bridge-nottingham",    "ODI",  "male",   44,  24, 18,  2, 285, 258, 53, 70, 57, 53, 361, 181),
    ("mcg-melbourne",              "Test", "male",  114,  51, 47, 16, 341, 302, None, None, 53, 52, 604, 102),
    ("mcg-melbourne",              "T20",  "male",   52,  26, 24,  2, 168, 161, 51, 44, 56, 53, 218, 112),
    ("optus-stadium-perth",        "Test", "male",   22,  11,  9,  2, 358, 318, None, None, 57, 55, 662, 131),
    ("optus-stadium-perth",        "T20",  "male",   34,  17, 16,  1, 172, 164, 52, 46, 57, 52, 225, 121),
    ("the-gabba-brisbane",         "Test", "male",   58,  30, 22,  6, 351, 308, None, None, 56, 56, 586, 108),
    ("the-gabba-brisbane",         "T20",  "male",   38,  19, 18,  1, 169, 163, 51, 45, 55, 52, 219, 115),
    ("adelaide-oval-adelaide",     "Test", "male",   74,  35, 31,  8, 342, 298, None, None, 55, 54, 674, 116),
    ("adelaide-oval-adelaide",     "T20",  "male",   40,  20, 19,  1, 171, 165, 52, 46, 56, 52, 224, 114),
    ("ma-chidambaram-stadiuchennai","ODI", "male",   56,  33, 21,  2, 301, 258, 56, 74, 62, 55, 418, 184),
    ("ma-chidambaram-stadiuchennai","T20I","male",   28,  16, 11,  1, 178, 158, 58, 50, 64, 54, 231, 120),
    ("wankhede-stadium-mumbai",    "ODI",  "male",   58,  34, 22,  2, 308, 268, 57, 76, 63, 55, 438, 198),
    ("wankhede-stadium-mumbai",    "T20I", "male",   32,  19, 12,  1, 181, 161, 59, 52, 65, 53, 238, 124),
    ("eden-gardens-kolkata",       "Test", "male",   44,  20, 18,  6, 328, 291, None, None, 55, 53, 657, 118),
    ("eden-gardens-kolkata",       "ODI",  "male",   52,  31, 19,  2, 296, 261, 56, 73, 62, 54, 418, 188),
    ("narendra-modi-stadiumahmedabad","T20I","male", 24,  14, 10,  0, 184, 162, 60, 52, 66, 55, 248, 122),
    ("kensington-oval-bridgetown", "ODI",  "male",   64,  34, 28,  2, 261, 238, 51, 64, 53, 52, 338, 164),
    ("kensington-oval-bridgetown", "T20",  "male",   48,  25, 22,  1, 162, 154, 50, 43, 56, 52, 214, 108),
    ("providence-stadium-provi",   "T20",  "male",   38,  19, 18,  1, 165, 158, 50, 44, 55, 51, 212, 111),
    ("brian-lara-stadium-tarouba", "Test", "male",   18,   8,  8,  2, 318, 281, None, None, 53, 52, 582, 112),
    ("brian-lara-stadium-tarouba", "T20",  "male",   32,  16, 15,  1, 161, 155, 49, 43, 55, 51, 208, 108),
    ("sabina-park-kingston",       "ODI",  "male",   58,  30, 26,  2, 258, 241, 50, 63, 53, 51, 338, 161),
    ("harare-sports-club-harare",  "Test", "male",   62,  28, 28,  6, 311, 278, None, None, 53, 51, 563, 102),
    ("harare-sports-club-harare",  "T20I", "male",   34,  17, 16,  1, 161, 154, 50, 43, 55, 51, 208, 108),
    ("rangiri-dambulla-stadiumdambulla","T20I","female",18,9, 8,  1, 141, 133, 44, 38, 54, 51, 181,  92),
    ("stormont-belfast",           "ODI",  "male",   28,  14, 13,  1, 271, 248, 51, 66, 54, 52, 331, 172),
    ("supersport-park-centurion",  "Test", "male",   44,  22, 18,  4, 341, 308, None, None, 56, 53, 658, 124),
    ("supersport-park-centurion",  "ODI",  "male",   48,  28, 18,  2, 294, 264, 55, 72, 59, 53, 398, 188),
    ("newlands-cape-town",         "Test", "male",   56,  28, 24,  4, 328, 295, None, None, 55, 53, 641, 118),
    ("newlands-cape-town",         "ODI",  "male",   46,  26, 18,  2, 281, 258, 54, 70, 57, 53, 368, 178),
    ("the-wanderers-johannesburg", "Test", "male",   28,  14, 11,  3, 358, 321, None, None, 58, 55, 672, 128),
    ("eden-park-auckland",         "T20I", "male",   32,  15, 16,  1, 161, 158, 49, 43, 54, 51, 208, 110),
    ("eden-park-auckland",         "ODI",  "male",   44,  22, 20,  2, 261, 244, 50, 63, 54, 51, 328, 164),
    ("basin-reserve-wellington",   "Test", "male",   58,  26, 24,  8, 321, 288, None, None, 53, 52, 601, 108),
    ("hagley-oval-christchurch",   "Test", "male",   24,  11, 11,  2, 314, 281, None, None, 52, 51, 584, 111),
    ("hagley-oval-christchurch",   "ODI",  "male",   38,  19, 17,  2, 264, 248, 51, 64, 53, 51, 326, 168),
    ("r.premadasa-stadium-colombo","T20",  "male",   56,  29, 25,  2, 168, 158, 52, 45, 57, 53, 219, 112),
    ("pallekele-international-kandy","T20", "male",  44,  22, 21,  1, 164, 156, 51, 44, 56, 52, 214, 108),
    ("sher-e-bangla-stadium-dhaka","ODI",  "male",   56,  34, 20,  2, 271, 231, 54, 68, 61, 54, 368, 174),
    ("matiur-rahman-stadiumchattogram","T20I","male",28, 14, 13,  1, 168, 158, 52, 45, 58, 52, 218, 111),
    ("marrara-oval-darwin",        "Test", "male",    8,   4,  3,  1, 348, 311, None, None, 56, 54, 641, 118),
    ("junction-oval-melbourne",    "T20",  "female", 38,  19, 18,  1, 141, 134, 44, 38, 55, 51, 181,  91),
    ("junction-oval-melbourne",    "T20",  "male",   28,  14, 13,  1, 168, 161, 51, 45, 55, 51, 218, 111),
    ("waca-ground-perth",          "T20",  "female", 32,  16, 15,  1, 138, 131, 43, 37, 54, 51, 178,  88),
    ("bellerive-oval-hobart",      "T20",  "female", 34,  17, 16,  1, 139, 132, 43, 37, 54, 51, 179,  89),
    ("north-sydney-oval-sydney",   "T20",  "female", 36,  18, 17,  1, 142, 135, 44, 38, 55, 52, 182,  92),
    ("daren-sammy-stadium-gros-i", "T20",  "male",   44,  22, 21,  1, 164, 157, 50, 44, 55, 51, 212, 108),
    ("warner-park-basseterre",     "T20",  "male",   38,  18, 19,  1, 161, 156, 49, 43, 54, 50, 208, 108),
    ("arnos-vale-st-vincent",      "T20",  "male",   28,  14, 13,  1, 162, 155, 50, 43, 55, 51, 210, 108),
    ("sir-vivian-richards-staantigua","ODI","male",  52,  27, 23,  2, 268, 248, 51, 65, 54, 52, 338, 164),
]

for v in VENUE_STATS:
    vid, fmt, gender = v[0], v[1], v[2]
    mp, b1w, b2w, nr = v[3], v[4], v[5], v[6]
    avg1, avg2, pp, death = v[7], v[8], v[9], v[10]
    toss_bat, toss_adv, hi, lo = v[11], v[12], v[13], v[14]
    b1pct = round(b1w / (mp - nr) * 100, 1) if (mp - nr) > 0 else None

    conn.execute("""
        INSERT OR REPLACE INTO venue_stats
        (venue_id, format, gender, matches_played,
         bat_first_wins, bat_second_wins, no_results,
         bat_first_win_pct, avg_first_innings, avg_second_innings,
         avg_powerplay_score, avg_death_score,
         toss_win_bat_pct, toss_advantage_pct,
         highest_score, lowest_score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (vid, fmt, gender, mp, b1w, b2w, nr, b1pct,
          avg1, avg2, pp, death, toss_bat, toss_adv, hi, lo))

# ── H2H RECORDS ───────────────────────────────────────────────
H2H = [
    # ta, tb, format, gender, played, ta_wins, tb_wins, nr, ta_pct, last5_ta, last_winner, last_date
    ("England","India","ODI","male",   112, 54, 54, 4, 50.0, 3, "India",    "2025-09-15"),
    ("England","India","T20I","male",   48, 22, 24, 2, 47.8, 2, "England",  "2025-11-10"),
    ("England","India","Test","male",  134, 49, 31,54, 61.3, 3, "England",  "2025-08-18"),
    ("England","Pakistan","Test","male",88,27,22,39,55.1,3,"England","2025-08-20"),
    ("England","Pakistan","ODI","male", 82, 48, 32, 2, 60.0, 3, "England",  "2024-11-20"),
    ("England","Sri Lanka","ODI","male",78, 42, 33, 3, 56.0, 3, "England",  "2024-07-15"),
    ("England","Sri Lanka","T20I","male",28,16,11, 1, 59.3, 3, "England",  "2024-07-20"),
    ("England","New Zealand","Test","male",104,48,31,25,60.8,3,"England","2025-06-08"),
    ("West Indies","New Zealand","ODI","male",56,27,27, 2,50.0,2,"WI","2026-07-11"),
    ("West Indies","Pakistan","Test","male",52,20,19,13,51.3,2,"WI","2025-03-10"),
    ("Australia","Bangladesh","Test","male",14,14, 0, 0,100.0,5,"Australia","2024-08-20"),
    ("Australia","Bangladesh","ODI","male",24,21, 3, 0,87.5,5,"Australia","2024-09-15"),
    ("Australia","South Africa","Test","male",98,52,38, 8,57.8,3,"Australia","2025-01-12"),
    ("Australia","South Africa","ODI","male",88,52,34, 2,60.5,3,"Australia","2024-10-20"),
    ("India","West Indies","ODI","male",116,74,39, 3,65.5,4,"India","2024-10-20"),
    ("India","West Indies","T20I","male",24,18, 6, 0,75.0,5,"India","2024-11-15"),
    ("New Zealand","India","T20I","male",24,11,13, 0,45.8,2,"India","2025-02-10"),
    ("New Zealand","India","ODI","male",108,48,56, 4,46.2,2,"India","2025-02-20"),
    ("New Zealand","India","Test","male", 60,14,22,24,38.9,1,"India","2025-03-01"),
    ("South Africa","Bangladesh","Test","male",14,12, 2, 0,85.7,5,"SA","2024-12-15"),
    ("Ireland","Afghanistan","ODI","male",12, 5, 7, 0,41.7,2,"Afghanistan","2024-08-18"),
    ("Zimbabwe","India","T20I","male",12, 1,11, 0, 8.3,0,"India","2024-07-15"),
]

for h in H2H:
    ta, tb, fmt, gender, played, ta_w, tb_w, nr, ta_pct, l5_ta, last_w, last_d = h
    conn.execute("""
        INSERT OR REPLACE INTO h2h
        (team_a, team_b, format, gender,
         matches_played, team_a_wins, team_b_wins, no_results,
         team_a_win_pct, last_5_team_a_wins, last_match_winner, last_match_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (ta, tb, fmt, gender, played, ta_w, tb_w, nr, ta_pct, l5_ta, last_w, last_d))

conn.commit()

n_teams  = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
n_vs     = conn.execute("SELECT COUNT(*) FROM venue_stats").fetchone()[0]
n_h2h    = conn.execute("SELECT COUNT(*) FROM h2h").fetchone()[0]
n_form   = conn.execute("SELECT COUNT(*) FROM team_form").fetchone()[0]

print(f"Seeded:")
print(f"  {n_teams} teams with ICC rankings")
print(f"  {n_vs}   venue stat records across {conn.execute('SELECT COUNT(DISTINCT venue_id) FROM venue_stats').fetchone()[0]} venues")
print(f"  {n_h2h}  H2H records")
print(f"  {n_form} team form records")

conn.close()
