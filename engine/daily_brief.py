"""
daily_brief.py
Run every morning. Produces the complete daily betting brief:
  - Fetches weather for today's venues
  - Runs decision engine on every match
  - Prints colour-coded terminal output
  - Returns structured data for the dashboard
"""
import sqlite3, os, sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../scripts"))

from decision_engine import decide, MatchContext, WEIGHTS

DB_PATH = os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")

# ANSI colours for terminal
G  = "\033[92m"   # green  — BET
Y  = "\033[93m"   # yellow — REDUCE
R  = "\033[91m"   # red    — SKIP/STOP
B  = "\033[94m"   # blue   — info
W  = "\033[97m"   # white
D  = "\033[90m"   # dim
NC = "\033[0m"    # reset

VERDICT_COL = {"BET": G, "REDUCE": Y, "SKIP": R, "STOP": R}

# Default inputs — in production these come from live odds feed
DEFAULT_ODDS     = 1.90
DEFAULT_WIN_PROB = 0.55

def format_currency(amount):
    return f"€{amount:,.2f}"

def verdict_bar(score):
    filled = int(score / 10)
    return "█" * filled + "░" * (10 - filled)

def run_daily_brief(target_date=None, bankroll=5000.0, verbose=True):
    if target_date is None:
        target_date = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Fetch weather first (silently)
    try:
        from fetch_weather import run as fetch_weather
        fetch_weather(target_date)
    except Exception as e:
        if verbose: print(f"{D}  Weather fetch: {e}{NC}")

    # Get all matches for today
    matches = conn.execute("""
        SELECT * FROM matches WHERE date=? ORDER BY step
    """, (target_date,)).fetchall()

    if not matches:
        if verbose: print(f"\n{D}No matches scheduled for {target_date}{NC}")
        conn.close()
        return []

    # Get current bankroll from tracker (if exists)
    bl_row = conn.execute("""
        SELECT closing_balance FROM bankroll
        ORDER BY date DESC, step DESC LIMIT 1
    """).fetchone()
    if bl_row:
        bankroll = bl_row["closing_balance"]

    conn.close()

    decisions = []
    for m in matches:
        ctx = MatchContext(
            match_id  = m["match_id"],
            date      = m["date"],
            label     = m["label"],
            team_a    = m["team_a"],
            team_b    = m["team_b"],
            format    = m["format"],
            category  = m["category"],
            gender    = m["gender"],
            venue_id  = m["venue_id"],
            city      = m["city"],
            step      = m["step"],
            phase     = m["phase"],
            bankroll  = bankroll,
            decimal_odds  = DEFAULT_ODDS,
            win_prob  = DEFAULT_WIN_PROB,
            player_status = "unknown",
            importance    = "high" if m["category"] in ("International","ICC Event") else "medium",
            toss_impact   = "high" if m["format"] == "Test" else "medium",
        )
        d = decide(ctx)
        decisions.append((m, d))

    if verbose:
        _print_brief(target_date, bankroll, decisions)

    return decisions

def _print_brief(target_date, bankroll, decisions):
    dt_display = datetime.strptime(target_date, "%Y-%m-%d").strftime("%A, %d %B %Y")
    bets   = [(m,d) for m,d in decisions if d.verdict == "BET"]
    reduce = [(m,d) for m,d in decisions if d.verdict == "REDUCE"]
    skips  = [(m,d) for m,d in decisions if d.verdict == "SKIP"]

    total_stake   = sum(d.recommended_stake for _,d in decisions)
    target_profit = sum(d.recommended_stake * 0.9 for _,d in bets)

    phase = decisions[0][0]["phase"] if decisions else 1
    step  = decisions[0][0]["step"] if decisions else 0

    print(f"\n{'═'*70}")
    print(f"{W}  CRICKET BETTING ENGINE — DAILY BRIEF{NC}")
    print(f"  {dt_display}")
    print(f"  Bankroll: {B}{format_currency(bankroll)}{NC}  |  "
          f"Phase {phase} ({'2%' if phase==1 else '1%'}/bet)  |  Step {step}")
    print(f"  {len(decisions)} matches today — "
          f"{G}{len(bets)} BET{NC}  "
          f"{Y}{len(reduce)} REDUCE{NC}  "
          f"{R}{len(skips)} SKIP{NC}")
    print(f"{'═'*70}\n")

    for m, d in sorted(decisions, key=lambda x: -x[1].confidence_score):
        col = VERDICT_COL.get(d.verdict, W)
        bar = verdict_bar(d.confidence_score)

        print(f"{col}  {'▶' if d.verdict=='BET' else '▷'} {d.team_a} vs {d.team_b}{NC}")
        print(f"     {D}{d.label} · {m['format']} · {m['city']} · {m['category']}{NC}")
        print(f"     Confidence: [{bar}] {d.confidence_score:.0f}/100")
        print(f"     EV: {'+' if d.ev_pct>0 else ''}{d.ev_pct:.1f}%  "
              f"Kelly: {d.kelly_pct:.1f}%  "
              f"Stake: {col}{format_currency(d.recommended_stake)}{NC}")
        print(f"     {col}{d.verdict}{NC}  —  {d.verdict_reason}")
        if d.override_applied:
            print(f"     {Y}⚠ Override: {d.override_reason}{NC}")
        print()

    print(f"{'─'*70}")
    print(f"  Total stake today:          {format_currency(total_stake)}")
    print(f"  Target profit (if all win): {G}{format_currency(target_profit)}{NC}")
    print(f"  Bankroll if all win:        {G}{format_currency(bankroll + target_profit)}{NC}")
    print(f"{'═'*70}\n")

def log_bet_outcome(match_id, outcome, odds_taken, stake, bankroll_before):
    """Call after each match to record result"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    pnl = (stake * odds_taken - stake) if outcome == "win" else (
           0 if outcome == "void" else -stake)
    bl_after = bankroll_before + pnl

    cs = conn.execute("""
        SELECT verdict, confidence_score, step, phase
        FROM confidence_scores cs
        JOIN matches m USING(match_id)
        WHERE cs.match_id=?
        ORDER BY cs.computed_at DESC LIMIT 1
    """, (match_id,)).fetchone()

    conn.execute("""
        INSERT INTO bet_log
        (match_id, bet_date, step, phase, bankroll_before,
         stake, odds_taken, confidence_score, verdict,
         outcome, profit_loss, bankroll_after)
        VALUES (?,date('now'),?,?,?,?,?,?,?,?,?,?)
    """, (match_id,
          cs["step"] if cs else None,
          cs["phase"] if cs else None,
          bankroll_before, stake, odds_taken,
          cs["confidence_score"] if cs else None,
          cs["verdict"] if cs else None,
          outcome, pnl, bl_after))

    conn.commit()
    conn.close()
    return bl_after

if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else None
    bk = float(sys.argv[2]) if len(sys.argv) > 2 else 5000.0
    run_daily_brief(d, bk)
