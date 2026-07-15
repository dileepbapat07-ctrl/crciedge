"""
run.py — master entry point
Usage:
  python run.py setup          # first-time: build DB + seed all data
  python run.py brief          # today's daily brief
  python run.py brief 2026-08-07  # brief for a specific date
  python run.py brief 2026-08-07 9800  # brief with custom bankroll
  python run.py stats          # database statistics
"""
import sys, os, sqlite3, subprocess

DB_PATH  = os.path.join(os.path.dirname(__file__), "db/cricket_engine.db")
SCR_PATH = os.path.join(os.path.dirname(__file__), "scripts")
ENG_PATH = os.path.join(os.path.dirname(__file__), "engine")

def run_script(name):
    path = os.path.join(SCR_PATH, name)
    print(f"\n{'─'*50}")
    print(f"  Running: {name}")
    print(f"{'─'*50}")
    result = subprocess.run([sys.executable, path], capture_output=False)
    return result.returncode == 0

def setup():
    print("\n" + "="*60)
    print("  CRICKET BETTING ENGINE — FIRST-TIME SETUP")
    print("="*60)
    ok1 = run_script("01_seed_matches.py")
    ok2 = run_script("02_seed_reference_data.py")
    if ok1 and ok2:
        print("\n✅  Setup complete. Database ready.")
        print(f"    Location: {os.path.abspath(DB_PATH)}")
        stats()
    else:
        print("\n❌  Setup encountered errors.")

def brief(target_date=None, bankroll=5000.0):
    sys.path.insert(0, ENG_PATH)
    sys.path.insert(0, SCR_PATH)
    from engine.daily_brief import run_daily_brief
    run_daily_brief(target_date, bankroll)

def stats():
    if not os.path.exists(DB_PATH):
        print("Database not found. Run: python run.py setup")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    print(f"\n{'─'*50}")
    print("  DATABASE STATISTICS")
    print(f"{'─'*50}")
    tables = ["matches","venues","venue_stats","teams","team_form","h2h","weather","odds","confidence_scores","bet_log","bankroll"]
    for t in tables:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<22} {n:>6} rows")
    print(f"{'─'*50}")

    print("\n  MATCH DISTRIBUTION BY MONTH:")
    rows = conn.execute("""
        SELECT strftime('%b %Y', date) mo, phase, COUNT(*) n
        FROM matches GROUP BY mo, phase ORDER BY date
    """).fetchall()
    for r in rows:
        ph_label = "2%/bet" if r["phase"] == 1 else "1%/bet"
        bar = "█" * min(20, r["n"] // 2)
        print(f"  {r['mo']:<12} Phase {r['phase']} ({ph_label})  {bar}  {r['n']} bets")

    print("\n  VENUE COVERAGE:")
    rows2 = conn.execute("""
        SELECT v.name, v.city, COUNT(vs.id) as stat_records
        FROM venues v
        LEFT JOIN venue_stats vs ON v.venue_id = vs.venue_id
        GROUP BY v.venue_id ORDER BY stat_records DESC LIMIT 15
    """).fetchall()
    for r in rows2:
        print(f"  {r['name'][:30]:<30} {r['city']:<18} {r['stat_records']} stat records")
    conn.close()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "setup":
        setup()
    elif cmd == "brief":
        d  = sys.argv[2] if len(sys.argv) > 2 else None
        bk = float(sys.argv[3]) if len(sys.argv) > 3 else 5000.0
        brief(d, bk)
    elif cmd == "stats":
        stats()
    else:
        print(__doc__)
