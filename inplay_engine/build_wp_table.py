"""
inplay_engine/build_wp_table.py
================================
One-time builder. Processes Cricsheet ball-by-ball CSV data from 2024+
and builds a win probability lookup table stored in inplay_engine.db.

The table answers: "Given this exact match state, what % of teams
in the same situation went on to win?"

This is Approach B — empirical frequency lookup, not a formula.
Covers T20, T20I, ODI and 100-ball formats.

USAGE:
  # With real Cricsheet data:
  python build_wp_table.py --data-dir /path/to/cricsheet_csvs

  # Demo mode (synthetic but realistic distributions):
  python build_wp_table.py --demo

CRICSHEET DOWNLOAD:
  https://cricsheet.org/downloads/
  Download all_csv2.zip → extract → pass folder as --data-dir
"""

import sqlite3, os, sys, csv, argparse, random, math
from collections import defaultdict
from datetime import date

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "inplay_engine.db")

DATA_START = "2024-01-01"

# ── Bin boundaries ────────────────────────────────────────────
# Binning ensures every cell has enough observations (target: 30+)
# balls_remaining bins (every 5 balls)
# runs_needed bins (every 8 runs for T20, every 15 for ODI)

FORMAT_CONFIG = {
    "T20": {
        "total_balls": 120,
        "par_rr": 8.0,         # average scoring rate
        "balls_bin": 5,         # bin size for balls remaining
        "runs_bin": 8,          # bin size for runs needed
        "max_runs": 240,
    },
    "T20I": {
        "total_balls": 120,
        "par_rr": 8.0,
        "balls_bin": 5,
        "runs_bin": 8,
        "max_runs": 240,
    },
    "100b": {
        "total_balls": 100,
        "par_rr": 9.6,
        "balls_bin": 5,
        "runs_bin": 8,
        "max_runs": 220,
    },
    "ODI": {
        "total_balls": 300,
        "par_rr": 5.5,
        "balls_bin": 12,
        "runs_bin": 15,
        "max_runs": 500,
    },
    "Test": None,  # skip — in-play model doesn't apply to Tests
}

def bin_val(val, bin_size, max_val):
    """Round val down to nearest bin_size bucket."""
    v = min(int(val), max_val)
    return (v // bin_size) * bin_size

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wp_lookup (
            format          TEXT NOT NULL,
            innings         INTEGER NOT NULL,   -- 1 or 2
            balls_remaining INTEGER NOT NULL,   -- binned
            wickets_lost    INTEGER NOT NULL,   -- 0-9
            runs_needed     INTEGER,            -- binned, NULL for 1st innings
            -- outcomes
            batting_wins    INTEGER DEFAULT 0,
            total_matches   INTEGER DEFAULT 0,
            win_pct         REAL,               -- batting_wins / total_matches
            -- confidence
            sample_size     INTEGER DEFAULT 0,
            confidence      TEXT,               -- high/medium/low
            -- metadata
            built_at        TEXT DEFAULT (datetime('now')),
            data_from       TEXT DEFAULT '2024-01-01',
            PRIMARY KEY (format, innings, balls_remaining, wickets_lost, runs_needed)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wp_build_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            built_at    TEXT,
            format      TEXT,
            matches_processed INTEGER,
            balls_processed   INTEGER,
            data_from   TEXT
        )
    """)
    conn.commit()
    return conn

# ── Process Cricsheet directory ───────────────────────────────
def process_cricsheet(data_dir: str, conn: sqlite3.Connection):
    """
    Reads Cricsheet ball-by-ball CSVs.
    Each match = one *_info.csv (metadata) + one *.csv (deliveries).
    """
    print(f"\n  Scanning {data_dir}...")

    # Find all delivery CSVs (not info files)
    delivery_files = []
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if f.endswith(".csv") and "_info" not in f:
                delivery_files.append(os.path.join(root, f))

    delivery_files.sort()
    print(f"  Found {len(delivery_files)} match files")

    # Accumulator: {(format, innings, balls_rem_bin, wkts, runs_bin): [win, total]}
    acc = defaultdict(lambda: [0, 0])

    processed = 0
    skipped   = 0

    for fpath in delivery_files:
        try:
            # Read delivery file
            deliveries = []
            with open(fpath, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    deliveries.append(row)

            if not deliveries:
                continue

            # Get match metadata from first row
            fmt_raw = deliveries[0].get('match_type', deliveries[0].get('type', ''))
            fmt = _map_format(fmt_raw)
            if fmt not in FORMAT_CONFIG or FORMAT_CONFIG[fmt] is None:
                skipped += 1
                continue

            match_date = deliveries[0].get('start_date', deliveries[0].get('date', ''))
            if match_date < DATA_START:
                skipped += 1
                continue

            cfg = FORMAT_CONFIG[fmt]
            total_balls = cfg["total_balls"]
            runs_bin    = cfg["runs_bin"]
            balls_bin   = cfg["balls_bin"]

            # Extract innings data
            innings_data = defaultdict(lambda: {
                'balls': [], 'team': None, 'target': None
            })

            for d in deliveries:
                inn_num = int(d.get('innings', 1))
                innings_data[inn_num]['balls'].append(d)
                if innings_data[inn_num]['team'] is None:
                    innings_data[inn_num]['team'] = d.get('batting_team', '')

            # Process second innings (where we have a target)
            if 2 not in innings_data:
                continue

            inn1 = innings_data[1]['balls']
            inn2 = innings_data[2]['balls']

            # Calculate first innings total
            inn1_runs = sum(
                int(d.get('runs_off_bat', 0)) + int(d.get('extras', 0))
                for d in inn1
            )
            target = inn1_runs + 1

            # Determine match winner
            winner = deliveries[-1].get('winner', '')
            batting_team_2 = innings_data[2]['team']
            chasing_won = (winner == batting_team_2)

            # Walk through 2nd innings ball by ball
            cum_runs  = 0
            cum_wkts  = 0
            balls_done = 0

            for ball in inn2:
                bat_runs  = int(ball.get('runs_off_bat', 0))
                extras    = int(ball.get('extras', 0))
                is_wicket = bool(ball.get('player_dismissed', ''))
                is_wide   = ball.get('wides', '0') != '0'
                is_nb     = ball.get('noballs', '0') != '0'

                # Record state BEFORE this ball
                runs_needed   = target - cum_runs
                balls_remaining = total_balls - balls_done

                if balls_remaining > 0 and runs_needed > 0 and cum_wkts < 10:
                    br_bin = bin_val(balls_remaining, balls_bin, total_balls)
                    rn_bin = bin_val(runs_needed, runs_bin, cfg['max_runs'])

                    key = (fmt, 2, br_bin, cum_wkts, rn_bin)
                    acc[key][0] += 1 if chasing_won else 0
                    acc[key][1] += 1

                # Update state
                cum_runs += bat_runs + extras
                if is_wicket:
                    cum_wkts += 1
                if not is_wide and not is_nb:
                    balls_done += 1

                # Stop if match over
                if cum_runs >= target or cum_wkts >= 10 or balls_done >= total_balls:
                    break

            processed += 1
            if processed % 200 == 0:
                print(f"  Processed {processed} matches...")

        except Exception as e:
            skipped += 1

    print(f"  Done: {processed} processed, {skipped} skipped")
    _write_acc(acc, conn, processed)

# ── Build synthetic demo data ─────────────────────────────────
def build_demo(conn: sqlite3.Connection):
    """
    Build realistic win probability distributions without Cricsheet data.
    Uses known cricket probabilities as seeds.
    """
    print("  Building demo win probability table (2024+ synthetic)...")
    random.seed(2024)

    acc = defaultdict(lambda: [0, 0])
    total_balls_gen = 0

    for fmt, cfg in FORMAT_CONFIG.items():
        if cfg is None:
            continue

        total_balls = cfg["total_balls"]
        par_rr      = cfg["par_rr"]
        runs_bin    = cfg["runs_bin"]
        balls_bin   = cfg["balls_bin"]
        max_runs    = cfg["max_runs"]

        # Simulate 800 matches per format
        n_matches = 800

        for _ in range(n_matches):
            # Random target between 130-220 (T20) or 220-360 (ODI)
            if fmt in ("T20","T20I","100b"):
                target = random.randint(130, 220)
            else:
                target = random.randint(220, 360)

            # Simulate a chase using realistic scoring model
            cum_runs = 0; cum_wkts = 0; balls_done = 0
            states = []  # (balls_rem, wkts, runs_needed) before each ball

            while balls_done < total_balls and cum_wkts < 10 and cum_runs < target:
                runs_needed    = target - cum_runs
                balls_remaining = total_balls - balls_done

                states.append((balls_remaining, cum_wkts, runs_needed))

                # Scoring model: probability based on resources
                rr_needed = runs_needed / (balls_remaining / 6) if balls_remaining > 0 else 99
                rr_ratio  = rr_needed / par_rr

                # Base scoring probability per ball
                p_dot    = max(0.20, min(0.60, 0.35 + (rr_ratio - 1) * 0.15))
                p_1      = 0.25
                p_2      = 0.12
                p_3      = 0.04
                p_4      = max(0.05, min(0.15, 0.10 - (rr_ratio - 1) * 0.03))
                p_6      = max(0.03, min(0.12, 0.07 + (rr_ratio - 1) * 0.02))
                p_wicket = max(0.03, min(0.12, 0.06 + (rr_ratio - 1) * 0.02))

                # Normalize
                total_p = p_dot + p_1 + p_2 + p_3 + p_4 + p_6 + p_wicket
                r = random.random() * total_p

                if r < p_dot:
                    scored = 0
                elif r < p_dot + p_1:
                    scored = 1
                elif r < p_dot + p_1 + p_2:
                    scored = 2
                elif r < p_dot + p_1 + p_2 + p_3:
                    scored = 3
                elif r < p_dot + p_1 + p_2 + p_3 + p_4:
                    scored = 4
                elif r < p_dot + p_1 + p_2 + p_3 + p_4 + p_6:
                    scored = 6
                else:
                    scored = 0
                    cum_wkts += 1

                cum_runs  += scored
                balls_done += 1
                total_balls_gen += 1

            chasing_won = cum_runs >= target

            # Record all states from this match
            for (br, wk, rn) in states:
                br_bin = bin_val(br, balls_bin, total_balls)
                rn_bin = bin_val(rn, runs_bin, max_runs)
                key = (fmt, 2, br_bin, wk, rn_bin)
                acc[key][0] += 1 if chasing_won else 0
                acc[key][1] += 1

    print(f"  Generated {total_balls_gen:,} ball states from {n_matches * len([f for f,c in FORMAT_CONFIG.items() if c])} matches")
    _write_acc(acc, conn, n_matches * 4)

def _map_format(fmt_raw: str) -> str:
    m = {
        "T20":  "T20I",  # international T20
        "IT20": "T20",   # domestic T20
        "ODI":  "ODI",
        "Test": "Test",
        "100-ball": "100b",
    }
    return m.get(fmt_raw, fmt_raw)

def _write_acc(acc, conn, n_processed):
    print(f"  Writing {len(acc):,} state cells to DB...")

    conn.execute("DELETE FROM wp_lookup")

    rows = []
    for (fmt, inn, br, wk, rn), (wins, total) in acc.items():
        if total < 5:
            continue
        wp  = round(wins / total * 100, 2)
        conf = "high" if total >= 50 else "medium" if total >= 20 else "low"
        rows.append((fmt, inn, br, wk, rn, wins, total, wp, total, conf,
                     DATA_START))

    conn.executemany("""
        INSERT OR REPLACE INTO wp_lookup
        (format, innings, balls_remaining, wickets_lost, runs_needed,
         batting_wins, total_matches, win_pct, sample_size, confidence, data_from)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, rows)

    conn.execute("""
        INSERT INTO wp_build_log (built_at, format, matches_processed,
                                  balls_processed, data_from)
        VALUES (datetime('now'), 'ALL', ?, ?, ?)
    """, (n_processed, sum(v[1] for v in acc.values()), DATA_START))

    conn.commit()

    n = conn.execute("SELECT COUNT(*) FROM wp_lookup").fetchone()[0]
    print(f"  ✅ {n:,} probability cells written")

    # Sample output
    print("\n  SAMPLE WIN PROBABILITIES:")
    print(f"  {'Fmt':<6} {'Inn'} {'BallsRem':>8} {'Wkts':>5} {'RunsNeeded':>10} {'WinPct':>8} {'n':>6} {'Conf'}")
    print("  " + "─"*65)
    samples = conn.execute("""
        SELECT format, innings, balls_remaining, wickets_lost,
               runs_needed, win_pct, sample_size, confidence
        FROM wp_lookup
        WHERE total_matches >= 20
        ORDER BY RANDOM() LIMIT 12
    """).fetchall()
    for s in samples:
        print(f"  {s[0]:<6} {s[1]:>3}  {s[2]:>8}  {s[3]:>5}  {s[4]:>10}  "
              f"{s[5]:>7.1f}%  {s[6]:>6}  {s[7]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", help="Cricsheet CSV directory")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    print("\n" + "="*58)
    print("  IN-PLAY WIN PROBABILITY TABLE BUILDER")
    print(f"  Data from: {DATA_START} onwards")
    print("="*58)

    conn = get_conn()

    if args.demo or not args.data_dir:
        print("\n  DEMO MODE — synthetic 2024+ distributions")
        print("  For production: python build_wp_table.py --data-dir /path\n")
        build_demo(conn)
    else:
        print(f"\n  Processing: {args.data_dir}\n")
        process_cricsheet(args.data_dir, conn)

    conn.close()
    print("\n  Build complete. Run wp_lookup.py to test queries.")
