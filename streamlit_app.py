"""
streamlit_app.py
================
Cricket Betting Engine — Streamlit Cloud entry point.
Wraps the existing engine into a full web UI.
Deploy to: share.streamlit.io
"""

import streamlit as st
import sqlite3, sys, os, math
from datetime import date, datetime

# ── Path setup ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "elo_engine"))

DB_PATH = os.path.join(ROOT, "db", "cricket_engine.db")

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cricket Edge",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Dark theme tweaks */
[data-testid="stSidebar"] { background-color: #111720; }
[data-testid="stSidebar"] .stMarkdown p { color: #8AA0B8; font-size: 12px; }
.metric-card {
    background: #161D28; border: 1px solid #1E2A38;
    border-radius: 10px; padding: 14px 16px; text-align: center;
}
.metric-val { font-size: 22px; font-weight: 600; }
.metric-lbl { font-size: 11px; color: #5A7090; text-transform: uppercase; letter-spacing:.06em; margin-top:3px; }
.bet-card {
    background: #0D2A1C; border: 1px solid #1A4A30;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
}
.skip-card {
    background: #161D28; border: 1px solid #1E2A38;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
}
.reduce-card {
    background: #2A1E08; border: 1px solid #4A3510;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
}
.card-title { font-size: 15px; font-weight: 600; }
.card-meta  { font-size: 12px; color: #5A7090; margin-top: 2px; }
.card-reason{ font-size: 12px; color: #8AA0B8; margin-top: 8px; line-height:1.6; }
.elo-row { padding: 6px 0; border-bottom: 1px solid #1E2A38; font-size:13px; }
.elo-row:last-child { border-bottom: none; }
.supp-box {
    background: #0E1E2A; border: 1px solid #183050;
    border-radius: 8px; padding: 12px 14px; margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

# ── DB helper ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def query(sql, params=()):
    conn = get_db()
    return conn.execute(sql, params).fetchall()

# ── ELO helper (inline, no import needed) ─────────────────────────────────
def get_elo(team, gender, fmt):
    rows = query("SELECT rating FROM elo_ratings WHERE team_id=? AND gender=? AND format=?",
                 (team, gender, fmt))
    return rows[0]["rating"] if rows else 1500.0

def elo_win_prob(ra, rb, home_team=None, team_a=None):
    adj_a = ra + (100 if home_team == team_a else 0)
    adj_b = rb + (100 if home_team and home_team != team_a else 0)
    return 1 / (1 + 10 ** ((adj_b - adj_a) / 400))

def elo_factor(delta):
    score = 10 / (1 + math.exp(-delta / 150))
    return round(max(0.5, min(9.5, score)), 1)

# ── Kelly engine (inline) ──────────────────────────────────────────────────
def kelly(odds, wp, bankroll, phase):
    b = odds - 1
    q = 1 - wp
    kf = max(0, (b * wp - q) / b)
    frac = 0.25 if phase == 1 else 0.125
    stake = round(bankroll * kf * frac, 2)
    ev = round((wp * odds - 1) * 100, 1)
    return stake, ev, round(kf * frac * 100, 1)

def confidence(ev, form, h2h, weather, players, market=8.5, importance=6):
    ev_s = min(10, max(0, 5 + ev * 0.15)) if ev > 0 else max(0, 5 + ev * 0.2)
    raw = (ev_s*.22 + form*.14 + h2h*.10 + weather*.10 +
           players*.10 + market*.08 + importance*.07)
    return round(min(100, raw * 10.5))

def verdict(conf, ev):
    if conf >= 72 and ev > 0: return "BET", "#1DB87A"
    if conf >= 52 and ev > 0: return "REDUCE", "#E8A020"
    return "SKIP", "#5A7090"

# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🏏 Cricket Edge")
    st.markdown("*Betting Intelligence Engine*")
    st.divider()

    # Bankroll input — persists in session state
    if "bankroll" not in st.session_state:
        st.session_state.bankroll = 5000.0
    if "phase" not in st.session_state:
        st.session_state.phase = 1
    if "step" not in st.session_state:
        st.session_state.step = 1

    bk = st.number_input("Current bankroll (€)", min_value=100.0,
                          max_value=500000.0, value=st.session_state.bankroll,
                          step=100.0, format="%.2f")
    st.session_state.bankroll = bk

    TARGET = 124040
    progress = min(1.0, (bk - 5000) / (TARGET - 5000)) if bk > 5000 else 0
    st.progress(progress, text=f"€{bk:,.0f} / €{TARGET:,} target")

    phase = st.radio("Phase", [1, 2],
                     format_func=lambda x: f"Phase {x} ({'2%' if x==1 else '1%'}/bet)",
                     horizontal=True)
    st.session_state.phase = phase

    st.divider()
    page = st.radio("Navigate", [
        "📅 Daily brief",
        "🎯 Decision engine",
        "📊 Over/Under totals",
        "🔴 Match dashboard",
        "👁 In-play engine",
        "👤 Player analytics",
        "📈 Bankroll tracker",
        "🧬 ELO ratings",
        "🛡 Risk framework",
        "📋 Match schedule",
        "✏️ Log result",
        "⚙️ Settings & updates",
    ])
    st.divider()
    st.caption(f"Step {st.session_state.step}/193 · Phase {phase}")
    st.caption(f"DB: {os.path.basename(DB_PATH)}")
    st.caption("Cricket Edge v1.0 · 2026")

bankroll = st.session_state.bankroll
ph = st.session_state.phase

# ══════════════════════════════════════════════════════════════════════════
# PAGE: DAILY BRIEF
# ══════════════════════════════════════════════════════════════════════════
if page == "📅 Daily brief":
    import datetime as dt

    conn = get_db()
    today     = dt.date.today().isoformat()
    today_fmt = dt.date.today().strftime("%A, %d %B %Y")

    # ── Load this week's matches from DB ──────────────────────────────────
    week_end = (dt.date.today() + dt.timedelta(days=6)).isoformat()
    week_matches = conn.execute("""
        SELECT m.*,
               w.rain_prob_pct, w.condition, w.temp_celsius, w.dl_risk,
               vs.avg_first_innings, vs.bat_first_win_pct
        FROM matches m
        LEFT JOIN weather w ON w.venue_id = m.venue_id AND w.match_date = m.date
        LEFT JOIN venue_stats vs ON vs.venue_id = m.venue_id
            AND vs.format = m.format
            AND vs.gender = m.gender
        WHERE m.date BETWEEN ? AND ?
        ORDER BY m.date, m.step
    """, (today, week_end)).fetchall()

    logged_steps = set(
        r["step"] for r in
        conn.execute("SELECT step FROM bet_log").fetchall()
    )

    bk_row = conn.execute(
        "SELECT closing_balance FROM bankroll ORDER BY step DESC LIMIT 1"
    ).fetchone()
    current_bk = bk_row["closing_balance"] if bk_row else bankroll

    # ── Header ─────────────────────────────────────────────────────────────
    st.title("📅 Daily brief")
    st.markdown(f"**{today_fmt}** · Auto-generated from database · Phase {ph}")
    st.divider()

    today_matches = [m for m in week_matches if m["date"] == today]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bankroll",        f"€{current_bk:,.2f}")
    c2.metric("Today's matches", len(today_matches))
    c3.metric("This week",        len(week_matches))
    c4.metric("Bets logged",
              len([m for m in week_matches if m["step"] in logged_steps]))

    # ── Decision engine helper ──────────────────────────────────────────────
    try:
        sys.path.insert(0, os.path.join(ROOT, "engine"))
        from decision_engine import decide, MatchContext
        ENGINE_OK = True
    except Exception:
        ENGINE_OK = False

    def run_engine(m, bk):
        if not ENGINE_OK: return None
        try:
            odds_row = conn.execute("""
                SELECT decimal_odds FROM odds
                WHERE match_id=? AND market='match_winner' LIMIT 1
            """, (m["match_id"],)).fetchone()
            odds = odds_row["decimal_odds"] if odds_row else 1.90
            ra = get_elo(m["team_a"], "male" if m["gender"] in ("male","Men's") else "female", m["format"])
            rb = get_elo(m["team_b"], "male" if m["gender"] in ("male","Men's") else "female", m["format"])
            wp = elo_win_prob(ra, rb)
            ctx = MatchContext(
                match_id=m["match_id"], date=m["date"], label=m["label"],
                team_a=m["team_a"], team_b=m["team_b"],
                format=m["format"], category=m["category"],
                gender=m["gender"], venue_id=m["venue_id"], city=m["city"],
                step=m["step"], phase=m["phase"],
                bankroll=bk, decimal_odds=odds, win_prob=wp,
                player_status="unknown", importance="medium", toss_impact="medium",
            )
            return decide(ctx)
        except Exception:
            return None

    # ── TODAY'S MATCHES ────────────────────────────────────────────────────
    if today_matches:
        st.subheader(f"📌 Today — {dt.date.today().strftime('%a %d %b')}")
        for m in today_matches:
            d = run_engine(m, current_bk)
            already = m["step"] in logged_steps
            rain = m["rain_prob_pct"] or 0
            temp = m["temp_celsius"] or "—"
            wx   = f"{'☀️' if rain<20 else '🌦' if rain<50 else '🌧'} {m['condition'] or 'unknown'} · {temp}°C · Rain {rain:.0f}%"

            v = d.verdict if d else "—"
            css = "bet-card" if v=="BET" else "reduce-card" if v=="REDUCE" else "skip-card"
            vb  = "vb-bet"  if v=="BET" else "vb-red"    if v=="REDUCE" else "vb-ski"
            icon= "✅" if v=="BET" else "⚡" if v=="REDUCE" else "⏸"
            ev_s    = f"{d.ev_pct:+.1f}%"   if d else "—"
            conf_s  = f"{d.confidence_score:.0f}/100" if d else "—"
            stake_s = f"€{d.recommended_stake:,.2f}"  if d else "—"
            logged_s = " · ✅ Logged" if already else ""
            cat_tag = "ti" if m["category"]=="International" else "tf"

            st.markdown(f"""
            <div class="{css}">
              <div class="mch">
                <div>
                  <div class="mct">{m["team_a"]} vs {m["team_b"]}</div>
                  <div class="mcm"><span class="tag {cat_tag}">{m["category"]}</span>
                  {m["label"]} · {m["format"]} · {m["city"]} · Step {m["step"]}{logged_s}</div>
                </div>
                <div class="vb {vb}">{icon} {v}</div>
              </div>
              <div style="display:flex;gap:20px;margin:8px 0;font-size:13px;flex-wrap:wrap">
                <span>EV: <strong style="color:'#1DB87A' if d and d.ev_pct>0 else '#E84040'">{ev_s}</strong></span>
                <span>Confidence: <strong>{conf_s}</strong></span>
                <span>Stake: <strong>{stake_s}</strong></span>
              </div>
              <div class="mr">{wx}</div>
            </div>""", unsafe_allow_html=True)

            if d:
                with st.expander(f"Factor breakdown"):
                    import pandas as pd
                    fs = d.factor_scores
                    fdf = pd.DataFrame([
                        {"Factor":"Value edge (EV)","Score":fs.value_edge,"Weight":"22%"},
                        {"Factor":"Team form",      "Score":fs.form,      "Weight":"14%"},
                        {"Factor":"H2H / ELO",      "Score":fs.h2h,       "Weight":"10%"},
                        {"Factor":"Venue",           "Score":fs.venue,     "Weight":"10%"},
                        {"Factor":"Weather",         "Score":fs.weather,   "Weight":"10%"},
                        {"Factor":"Players",         "Score":fs.players,   "Weight":"10%"},
                        {"Factor":"Market",          "Score":fs.market,    "Weight":"8%"},
                        {"Factor":"Importance",      "Score":fs.importance,"Weight":"7%"},
                    ])
                    st.dataframe(fdf, width="stretch", hide_index=True,
                                 column_config={"Score": st.column_config.ProgressColumn(
                                     "Score", min_value=0, max_value=10, format="%.1f")})
                    ra = get_elo(m["team_a"],"male",m["format"])
                    rb = get_elo(m["team_b"],"male",m["format"])
                    st.caption(f"ELO: {m['team_a']} {ra:.0f} · {m['team_b']} {rb:.0f} · Delta {ra-rb:+.0f}")
    else:
        st.info(f"No matches scheduled for today ({today}). Next matches are coming up this week.")

    # ── REST OF WEEK ────────────────────────────────────────────────────────
    upcoming = [m for m in week_matches if m["date"] > today]
    if upcoming:
        st.divider()
        st.subheader("📆 Rest of this week")
        prev_date = None
        for m in upcoming:
            if m["date"] != prev_date:
                dobj = dt.date.fromisoformat(m["date"])
                st.markdown(f"**{dobj.strftime('%a %d %b')}**")
                prev_date = m["date"]
            d = run_engine(m, current_bk)
            already = m["step"] in logged_steps
            v    = d.verdict if d else "—"
            col  = "#1DB87A" if v=="BET" else "#E8A020" if v=="REDUCE" else "#5A7090"
            icon = "✅" if v=="BET" else "⚡" if v=="REDUCE" else "⏸"
            detail = f"EV {d.ev_pct:+.1f}% · Conf {d.confidence_score:.0f}/100 · Stake €{d.recommended_stake:,.2f}" if d else "No engine data"
            logged_s = " ✅" if already else ""
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:center;"
                f"padding:8px 12px;background:var(--card);border:1px solid var(--bdr);"
                f"border-radius:8px;margin-bottom:6px'>"
                f"<span style='font-size:13px'><strong>{m['team_a']} vs {m['team_b']}</strong>"
                f" <span style='color:#5A7090'>· {m['label']} · {m['format']} · Step {m['step']}{logged_s}</span></span>"
                f"<span style='font-size:12px;color:{col};font-weight:600'>{icon} {v}"
                f" <span style='color:#8AA0B8;font-weight:400'>· {detail}</span></span>"
                f"</div>", unsafe_allow_html=True)

    # ── Supplementary markets from DB ───────────────────────────────────────
    supp = conn.execute("""
        SELECT o.*, m.team_a, m.team_b, m.date
        FROM odds o JOIN matches m ON o.match_id = m.match_id
        WHERE m.date BETWEEN ? AND ? AND o.market NOT IN ('match_winner')
        ORDER BY m.date, o.market
    """, (today, week_end)).fetchall()

    if supp:
        st.divider()
        st.subheader("📊 Supplementary markets")
        for s in supp:
            ev = round((1/s["implied_prob"] - 1) * 100, 1) if s["implied_prob"] else 0
            col = "#1DB87A" if ev > 5 else "#5A7090"
            st.markdown(
                f"<div style='padding:7px 12px;background:var(--card);border:1px solid var(--bdr);"
                f"border-radius:8px;margin-bottom:5px;font-size:13px;"
                f"display:flex;justify-content:space-between'>"
                f"<span><strong>{s['team_a']} vs {s['team_b']}</strong> · {s['market']} · {s['selection']}</span>"
                f"<span style='color:{col}'>{s['decimal_odds']} odds · EV {ev:+.1f}%</span>"
                f"</div>", unsafe_allow_html=True)

    # ── Risk status ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🛡 Risk status")
    today_staked = sum(r["stake"] for r in
        conn.execute("SELECT stake FROM bet_log WHERE bet_date=?", (today,)).fetchall()) or 0.0
    daily_cap = round(current_bk * 0.05, 2)
    rem = max(0, daily_cap - today_staked)
    pct = min(100, round(today_staked/daily_cap*100, 1)) if daily_cap > 0 else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Staked today", f"€{today_staked:,.2f}", f"{pct}% of cap")
    c2.metric("Daily cap (5%)", f"€{daily_cap:,.2f}")
    c3.metric("Remaining today", f"€{rem:,.2f}",
              "✓ Safe" if rem > 0 else "⚠ At cap",
              delta_color="normal" if rem > 0 else "inverse")
    st.progress(pct/100, text=f"{pct}% of daily cap used")

    # ── Recent bets ──────────────────────────────────────────────────────────
    recent = conn.execute("""
        SELECT bl.*, m.team_a, m.team_b FROM bet_log bl
        LEFT JOIN matches m ON bl.match_id = m.match_id
        ORDER BY bl.step DESC LIMIT 5
    """).fetchall()
    if recent:
        st.divider()
        st.subheader("📋 Recent bets")
        for b in recent:
            icon = "✅" if b["outcome"]=="win" else "❌" if b["outcome"]=="loss" else "⬜"
            pnl = b["profit_loss"] or 0
            col = "#1DB87A" if pnl > 0 else "#E84040"
            st.markdown(
                f"<div style='padding:7px 12px;background:var(--card);border:1px solid var(--bdr);"
                f"border-radius:8px;margin-bottom:5px;font-size:13px;"
                f"display:flex;justify-content:space-between'>"
                f"<span>{icon} Step {b['step']} · {b['bet_date']} · "
                f"{b['team_a'] or '—'} vs {b['team_b'] or '—'}</span>"
                f"<span>€{b['stake']:,.2f} @ {b['odds_taken']} · "
                f"<strong style='color:{col}'>€{pnl:+,.2f}</strong></span>"
                f"</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: DECISION ENGINE
# ══════════════════════════════════════════════════════════════════════════
elif page == "🎯 Decision engine":
    st.title("🎯 Decision engine")
    st.divider()

    conn = get_db()

    # ── Optional: pick a match from schedule to pre-fill ──────
    st.subheader("Step 1 — Pick a match (optional)")
    st.caption("Select from schedule to auto-fill team names, or skip and enter manually below.")

    matches_de = conn.execute("""
        SELECT match_id, date, step, label, team_a, team_b,
               format, category, venue_id, gender
        FROM matches ORDER BY date, step
    """).fetchall()

    de_opts = {"— Enter manually —": None}
    de_opts.update({
        f"Step {m['step']:>3} | {m['date']} | {m['team_a']} vs {m['team_b']} [{m['format']}]":
        dict(m) for m in matches_de
    })

    sel_de = st.selectbox("Select match", list(de_opts.keys()), key="de_match")
    sel_m  = de_opts[sel_de]

    # Pre-fill defaults from selected match
    if sel_m:
        default_ta  = sel_m["team_a"]
        default_tb  = sel_m["team_b"]
        default_fmt = sel_m["format"]
        # Get ELO-based win probability
        ra = get_elo(sel_m["team_a"], "male", sel_m["format"])
        rb = get_elo(sel_m["team_b"], "male", sel_m["format"])
        default_wp = int(round(elo_win_prob(ra, rb) * 100))
        default_wp = max(30, min(75, default_wp))
    else:
        default_ta, default_tb, default_fmt = "India", "England", "ODI"
        default_wp = 55

    st.divider()
    st.subheader("Step 2 — Enter market details")

    # ── INPUT SECTION — full width, not hidden in columns ─────
    c1, c2 = st.columns(2)
    with c1:
        odds = st.number_input(
            "Betfair/bookmaker odds (decimal)",
            min_value=1.10, max_value=20.0, value=2.08, step=0.01, format="%.2f",
            help="e.g. 2.08 means you win €1.08 for every €1 staked"
        )
        wp = st.slider(
            "Your estimated win probability (%)",
            min_value=30, max_value=75, value=default_wp, step=1,
            help="Based on ELO, form, H2H. Auto-filled if you picked a match above."
        )
        bk_e = st.number_input(
            "Bankroll (€)",
            min_value=100.0, max_value=500000.0,
            value=float(int(bankroll)), step=100.0, format="%.2f"
        )
        ph_e = st.radio(
            "Phase",
            [1, 2],
            format_func=lambda x: f"Phase {x} — {'¼ Kelly (2%/bet)' if x==1 else '⅛ Kelly (1%/bet)'}",
            horizontal=True,
            index=ph - 1
        )

    with c2:
        st.markdown("**Condition factors** (1 = very poor · 10 = excellent)")
        form    = st.slider("Team form",            1.0, 10.0, 7.0, 0.5)
        h2h_s   = st.slider("H2H / ELO advantage", 1.0, 10.0, 6.0, 0.5)
        weather = st.slider("Weather conditions",  1,   10,   9,   1)
        players = st.slider("Player availability", 1,   10,   8,   1)

        if sel_m:
            # Auto-fetch ELO factor
            ra = get_elo(sel_m["team_a"], "male", sel_m["format"])
            rb = get_elo(sel_m["team_b"], "male", sel_m["format"])
            elo_f = elo_factor(ra - rb)
            st.caption(
                f"ELO: {sel_m['team_a']} **{ra:.0f}** · "
                f"{sel_m['team_b']} **{rb:.0f}** · "
                f"H2H factor auto-suggested: **{elo_f:.1f}/10**"
            )

    st.divider()
    st.subheader("Step 3 — Engine output")

    # ── COMPUTE ────────────────────────────────────────────────
    wp_f  = wp / 100
    stake, ev, kf_pct = kelly(odds, wp_f, bk_e, ph_e)
    conf  = confidence(ev, form, h2h_s, weather, players)
    v, vc = verdict(conf, ev)
    impl  = round(1 / odds * 100, 1)
    edge  = round(wp_f * 100 - impl, 1)

    # ── VERDICT ────────────────────────────────────────────────
    if v == "BET":
        st.success(f"## ✅ BET  ·  Stake €{stake:,.2f}  ·  EV {ev:+.1f}%  ·  Confidence {conf}/100")
    elif v == "REDUCE":
        st.warning(f"## ⚡ REDUCE STAKE  ·  Stake €{stake:,.2f}  ·  EV {ev:+.1f}%  ·  Confidence {conf}/100")
    else:
        st.info(f"## ⏸ SKIP  ·  EV {ev:+.1f}%  ·  Confidence {conf}/100  ·  No positive edge")

    st.progress(conf / 100, text=f"Confidence {conf}/100  (BET threshold: 72)")

    # ── METRICS ────────────────────────────────────────────────
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Stake",         f"€{stake:,.2f}")
    m2.metric("Expected value", f"{ev:+.1f}%",
              "Edge ✓" if ev > 0 else "No edge ✗")
    m3.metric("Confidence",    f"{conf}/100")
    m4.metric("Your edge",     f"{edge:+.1f}%",
              f"Mkt: {impl}%")
    m5.metric("Profit if win", f"+€{round(stake*(odds-1),2):,.2f}")
    m6.metric("Loss if lose",  f"-€{stake:,.2f}")

    # ── FACTOR TABLE ───────────────────────────────────────────
    st.divider()
    import pandas as pd
    fdf = pd.DataFrame([
        {"Factor":"Value edge (EV)", "Score": round(min(10,max(0,5+ev*0.15)),1), "Weight":"22%", "Contribution": round(min(10,max(0,5+ev*0.15))*0.22,2)},
        {"Factor":"Team form",       "Score": form,    "Weight":"14%", "Contribution": round(form*0.14,2)},
        {"Factor":"H2H / ELO",       "Score": h2h_s,   "Weight":"10%", "Contribution": round(h2h_s*0.10,2)},
        {"Factor":"Weather",         "Score": weather, "Weight":"10%", "Contribution": round(weather*0.10,2)},
        {"Factor":"Players",         "Score": players, "Weight":"10%", "Contribution": round(players*0.10,2)},
        {"Factor":"Market quality",  "Score": 8.5,     "Weight":"8%",  "Contribution": round(8.5*0.08,2)},
    ])
    st.dataframe(fdf, width="stretch", hide_index=True,
                 column_config={
                     "Score": st.column_config.ProgressColumn(
                         "Score", min_value=0, max_value=10, format="%.1f"),
                     "Contribution": st.column_config.NumberColumn(
                         "Contribution", format="%.2f"),
                 })

    # ── IN-PLAY GUIDANCE ──────────────────────────────────────
    if v == "BET" and sel_m:
        st.divider()
        st.subheader("In-play rules for this match")
        c1, c2, c3 = st.columns(3)
        max_inplay = round(bk_e * 0.05 - stake, 2)
        with c1:
            st.success(f"**Pre-match entry**\nStake €{stake:,.2f} now.\nExposure: {kf_pct:.1f}% of bankroll.")
        with c2:
            if max_inplay > 0:
                st.warning(f"**Optional in-play add**\nMax €{max_inplay:,.2f} more at innings break.\nOnly if EV still positive.")
            else:
                st.warning("**No in-play capacity**\nAlready at 5% daily cap.")
        with c3:
            st.error("**Hard stop**\nNever add after 15 overs of the chase. One match = max 5% bankroll.")

# ══════════════════════════════════════════════════════════════════════════
# PAGE: OVER/UNDER TOTALS
# ══════════════════════════════════════════════════════════════════════════
elif page == "📊 Over/Under totals":
    st.title("📊 Over / Under totals engine")
    st.markdown(
        "Compare our venue-based predicted score against the bookmaker's line. "
        "Edge exists when the gap is large enough — bookmakers use generic global averages, "
        "we use ground-specific Cricsheet data."
    )
    st.divider()

    sys.path.insert(0, os.path.join(ROOT, "engine"))
    from totals_engine import analyse_totals, TotalsContext

    conn = get_db()

    # Match selector
    matches = conn.execute("""
        SELECT match_id, date, step, phase, label, team_a, team_b,
               format, category, gender, venue_id, city
        FROM matches ORDER BY step ASC
    """).fetchall()

    col1, col2 = st.columns(2)
    with col1:
        fmt_tf = st.selectbox("Format", ["All","ODI","T20I","T20","Test"], key="tf_fmt")
    with col2:
        search_tf = st.text_input("Search team", "", key="tf_search")

    filtered = [m for m in matches
                if (fmt_tf == "All" or m["format"] == fmt_tf)
                and (not search_tf or search_tf.lower() in
                     (m["team_a"] + m["team_b"]).lower())]

    match_opts = {
        f"Step {m['step']:>3} | {m['date']} | {m['team_a']} vs {m['team_b']} [{m['format']}]":
        dict(m) for m in filtered
    }

    if not match_opts:
        st.warning("No matches found.")
    else:
        sel_lbl = st.selectbox(f"Select match ({len(match_opts)} shown)",
                               list(match_opts.keys()), key="tf_match")
        sm = match_opts[sel_lbl]

        # Get venue stats preview
        vs_row = conn.execute("""
            SELECT avg_first_innings, avg_second_innings, matches_played,
                   highest_score, lowest_score
            FROM venue_stats
            WHERE venue_id=? AND format IN (?,?,?)
            AND avg_first_innings IS NOT NULL
            ORDER BY
                CASE format
                    WHEN ? THEN 1
                    WHEN 'T20' THEN 2
                    WHEN 'T20I' THEN 3
                    ELSE 4
                END,
                matches_played DESC
            LIMIT 1
        """, (sm["venue_id"],
              sm["format"],
              "T20" if sm["format"] in ("T20I","T20","100b") else sm["format"],
              "100b" if sm["format"] == "100b" else sm["format"],
              sm["format"])).fetchone()

        # Show venue baseline
        if vs_row and vs_row["avg_first_innings"]:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Venue avg 1st innings", f"{vs_row['avg_first_innings']:.0f}")
            c2.metric("Venue avg 2nd innings", f"{vs_row['avg_second_innings'] or 'N/A'}")
            c3.metric("Venue matches", vs_row["matches_played"])
            c4.metric("Highest score", vs_row["highest_score"] or "N/A")
        else:
            st.warning("No venue stats found — results will use defaults.")

        st.divider()
        st.subheader("Enter bookmaker lines")
        st.caption("Get these from Betfair, Bet365 or Sportsbet on match morning")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**1st innings line**")
            use_first = st.checkbox("Bet on 1st innings total", value=True)
            bk_first  = st.number_input(
                "Bookmaker 1st innings line",
                min_value=50.0, max_value=500.0,
                value=285.0 if sm["format"] in ("ODI","Test") else 162.0,
                step=0.5, format="%.1f",
                disabled=not use_first
            )
            odds_over_f  = st.number_input("Odds for OVER", 1.50, 3.00, 1.90, 0.01,
                                           format="%.2f", disabled=not use_first)
            odds_under_f = st.number_input("Odds for UNDER", 1.50, 3.00, 1.90, 0.01,
                                           format="%.2f", disabled=not use_first)

        with col2:
            st.markdown("**Match total line (both innings)**")
            use_total = st.checkbox("Bet on match total", value=False)
            bk_total  = st.number_input(
                "Bookmaker match total line",
                min_value=100.0, max_value=1000.0,
                value=580.0 if sm["format"] in ("ODI","Test") else 320.0,
                step=0.5, format="%.1f",
                disabled=not use_total
            )

        st.divider()
        st.subheader("Conditions")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            weather_sc = st.slider("Weather (1–10)", 1, 10, 8, key="tf_wx")
        with col2:
            pitch_t = st.selectbox("Pitch type",
                ["flat","good","neutral","spin","green","deteriorating"],
                key="tf_pitch")
        with col3:
            dew = st.checkbox("Dew expected (D/N)", key="tf_dew")
        with col4:
            gender_tf = st.radio("Gender", ["male","female"], horizontal=True,
                                 key="tf_gen",
                                 format_func=lambda x: "Men's" if x=="male" else "Women's")

        if st.button("🔍 Analyse totals market", type="primary"):
            ctx = TotalsContext(
                match_id      = sm["match_id"],
                venue_id      = sm["venue_id"],
                format        = sm["format"],
                gender        = gender_tf,
                team_a        = sm["team_a"],
                team_b        = sm["team_b"],
                bankroll      = bankroll,
                phase         = ph,
                bk_line_first = bk_first if use_first else None,
                bk_line_total = bk_total if use_total else None,
                bk_odds_over  = odds_over_f,
                bk_odds_under = odds_under_f,
                weather_score = float(weather_sc),
                pitch_type    = pitch_t,
                dew_expected  = dew,
            )

            result = analyse_totals(ctx)

            st.divider()
            st.subheader("Engine output")

            # Predictions
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Predicted 1st innings", f"{result.predicted_first:.0f}")
            c2.metric("Predicted match total", f"{result.predicted_total:.0f}")
            if use_first:
                gap_col = "normal" if result.gap_first > 0 else "inverse"
                c3.metric("Gap to 1st innings line",
                          f"{result.gap_first:+.0f} runs",
                          delta_color=gap_col)
            if use_total:
                c4.metric("Gap to total line", f"{result.gap_total:+.0f} runs")

            st.divider()

            # EV table
            import pandas as pd
            ev_data = []
            if use_first:
                ev_data.append({
                    "Market": "1st innings OVER",
                    "Line": f"{bk_first:.1f}",
                    "Odds": odds_over_f,
                    "EV %": f"{result.ev_first_over:+.1f}%",
                    "Edge": "✅" if result.ev_first_over > 0 else "❌"
                })
                ev_data.append({
                    "Market": "1st innings UNDER",
                    "Line": f"{bk_first:.1f}",
                    "Odds": odds_under_f,
                    "EV %": f"{result.ev_first_under:+.1f}%",
                    "Edge": "✅" if result.ev_first_under > 0 else "❌"
                })
            if use_total:
                ev_data.append({
                    "Market": "Match total OVER",
                    "Line": f"{bk_total:.1f}",
                    "Odds": odds_over_f,
                    "EV %": f"{result.ev_total_over:+.1f}%",
                    "Edge": "✅" if result.ev_total_over > 0 else "❌"
                })
                ev_data.append({
                    "Market": "Match total UNDER",
                    "Line": f"{bk_total:.1f}",
                    "Odds": odds_under_f,
                    "EV %": f"{result.ev_total_under:+.1f}%",
                    "Edge": "✅" if result.ev_total_under > 0 else "❌"
                })
            if ev_data:
                st.dataframe(pd.DataFrame(ev_data),
                             width="stretch", hide_index=True)

            st.divider()

            # Final verdict
            if result.verdict == "BET":
                st.success(f"""
                ### ✅ BET — {result.best_bet}
                **EV: {result.best_ev:+.1f}%** · Confidence: {result.confidence:.0f}/100 · Stake: **€{result.recommended_stake:,.2f}**

                {result.reason}
                """)
            elif result.verdict == "REDUCE":
                st.warning(f"""
                ### ⚡ REDUCE STAKE — {result.best_bet}
                **EV: {result.best_ev:+.1f}%** · Confidence: {result.confidence:.0f}/100 · Stake: **€{result.recommended_stake:,.2f}**

                {result.reason}
                """)
            else:
                st.info(f"""
                ### ⏸ SKIP totals market
                {result.reason}

                **Venue avg:** {result.venue_avg_first:.0f} (1st innings) from {result.venue_matches} matches
                """)

# ══════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════
# PAGE: MATCH DASHBOARD
# ══════════════════════════════════════════════════════════════════════════
elif page == "🔴 Match dashboard":
    import datetime as dt
    import requests as _req
    import re as _re

    st.title("🔴 Match dashboard")
    st.markdown(
        "Track one match at a time from toss to result. "
        "Each match has its own independent tracker."
    )
    st.divider()

    conn  = get_db()
    today = dt.date.today().isoformat()
    yest  = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    nxt7  = (dt.date.today() + dt.timedelta(days=7)).isoformat()

    # ── Load matches ───────────────────────────────────────────
    window = conn.execute("""
        SELECT match_id, date, step, label, team_a, team_b,
               format, venue_id, gender, category, city
        FROM matches WHERE date BETWEEN ? AND ?
        ORDER BY date, step
    """, (yest, nxt7)).fetchall()

    if not window:
        st.info("No matches in window. Check match schedule.")
        st.stop()

    # ── Group by date ──────────────────────────────────────────
    from itertools import groupby
    date_groups = {}
    for m in window:
        d = m["date"]
        tag = "🟡 Yesterday" if d==yest else               "🔴 Today"     if d==today else               dt.date.fromisoformat(d).strftime("%a %d %b")
        date_groups.setdefault(tag, []).append(dict(m))

    # ── Date picker first ──────────────────────────────────────
    col1, col2 = st.columns([1, 2])
    with col1:
        date_sel = st.selectbox(
            "Date",
            list(date_groups.keys()),
            key="dash_date",
            help="Select the day first"
        )

    day_matches = date_groups[date_sel]

    # ── Gender filter + Match picker ───────────────────────────
    # Check if this day has both men's and women's matches
    has_men   = any("female" not in dict(m).get("gender","") and "Women" not in m["team_a"]
                    for m in day_matches)
    has_women = any("female" in dict(m).get("gender","") or "Women" in m["team_a"]
                    for m in day_matches)

    with col2:
        if has_men and has_women:
            gender_filter = st.radio(
                "Gender",
                ["👨 Men's", "👩 Women's"],
                horizontal=True,
                key="dash_gender",
                help="Men's and Women's matches on the same day track independently"
            )
            is_female = gender_filter == "👩 Women's"
            filtered_day = [
                m for m in day_matches
                if ("female" in dict(m).get("gender","") or "Women" in m["team_a"]) == is_female
            ]
        else:
            # Only one gender today — no filter needed
            filtered_day = day_matches
            gender_icon  = "👩 Women's" if has_women else "👨 Men's"
            st.markdown(
                f"<div style='padding:6px 10px;background:var(--card);"
                f"border:1px solid var(--bdr);border-radius:8px;"
                f"font-size:13px;color:var(--text-secondary)'>"
                f"{gender_icon} only</div>",
                unsafe_allow_html=True
            )

    # ── Match picker (after gender filter) ────────────────────
    match_opts = {}
    for m in filtered_day:
        key = f"{m['team_a']} vs {m['team_b']} · {m['label']} [{m['format']}]"
        match_opts[key] = m

    if not match_opts:
        st.warning("No matches found for this selection.")
        st.stop()

    n_shown = len(match_opts)
    match_sel = st.selectbox(
        f"{n_shown} match{'es' if n_shown>1 else ''} — select to track",
        list(match_opts.keys()),
        key="dash_match",
        help="Each match has its own independent tracker"
    )

    match = match_opts[match_sel]
    mid   = match["match_id"]
    ta    = match["team_a"]
    tb    = match["team_b"]
    fmt   = match["format"]
    gender= "female" if any(w in (match.get("gender","") or "").lower()
                            for w in ["female","women"]) else "male"

    # ── Match info strip ───────────────────────────────────────
    d_label = ("🟡 Yesterday" if match["date"]==yest else
               "🔴 Today — LIVE" if match["date"]==today else
               dt.date.fromisoformat(match["date"]).strftime("%A %d %b"))
    gender_str = "Women's" if gender=="female" else "Men's"

    st.markdown(
        f"<div style='padding:10px 16px;background:var(--card);"
        f"border:1px solid var(--bdr);border-radius:10px;"
        f"display:flex;justify-content:space-between;align-items:center'>"
        f"<div>"
        f"<span style='font-size:15px;font-weight:600'>{ta} vs {tb}</span>"
        f"<span style='font-size:12px;color:#5A7090;margin-left:10px'>"
        f"{match['label']} · {match['format']} · {gender_str} · {match.get('city','')} · Step {match['step']}"
        f"</span></div>"
        f"<span style='color:#00C8A0;font-size:12px;font-weight:600'>{d_label}</span>"
        f"</div>",
        unsafe_allow_html=True
    )

    # ── Per-match session state (keyed by match_id) ────────────
    sk = f"dash_{mid}"   # unique state key per match
    if sk not in st.session_state:
        st.session_state[sk] = {
            "phase":  "pre_toss",
            "toss":   {},
            "xi":     {},
            "signal": None,
            "score":  {},
        }
    S = st.session_state[sk]   # shorthand

    st.divider()

    # ── Phase progress bar ─────────────────────────────────────
    phases       = ["pre_toss","xi_confirmed","match_live","completed"]
    phase_labels = ["⏳ Pre-toss","🪙 XI ready","🔴 Live","✅ Done"]
    p_idx = phases.index(S["phase"]) if S["phase"] in phases else 0

    pcols = st.columns(4)
    for i,(pl,pp) in enumerate(zip(phase_labels,phases)):
        with pcols[i]:
            if i < p_idx:
                st.success(pl)
            elif i == p_idx:
                st.warning(f"**{pl}**")
            else:
                st.markdown(
                    f"<div style='padding:8px;background:var(--sur);"
                    f"border:1px solid var(--bdr);border-radius:8px;"
                    f"text-align:center;font-size:12px;color:#5A7090'>{pl}</div>",
                    unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════════════════
    # STEP 1 — TOSS & XI
    # ══════════════════════════════════════════════════════════
    with st.expander(
        f"🪙 Step 1 — Toss & Playing XI  "
        f"{'✅ Done' if p_idx>=1 else '← Start here'}",
        expanded=(p_idx==0)
    ):
        c1,c2 = st.columns(2)
        with c1:
            toss_winner = st.selectbox("Toss won by",[ta,tb,"—"],key=f"{sk}_tw")
            toss_choice = st.radio("Elected to",["bat","field"],
                                   horizontal=True,key=f"{sk}_tc")
        with c2:
            xi_paste = st.text_area(
                "Paste playing XI (both teams)",
                placeholder=f"{ta}: Player1, Player2, ...\n{tb}: Player1, Player2, ...",
                height=80, key=f"{sk}_xp"
            )

        fc1,fc2 = st.columns(2)
        with fc1:
            if st.button("🌐 Auto-fetch XI", key=f"{sk}_fxi"):
                with st.spinner("Fetching from ESPNcricinfo..."):
                    try:
                        sys.path.insert(0, os.path.join(ROOT,"scripts"))
                        from fetch_playingxi import fetch_and_store_xi
                        res = fetch_and_store_xi(mid, match["date"], ta, tb)
                        if res["success"]:
                            S["xi"] = res.get("players",{})
                            st.success(f"✅ {res['count']} players fetched")
                            for team,players in res.get("players",{}).items():
                                st.write(f"**{team}:** {', '.join(players)}")
                        else:
                            st.warning("Auto-fetch failed — paste XI above")
                    except Exception as e:
                        st.error(f"{e}")

        with fc2:
            if st.button("✅ Confirm & run player signal",
                         type="primary", key=f"{sk}_conf"):
                # Parse pasted XI
                if xi_paste and len(xi_paste)>10:
                    try:
                        sys.path.insert(0, os.path.join(ROOT,"scripts"))
                        from fetch_playingxi import fetch_and_store_xi
                        res = fetch_and_store_xi(mid, match["date"], ta, tb, xi_text=xi_paste)
                        if res["success"]:
                            S["xi"] = res.get("players",{})
                    except Exception:
                        pass

                S["toss"] = {"winner":toss_winner,"choice":toss_choice}

                # Run player signal
                with st.spinner("Computing player signal..."):
                    try:
                        sys.path.insert(0, os.path.join(ROOT,"player_engine"))
                        from player_signal import get_player_signal
                        sig = get_player_signal(mid, ta, tb, fmt, match["venue_id"], gender)
                        S["signal"] = sig
                        st.success(f"✅ Player signal computed — "
                                   f"{ta} {sig.team_a_signal.overall:.1f}/10 vs "
                                   f"{tb} {sig.team_b_signal.overall:.1f}/10")
                    except Exception as e:
                        S["signal"] = None
                        st.warning(f"Player signal error: {e}")

                S["phase"] = "xi_confirmed"
                st.rerun()

    # ══════════════════════════════════════════════════════════
    # STEP 2 — PRE-MATCH ANALYSIS
    # ══════════════════════════════════════════════════════════
    with st.expander(
        f"📊 Step 2 — Pre-match player analysis  "
        f"{'✅ Done' if p_idx>=2 else ''}",
        expanded=(p_idx==1)
    ):
        toss = S["toss"]
        sig  = S["signal"]

        if not toss:
            st.info("Complete Step 1 first.")
        else:
            if toss.get("winner","—") != "—":
                tw2 = toss["winner"]; tc2 = toss["choice"]
                bat1st = tw2 if tc2=="bat" else (tb if tw2==ta else ta)
                bowl1st= tb if bat1st==ta else ta
                st.info(f"🪙 **{tw2}** won toss · elected to **{tc2}** · "
                        f"**{bat1st}** bats first")

            if sig:
                import pandas as pd
                ta_s = sig.team_a_signal
                tb_s = sig.team_b_signal

                c1,c2,c3,c4 = st.columns(4)
                c1.metric(f"{ta}",    f"{ta_s.overall:.1f}/10")
                c2.metric(f"{tb}",    f"{tb_s.overall:.1f}/10")
                c3.metric("Signal",   f"{sig.signal_factor:.1f}/10",
                          f"{ta} edge" if sig.signal_factor>5.5 else
                          f"{tb} edge" if sig.signal_factor<4.5 else "Even")
                c4.metric("EV adj",   f"{sig.signal_ev_adj:+.1f}%")

                fdf = pd.DataFrame([
                    {"Factor":"Batting",     ta:ta_s.batting_score,  tb:tb_s.batting_score},
                    {"Factor":"Bowling",     ta:ta_s.bowling_score,  tb:tb_s.bowling_score},
                    {"Factor":"Form",        ta:ta_s.form_score,     tb:tb_s.form_score},
                    {"Factor":"Venue",       ta:ta_s.venue_score,    tb:tb_s.venue_score},
                    {"Factor":"Matchups",    ta:ta_s.matchup_score,  tb:tb_s.matchup_score},
                    {"Factor":"Availability",ta:ta_s.avail_score,    tb:tb_s.avail_score},
                ])
                st.dataframe(fdf, width="stretch", hide_index=True,
                             column_config={
                                 ta:st.column_config.ProgressColumn(ta,min_value=0,max_value=10,format="%.1f"),
                                 tb:st.column_config.ProgressColumn(tb,min_value=0,max_value=10,format="%.1f"),
                             })

                if sig.key_insights:
                    for ins in sig.key_insights[:6]:
                        if any(w in ins for w in ["dominates","OUT","⚠"]):
                            st.warning(f"⚠ {ins}")
                        elif any(w in ins for w in ["exceptional","outstanding","✅"]):
                            st.success(f"✅ {ins}")
                        else:
                            st.info(f"ℹ {ins}")
            else:
                st.info("Player signal not available — check player_engine.db")

            if p_idx == 1:
                if st.button("🔴 Match started",
                             type="primary", key=f"{sk}_start"):
                    S["phase"] = "match_live"
                    S["score"] = {}
                    st.rerun()

    # ══════════════════════════════════════════════════════════
    # STEP 3 — LIVE TRACKER
    # ══════════════════════════════════════════════════════════
    with st.expander(
        f"🔴 Step 3 — Live in-play tracker",
        expanded=(p_idx==2)
    ):
        if p_idx < 2:
            st.info("Available once match starts (Step 2 → Match started).")
        else:
            sys.path.insert(0, os.path.join(ROOT,"inplay_engine"))
            try:
                from wp_lookup import MatchState, lookup
                from verdict import decide
                IP_OK = True
            except Exception as e:
                IP_OK = False
                st.error(f"In-play engine: {e}")

            if IP_OK:
                total_balls = {"T20":120,"T20I":120,"100b":100,"ODI":300}.get(fmt,120)
                fmt_ip = {"T20I":"T20I","T20":"T20","ODI":"ODI","100b":"100b"}.get(fmt,"T20")
                score_d = S["score"]

                # Refresh button
                rc1,rc2 = st.columns([1,4])
                with rc1:
                    do_refresh = st.button("🔄 Refresh score",
                                           type="primary", key=f"{sk}_ref")
                with rc2:
                    ref_status = st.empty()

                if do_refresh:
                    with ref_status, st.spinner("Fetching live score..."):
                        try:
                            sys.path.insert(0, os.path.join(ROOT, "scripts"))
                            from score_fetcher import fetch_live_score
                            api_key = st.secrets["ANTHROPIC_API_KEY"] if "ANTHROPIC_API_KEY" in st.secrets else os.environ.get("ANTHROPIC_API_KEY","")
                            from score_fetcher import fetch_live_score
                            res = fetch_live_score(ta, tb, match["date"], fmt, api_key=api_key)
                            st.session_state[f"fetch_log_{mid}"] = res
                            if res.success:
                                fetched = dict(score_d)
                                fetched["score"]      = res.score
                                fetched["wickets"]    = res.wickets
                                fetched["balls_done"] = res.balls_done
                                if res.innings: fetched["innings"] = res.innings
                                if res.target:  fetched["target"]  = res.target
                                S["score"] = fetched
                                score_d    = fetched
                                ov = res.overs_str or f"{res.balls_done//6}.{res.balls_done%6}"
                                ref_status.success(
                                    f"✅ {res.score}/{res.wickets} ({ov} ov) "
                                    f"via {res.source}"
                                    + (f" · Target {res.target}" if res.target else "")
                                )
                                if res.result_str:
                                    ref_status.info(f"🏆 {res.result_str}")
                            elif res.match_status == "NotStarted":
                                ref_status.info(
                                    f"⏳ Match has not started yet."
                                    + (f" Toss: **{res.toss_winner}** elected to **{res.toss_choice}**"
                                       if res.toss_winner else "")
                                    + f"\n\n{res.error or ''}"
                                )
                            else:
                                ref_status.warning(
                                    f"⚠️ Could not fetch automatically. Add ANTHROPIC_API_KEY to Streamlit secrets, or enter manually below.\n\nDebug: {res.raw_text[:200] if res.raw_text else res.error}"
                                )
                        except Exception as e:
                            ref_status.warning(f"Fetch error: {e}")
                    # Show fetch log
                    log_key = f"fetch_log_{mid}"
                    if log_key in st.session_state:
                        _r = st.session_state[log_key]
                        with st.expander("🔍 Fetch log", expanded=not _r.success):
                            st.text(f"Source tried:  {_r.source or 'none'}")
                            st.text(f"Success:       {_r.success}")
                            if _r.error:
                                st.text(f"Error:         {_r.error}")
                            if _r.raw_text:
                                st.text_area("Raw detail", _r.raw_text[:600], height=100, key=f"rlog_{mid}")
                    innings = st.radio("Innings",[1,2],horizontal=True,
                                       index=max(0,score_d.get("innings",1)-1),
                                       format_func=lambda x:"1st" if x==1 else "2nd",
                                       key=f"{sk}_inn")
                    # Auto-set batting from toss
                    bat_opts = [ta, tb]
                    bat_idx  = 0
                    if S["toss"] and innings==1:
                        tw3 = S["toss"].get("winner","")
                        tc3 = S["toss"].get("choice","")
                        if tw3 and tc3:
                            auto_bat = tw3 if tc3=="bat" else (tb if tw3==ta else ta)
                            bat_idx  = 0 if auto_bat==ta else 1
                    batting_team = st.selectbox("Batting",bat_opts,
                                                index=bat_idx,key=f"{sk}_bat")
                    bowling_team = tb if batting_team==ta else ta
                    st.success(f"🎳 {bowling_team}")

                with c2:
                    score      = st.number_input("Runs",0,700,
                                                 score_d.get("score",0),1,key=f"{sk}_sc")
                    wickets    = st.number_input("Wickets",0,9,
                                                 score_d.get("wickets",0),1,key=f"{sk}_wk")
                    balls_done = st.number_input(f"Balls (of {total_balls})",
                                                 0,total_balls,
                                                 score_d.get("balls_done",0),1,key=f"{sk}_bd")

                with c3:
                    target = None
                    if innings==2:
                        target = st.number_input("Target",50,700,
                                                 score_d.get("target",150),1,key=f"{sk}_tgt")
                        bl = total_balls-int(balls_done)
                        if bl>0 and target>score:
                            st.metric("Req RR",f"{(target-score)/(bl/6):.2f}")
                    bfo = st.number_input(f"Betfair odds ({batting_team})",
                                          1.01,50.0,2.00,0.01,
                                          format="%.2f",key=f"{sk}_bfo")
                    st.caption(f"Implied: {1/bfo:.1%}")

                # Pre-match position
                st.markdown("**Your pre-match position**")
                pc1,pc2,pc3 = st.columns(3)
                with pc1:
                    pre_team = st.selectbox("Bet on",[ta,tb,"— None —"],
                                            key=f"{sk}_pt")
                with pc2:
                    pre_stake = st.number_input("Stake €",0.0,50000.0,0.0,1.0,
                                                key=f"{sk}_ps",
                                                disabled=pre_team=="— None —")
                with pc3:
                    pre_odds = st.number_input("Odds",1.01,20.0,2.00,0.01,
                                               format="%.2f",key=f"{sk}_po",
                                               disabled=pre_team=="— None —")

                if st.button("▶ Get verdict", type="primary", key=f"{sk}_verd"):
                    state = MatchState(
                        format=fmt_ip, innings=innings,
                        batting_team=batting_team, bowling_team=bowling_team,
                        balls_completed=int(balls_done), score=int(score),
                        wickets_lost=int(wickets),
                        target=int(target) if target else None,
                        betfair_odds=float(bfo),
                        pre_match_stake=float(pre_stake) if pre_team!="— None —" else 0.0,
                        pre_match_odds=float(pre_odds),
                        pre_match_team=pre_team if pre_team!="— None —" else batting_team,
                        bankroll=bankroll, phase=ph, gender=gender,
                    )
                    wp = lookup(state)
                    d  = decide(state)

                    # Show player signal influence
                    if S["signal"]:
                        sig3 = S["signal"]
                        st.info(
                            f"Player signal: **{sig3.signal_factor:.1f}/10** — "
                            f"EV adj **{sig3.signal_ev_adj:+.1f}%** for {ta}"
                        )

                    if d.verdict=="ADD":
                        msg = (f"### ✅ ADD — €{d.add_stake:.2f} on {batting_team} @ {d.add_odds}"
                               + f"\n\nEV {d.add_ev_pct:+.1f}% · Edge {wp.edge:+.1%} · "
                               + f"Model {wp.blended_wp:.1%} vs Market {wp.implied_wp:.1%}"
                               + f"\n\n{d.reason}"
                               + f"\n\nWins → **+€{d.pnl_if_batting_wins:.2f}** · "
                               + f"Loses → **-€{abs(d.pnl_if_batting_loses):.2f}**")
                        st.success(msg)
                    elif d.verdict=="HEDGE":
                        msg = (f"### 🔄 HEDGE — Lay €{d.lay_stake:.2f} → "
                               + f"lock €{d.guaranteed_profit:.2f} guaranteed"
                               + f"\n\n{d.reason}")
                        st.info(msg)
                    elif d.verdict=="EXIT":
                        st.error(f"### 🛑 EXIT — Cut position\n\n{d.reason}")
                    else:
                        msg = (f"### ⏸ HOLD — No action"
                               + f"\n\n{d.reason}"
                               + f"\n\nWins → **+€{d.pnl_if_batting_wins:.2f}** · "
                               + f"Loses → **-€{abs(d.pnl_if_batting_loses):.2f}**")
                        st.warning(msg)

                    with st.expander("Win probability detail"):
                        import pandas as pd
                        st.dataframe(pd.DataFrame([
                            {"Source":"Historical","WP":f"{wp.historical_wp:.1%}",
                             "n":wp.sample_size,"Note":wp.confidence},
                            {"Source":f"ELO","WP":f"{wp.elo_wp:.1%}",
                             "n":"—","Note":f"{batting_team} {wp.elo_batting:.0f} vs {bowling_team} {wp.elo_bowling:.0f}"},
                            {"Source":"Blended","WP":f"{wp.blended_wp:.1%}","n":"—","Note":"Model"},
                            {"Source":f"Market @ {bfo}","WP":f"{wp.implied_wp:.1%}","n":"—","Note":"Betfair"},
                        ]), width="stretch", hide_index=True)

                st.divider()
                if st.button("✅ Match finished → Log result",
                             key=f"{sk}_done"):
                    S["phase"] = "completed"
                    st.success("Go to **✏️ Log result** to record the outcome and update ELO.")
                    st.rerun()


# PAGE: IN-PLAY ENGINE
# ══════════════════════════════════════════════════════════════════════════
elif page == "👁 In-play engine":
    st.title("👁 In-play engine")
    st.markdown(
        "Live match state → **ADD / HOLD / HEDGE / EXIT** verdict. "
        "Blends Cricsheet 2024+ historical frequencies with ELO team ratings."
    )
    st.divider()

    sys.path.insert(0, os.path.join(ROOT, "inplay_engine"))
    try:
        from wp_lookup import MatchState, lookup
        from verdict import decide
        ENGINE_LOADED = True
    except Exception as e:
        st.error(f"In-play engine not loaded: {e}")
        ENGINE_LOADED = False

    if not ENGINE_LOADED:
        st.stop()

    import datetime as dt
    import requests as _req

    conn  = get_db()
    today = dt.date.today().isoformat()
    yest  = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    nxt7  = (dt.date.today() + dt.timedelta(days=7)).isoformat()

    # ── STEP 1: Match selector — yesterday to next 7 days ──────
    st.subheader("Step 1 — Select match")

    window_matches = conn.execute("""
        SELECT match_id, date, step, label, team_a, team_b,
               format, venue_id, gender, category, city
        FROM matches
        WHERE date BETWEEN ? AND ?
        ORDER BY date, step
    """, (yest, nxt7)).fetchall()

    mode = st.radio("Match source",
        ["📅 This week (yesterday + 7 days)", "✏️ Enter teams manually"],
        horizontal=True, key="ip_mode", label_visibility="collapsed"
    )

    sm_ip = None

    if mode == "📅 This week (yesterday + 7 days)":
        if window_matches:
            # Group by date for display
            from itertools import groupby
            date_groups = {}
            for m in window_matches:
                d = m["date"]
                lbl = "Yesterday" if d == yest else                       "Today"     if d == today else                       dt.date.fromisoformat(d).strftime("%a %d %b")
                date_groups.setdefault(lbl, []).append(m)

            opts = {}
            for day_lbl, day_matches in date_groups.items():
                for m in day_matches:
                    g = dict(m).get("gender","male")
                    gender_icon = "👩" if g == "female" or "Women" in m["team_a"] else "👨"
                    key = (f"{day_lbl} · {gender_icon} "
                           f"{m['team_a']} vs {m['team_b']} · "
                           f"{m['label']} [{m['format']}]")
                    opts[key] = dict(m)

            sel = st.selectbox(
                f"{len(window_matches)} matches — yesterday through next 7 days",
                list(opts.keys()), key="ip_sel"
            )
            sm_ip = opts[sel]

            # Match info card
            d_label = "Yesterday" if sm_ip["date"]==yest else                       "Today ↔ LIVE" if sm_ip["date"]==today else                       dt.date.fromisoformat(sm_ip["date"]).strftime("%a %d %b")
            st.markdown(
                f"<div style='padding:10px 14px;background:var(--card);"
                f"border:1px solid var(--bdr);border-radius:8px;font-size:13px'>"
                f"<strong>{sm_ip['team_a']}</strong> vs <strong>{sm_ip['team_b']}</strong>"
                f" · {sm_ip['label']} · {sm_ip['format']}"
                f" · {sm_ip.get('city','')} · Step {sm_ip['step']}"
                f" · <span style='color:#00C8A0'>{d_label}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.info("No matches in DB for yesterday through next 7 days.")

    else:  # Manual
        c1,c2,c3 = st.columns(3)
        with c1: ta  = st.text_input("Batting team", "India", key="ip_mta")
        with c2: tb  = st.text_input("Bowling team", "England", key="ip_mtb")
        with c3: mfmt = st.selectbox("Format", ["T20","T20I","ODI","100b"], key="ip_mfmt")
        sm_ip = {"match_id":"manual","date":today,"step":0,"label":"Manual",
                 "team_a":ta,"team_b":tb,"format":mfmt,
                 "venue_id":"","gender":"male","category":"International","city":""}

    st.divider()

    if not sm_ip:
        st.stop()

    fmt_ip      = {"T20I":"T20I","T20":"T20","ODI":"ODI","100b":"100b","Test":"Test"}.get(sm_ip["format"],"T20")
    total_balls = {"T20":120,"T20I":120,"100b":100,"ODI":300}.get(fmt_ip,120)

    # ── STEP 2: Live state — with auto-fetch button ─────────────
    st.subheader("Step 2 — Live match state")

    # Auto-fetch section
    fetch_col, status_col = st.columns([1, 3])
    with fetch_col:
        do_fetch = st.button("🔄 Fetch live score", key="ip_fetch", type="secondary")
    with status_col:
        fetch_status = st.empty()

    # Session state for fetched values
    if "ip_fetched" not in st.session_state:
        st.session_state.ip_fetched = {}

    fetched = st.session_state.ip_fetched

    if do_fetch:
        with fetch_status:
            with st.spinner(f"Fetching score for {sm_ip['team_a']} vs {sm_ip['team_b']}..."):
                try:
                    sys.path.insert(0, os.path.join(ROOT, "scripts"))
                    from score_fetcher import fetch_live_score
                    _api_key = st.secrets["ANTHROPIC_API_KEY"] if "ANTHROPIC_API_KEY" in st.secrets else os.environ.get("ANTHROPIC_API_KEY","")
                    res = fetch_live_score(
                        sm_ip["team_a"], sm_ip["team_b"],
                        sm_ip["date"], fmt_ip,
                        api_key=_api_key
                    )
                    if res.success:
                        fetched = {
                            "score":      res.score,
                            "wickets":    res.wickets,
                            "balls_done": res.balls_done,
                        }
                        if res.innings: fetched["innings"] = res.innings
                        if res.target:  fetched["target"]  = res.target
                        if res.batting_team: fetched["batting_team"] = res.batting_team
                        st.session_state.ip_fetched = fetched
                        fetched_state = fetched
                        ov = res.overs_str or f"{res.balls_done//6}.{res.balls_done%6}"
                        fetch_status.success(
                            f"✅ {res.score}/{res.wickets} ({ov} ov) "
                            f"via **{res.source}**"
                            + (f" · Target {res.target}" if res.target else "")
                            + (f" · {res.match_status}" if res.match_status else "")
                        )
                        if res.result_str:
                            fetch_status.info(f"🏆 {res.result_str}")
                    elif res.match_status == "NotStarted":
                        fetch_status.info(
                            f"⏳ Match has not started yet."
                            + (f" Toss: **{res.toss_winner}** elected to **{res.toss_choice}**" if res.toss_winner else "")
                            + f"\n\n{res.error or ''}"
                        )
                    else:
                        err_detail = res.raw_text or res.error or "Unknown error"
                        fetch_status.warning(
                            f"⚠️ Auto-fetch failed. Enter score manually below.\n\n"
                            f"**Debug:** {err_detail[:300]}"
                        )
                    st.session_state["ip_fetch_log"] = res
                except Exception as e:
                    res = type("R",(),{"success":False,"source":"exception","error":str(e),"raw_text":""})()
                    fetch_status.warning(f"Fetch error: {e}")
                    st.session_state["ip_fetch_log"] = res

    # ── Fetch log expander ─────────────────────────────────
    if "ip_fetch_log" in st.session_state:
        _lr = st.session_state["ip_fetch_log"]
        with st.expander("🔍 Fetch log — click to see what was tried", expanded=not _lr.success):
            c1,c2 = st.columns(2)
            c1.metric("Source", getattr(_lr,"source","none") or "none")
            c2.metric("Success", "✅ Yes" if getattr(_lr,"success",False) else "❌ No")
            if getattr(_lr,"error",""):
                st.error(f"Error: {_lr.error}")
            if getattr(_lr,"raw_text",""):
                st.text_area("Raw detail (all sources tried)", _lr.raw_text[:600],
                             height=120, key="ip_rlog", disabled=True)
            if not getattr(_lr,"success",False):
                st.info(
                    "💡 To enable auto-fetch: go to **Manage app → Settings → Secrets** "
                    "and add:\n```\nANTHROPIC_API_KEY = \"sk-ant-...\"\n```"
                )

    st.caption("Values pre-filled from fetch if available — adjust as needed")

    c1,c2,c3 = st.columns(3)
    with c1:
        innings = st.radio("Innings", [1,2], horizontal=True,
                           index=(fetched.get("innings",1)-1),
                           format_func=lambda x:"1st innings" if x==1 else "2nd innings",
                           key="ip_inn")
        batting_opts = [sm_ip["team_a"], sm_ip["team_b"]]
        bat_idx = 0
        if "batting_team" in fetched:
            bat_idx = 0 if fetched["batting_team"]==sm_ip["team_a"] else 1
        batting_team = st.selectbox("Who is batting", batting_opts, index=bat_idx, key="ip_bat")
        bowling_team = sm_ip["team_b"] if batting_team==sm_ip["team_a"] else sm_ip["team_a"]
        st.success(f"🎳 Bowling: **{bowling_team}**")

    with c2:
        score      = st.number_input("Runs scored",
                                     0, 600, fetched.get("score", 51), 1, key="ip_score")
        wickets    = st.number_input("Wickets lost",
                                     0, 9, fetched.get("wickets", 3), 1, key="ip_wkts")
        balls_done = st.number_input(f"Balls completed (of {total_balls})",
                                     0, total_balls, fetched.get("balls_done", 44), 1, key="ip_balls")

    with c3:
        target = None
        if innings == 2:
            target = st.number_input("Target (runs to win)", 50, 700,
                                     fetched.get("target", 144), 1, key="ip_target")
            bl = total_balls - int(balls_done)
            if bl > 0 and target > score:
                rr = (target - score) / (bl / 6)
                st.metric("Required RR", f"{rr:.2f}")
        betfair_odds = st.number_input(
            f"Betfair odds on {batting_team}",
            1.01, 50.0, 2.95, 0.01, format="%.2f", key="ip_odds",
            help="Live Betfair Exchange price for batting team to win"
        )
        st.caption(f"Implied: {1/betfair_odds:.1%}")

    st.divider()

    # ── STEP 3: Pre-match position ──────────────────────────────
    st.subheader("Step 3 — Your pre-match position")
    c1,c2,c3 = st.columns(3)
    with c1:
        pre_team = st.selectbox("Bet was on",
            [sm_ip["team_a"], sm_ip["team_b"], "— No pre-match bet —"], key="ip_pteam")
    with c2:
        pre_stake = st.number_input("Stake placed (€)", 0.0, 50000.0,
            199.0 if pre_team!="— No pre-match bet —" else 0.0, 1.0, key="ip_pstake",
            disabled=(pre_team=="— No pre-match bet —"))
    with c3:
        pre_odds = st.number_input("Odds taken", 1.01, 20.0, 1.95, 0.01,
            format="%.2f", key="ip_podds",
            disabled=(pre_team=="— No pre-match bet —"))

    gender_ip = "female" if any(w in (sm_ip.get("gender","male") or "male").lower()
                                for w in ["female","women","w"]) else "male"

    st.divider()
    if st.button("▶  Get verdict", type="primary", key="ip_run"):
        state = MatchState(
            format=fmt_ip, innings=innings,
            batting_team=batting_team, bowling_team=bowling_team,
            balls_completed=int(balls_done), score=int(score),
            wickets_lost=int(wickets),
            target=int(target) if target else None,
            betfair_odds=float(betfair_odds),
            pre_match_stake=float(pre_stake) if pre_team!="— No pre-match bet —" else 0.0,
            pre_match_odds=float(pre_odds),
            pre_match_team=pre_team if pre_team!="— No pre-match bet —" else batting_team,
            bankroll=bankroll, phase=ph, gender=gender_ip,
        )
        wp = lookup(state)
        d  = decide(state)

        # WP breakdown
        st.subheader("Win probability")
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Balls left",   total_balls - int(balls_done))
        c2.metric("Wickets left", 10 - int(wickets))
        if target:
            c3.metric("Runs needed", int(target)-int(score))
            c4.metric("Req RR", f"{wp.required_rr or 0:.1f}")
            p = wp.pressure_index or 1.0
            c5.metric("Pressure", f"{p:.1f}×",
                      "🔴 High" if p>1.4 else "🟡 Med" if p>1.1 else "🟢 Low",
                      delta_color="inverse" if p>1.4 else "normal")

        import pandas as pd
        wpdf = pd.DataFrame([
            {"Source":"Historical (Cricsheet 2024+)","Win %":f"{wp.historical_wp:.1%}",
             "n":wp.sample_size,"Quality":wp.confidence,
             "Note":"WASP fallback" if wp.fallback_used else "Lookup table ✓"},
            {"Source":f"ELO ({batting_team} {wp.elo_batting:.0f} vs {bowling_team} {wp.elo_bowling:.0f})",
             "Win %":f"{wp.elo_wp:.1%}","n":"—","Quality":"high","Note":"2024+ ELO ratings"},
            {"Source":"Blended (70% hist + 30% ELO)","Win %":f"{wp.blended_wp:.1%}",
             "n":"—","Quality":"—","Note":"← Model output"},
            {"Source":f"Betfair @ {betfair_odds}","Win %":f"{wp.implied_wp:.1%}",
             "n":"—","Quality":"—","Note":"Market implied"},
        ])
        st.dataframe(wpdf, width="stretch", hide_index=True)

        ec = "#1DB87A" if wp.edge>0 else "#E84040"
        st.markdown(
            f"<div style='padding:10px 14px;background:var(--card);"
            f"border:1px solid var(--bdr);border-radius:8px'>"
            f"<strong>Edge:</strong> <span style='color:{ec};font-size:16px;font-weight:600'>"
            f"{wp.edge:+.1%}</span>&nbsp;·&nbsp;"
            f"Model {wp.blended_wp:.1%} vs Market {wp.implied_wp:.1%}"
            f"</div>", unsafe_allow_html=True)

        st.divider()
        st.subheader("Verdict")
        if d.verdict=="ADD":
            st.success(f"""### ✅ ADD — Place **€{d.add_stake:.2f}** on {batting_team} @ {d.add_odds}
**EV: {d.add_ev_pct:+.1f}%** · Edge {wp.edge:+.1%} · n={wp.sample_size}  
{d.reason}  
**If {batting_team} wins → +€{d.pnl_if_batting_wins:.2f}** · **loses → -€{abs(d.pnl_if_batting_loses):.2f}**""")
        elif d.verdict=="HEDGE":
            st.info(f"""### 🔄 HEDGE — Green up on Betfair
Lay **€{d.lay_stake:.2f}** @ {betfair_odds} → **€{d.guaranteed_profit:.2f} guaranteed** regardless of result.  
Use Betfair's **Green All** button. {d.reason}""")
        elif d.verdict=="EXIT":
            st.error(f"""### 🛑 EXIT — Cut position now
{d.reason}  
Exposure **€{pre_stake:.2f}** — limit the loss, don't ride to the end.""")
        else:
            st.warning(f"""### ⏸ HOLD — No action
{d.reason}  
**€{pre_stake:.2f} @ {pre_odds}** pre-match bet is still valid. Sit tight.  
Wins → **+€{d.pnl_if_batting_wins:.2f}** · Loses → **-€{abs(d.pnl_if_batting_loses):.2f}**""")

        # What-if table
        st.divider()
        st.subheader("What-if — verdict at different odds")
        scen_rows=[]
        for to in [1.10,1.20,1.30,1.50,1.75,2.00,2.20,2.50,3.00,4.00,6.00]:
            st2=MatchState(format=fmt_ip,innings=innings,batting_team=batting_team,
                           bowling_team=bowling_team,balls_completed=int(balls_done),
                           score=int(score),wickets_lost=int(wickets),
                           target=int(target) if target else None,betfair_odds=to,
                           pre_match_stake=float(pre_stake) if pre_team!="— No pre-match bet —" else 0,
                           pre_match_odds=float(pre_odds),
                           pre_match_team=pre_team if pre_team!="— No pre-match bet —" else batting_team,
                           bankroll=bankroll,phase=ph,gender=gender_ip)
            d2=decide(st2)
            scen_rows.append({"Odds":to,"Market implies":f"{1/to:.1%}",
                              "Model WP":f"{wp.blended_wp:.1%}",
                              "Edge":f"{(wp.blended_wp-1/to)*100:+.1f}%",
                              "Verdict":d2.verdict,
                              "Action":(f"Add €{d2.add_stake:.0f}" if d2.verdict=="ADD"
                                        else f"Lay €{d2.lay_stake:.0f}" if d2.verdict=="HEDGE"
                                        else d2.verdict)})
        st.dataframe(pd.DataFrame(scen_rows), width="stretch", hide_index=True)


# PAGE: PLAYER ANALYTICS
# ══════════════════════════════════════════════════════════════════════════
elif page == "👤 Player analytics":
    st.title("👤 Player analytics")
    st.markdown(
        "Head-to-head matchups, venue records and form scores for key players. "
        "Feeds directly into the confidence score as the **players factor (10% weight)**."
    )
    st.divider()

    PLAYER_DB = os.path.join(ROOT, "db", "player_engine.db")

    if not os.path.exists(PLAYER_DB):
        st.error("player_engine.db not found. Upload it to the db/ folder on GitHub.")
        st.stop()

    pconn = sqlite3.connect(PLAYER_DB)
    pconn.row_factory = sqlite3.Row

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏏 Match signal", "⚔️ Player matchups",
        "📍 Venue records", "📋 Playing XI"
    ])

    # ── TAB 1: MATCH SIGNAL ──────────────────────────────────
    with tab1:
        st.subheader("Player signal for any match")
        st.caption("Computes a 0–10 confidence factor for team_a based on batting, bowling, form, venue and matchup data.")

        conn_ce = get_db()
        matches_ps = conn_ce.execute(
            "SELECT match_id, date, step, label, team_a, team_b, format, venue_id, category FROM matches ORDER BY step"
        ).fetchall()

        col1, col2 = st.columns(2)
        with col1:
            fmt_ps = st.selectbox("Format", ["All","ODI","T20I","T20","Test"], key="ps_fmt")
        with col2:
            search_ps = st.text_input("Search team", "", key="ps_search")

        filtered_ps = [m for m in matches_ps
                       if (fmt_ps == "All" or m["format"] == fmt_ps)
                       and (not search_ps or search_ps.lower() in (m["team_a"]+m["team_b"]).lower())]

        opts_ps = {
            f"Step {m['step']:>3} | {m['date']} | {m['team_a']} vs {m['team_b']} [{m['format']}]": dict(m)
            for m in filtered_ps
        }

        if opts_ps:
            sel_ps  = st.selectbox(f"Select match ({len(opts_ps)} shown)", list(opts_ps.keys()), key="ps_sel")
            sm_ps   = opts_ps[sel_ps]

            if st.button("▶ Run player signal", type="primary", key="ps_run"):
                sys.path.insert(0, os.path.join(ROOT, "player_engine"))
                try:
                    from player_signal import get_player_signal
                    with st.spinner("Computing player signal..."):
                        sig = get_player_signal(
                            match_id = sm_ps["match_id"],
                            team_a   = sm_ps["team_a"],
                            team_b   = sm_ps["team_b"],
                            fmt      = sm_ps["format"],
                            venue_id = sm_ps["venue_id"],
                        )

                    ta = sig.team_a_signal
                    tb = sig.team_b_signal

                    # Top metrics
                    c1,c2,c3,c4,c5 = st.columns(5)
                    c1.metric("Signal factor", f"{sig.signal_factor:.1f}/10",
                              "India advantage" if sig.signal_factor > 5.5
                              else "England advantage" if sig.signal_factor < 4.5 else "Even")
                    c2.metric("EV adjustment", f"{sig.signal_ev_adj:+.1f}%",
                              f"for {sm_ps['team_a']}")
                    c3.metric(f"{sm_ps['team_a']} overall", f"{ta.overall:.1f}/10")
                    c4.metric(f"{sm_ps['team_b']} overall", f"{tb.overall:.1f}/10")
                    c5.metric("Data quality", sig.data_quality.upper())

                    st.divider()

                    # Factor breakdown table
                    import pandas as pd
                    factor_data = [
                        {"Factor":"Batting",     sm_ps["team_a"]: ta.batting_score,  sm_ps["team_b"]: tb.batting_score},
                        {"Factor":"Bowling",     sm_ps["team_a"]: ta.bowling_score,  sm_ps["team_b"]: tb.bowling_score},
                        {"Factor":"Form",        sm_ps["team_a"]: ta.form_score,     sm_ps["team_b"]: tb.form_score},
                        {"Factor":"Venue record",sm_ps["team_a"]: ta.venue_score,    sm_ps["team_b"]: tb.venue_score},
                        {"Factor":"Matchups",    sm_ps["team_a"]: ta.matchup_score,  sm_ps["team_b"]: tb.matchup_score},
                        {"Factor":"Availability",sm_ps["team_a"]: ta.avail_score,    sm_ps["team_b"]: tb.avail_score},
                        {"Factor":"OVERALL",     sm_ps["team_a"]: ta.overall,        sm_ps["team_b"]: tb.overall},
                    ]
                    fdf = pd.DataFrame(factor_data)
                    st.dataframe(fdf, width="stretch", hide_index=True,
                                 column_config={
                                     sm_ps["team_a"]: st.column_config.ProgressColumn(
                                         sm_ps["team_a"], min_value=0, max_value=10, format="%.1f"),
                                     sm_ps["team_b"]: st.column_config.ProgressColumn(
                                         sm_ps["team_b"], min_value=0, max_value=10, format="%.1f"),
                                 })

                    # Key insights
                    if sig.key_insights:
                        st.divider()
                        st.subheader("Key matchup insights")
                        for ins in sig.key_insights:
                            if "dominates" in ins or "OUT" in ins:
                                st.warning(f"⚠ {ins}")
                            elif "exceptional" in ins or "outstanding" in ins:
                                st.success(f"✅ {ins}")
                            else:
                                st.info(f"ℹ {ins}")

                    # Key batters
                    col1, col2 = st.columns(2)
                    with col1:
                        if ta.key_batters:
                            st.subheader(f"{sm_ps['team_a']} batting")
                            for b in ta.key_batters:
                                arrow = {"up":"↑","flat":"→","down":"↓"}.get(b["trend"],"→")
                                avg = f"  L5 avg: {b['l5avg']}" if b.get("l5avg") else ""
                                st.metric(b["name"], f"{b['form']}/10 {arrow}", avg)

                    with col2:
                        if ta.key_bowlers:
                            st.subheader(f"{sm_ps['team_a']} bowling")
                            for b in ta.key_bowlers:
                                rank = f"ICC #{b['rank']}" if b.get("rank") else b.get("style","")
                                st.metric(b["name"], f"{b['form']}/10", rank)

                    # Injuries
                    all_inj = ta.injuries + tb.injuries
                    real_inj = [i for i in all_inj if "OUT" in i or "not playing" in i.lower()]
                    if real_inj:
                        st.divider()
                        st.subheader("Availability alerts")
                        for inj in real_inj:
                            st.error(inj)

                except Exception as e:
                    st.error(f"Player signal error: {e}")
                    st.caption("Make sure player_engine.db is in the db/ folder")

    # ── TAB 2: PLAYER MATCHUPS ────────────────────────────────
    with tab2:
        st.subheader("Batter vs bowler head-to-head")
        st.caption("Who has the edge when specific players meet? Minimum 12 balls to show.")

        pvp_rows = pconn.execute("""
            SELECT pvp.*,
                   bp.name  AS batter_name,  bp.team AS batter_team,
                   bwp.name AS bowler_name, bwp.team AS bowler_team
            FROM player_vs_player pvp
            JOIN players bp  ON pvp.batter_id  = bp.player_id
            JOIN players bwp ON pvp.bowler_id  = bwp.player_id
            WHERE pvp.balls >= 12
            ORDER BY pvp.balls DESC
        """).fetchall()

        if pvp_rows:
            import pandas as pd
            pvp_df = pd.DataFrame([{
                "Batter":      r["batter_name"],
                "Batter team": r["batter_team"],
                "Bowler":      r["bowler_name"],
                "Bowler team": r["bowler_team"],
                "Format":      r["format"],
                "Balls":       r["balls"],
                "Runs":        r["runs"],
                "Dismissals":  r["dismissals"],
                "SR":          round(r["strike_rate"] or 0, 1),
                "Dot %":       round(r["dot_pct"] or 0, 1),
                "Last 5":      r["last_5_results"] or "",
                "Edge":        "🎳 Bowler" if r["bowler_dominates"]
                               else "🏏 Batter" if r["batter_dominates"]
                               else "Even",
            } for r in pvp_rows])

            # Filter
            col1, col2 = st.columns(2)
            with col1:
                edge_f = st.selectbox("Edge filter",
                    ["All","🎳 Bowler dominates","🏏 Batter dominates","Even"],
                    key="pvp_edge")
            with col2:
                team_f = st.text_input("Filter by team", "", key="pvp_team")

            if edge_f != "All":
                pvp_df = pvp_df[pvp_df["Edge"] == edge_f.split(" ",1)[1] if " " in edge_f else edge_f]
            if team_f:
                pvp_df = pvp_df[
                    pvp_df["Batter team"].str.contains(team_f, case=False) |
                    pvp_df["Bowler team"].str.contains(team_f, case=False)
                ]

            st.dataframe(pvp_df, width="stretch", hide_index=True)
            st.caption(f"{len(pvp_df)} matchup records")
        else:
            st.info("No matchup data yet. Add more player data via seed_players.py")

    # ── TAB 3: VENUE RECORDS ─────────────────────────────────
    with tab3:
        st.subheader("Player venue records")
        st.caption("Career batting/bowling averages at specific grounds.")

        col1, col2 = st.columns(2)
        with col1:
            player_search = st.text_input("Search player name", "Kohli", key="pvs_player")
        with col2:
            fmt_pvs = st.selectbox("Format  ", ["ODI","T20I","T20","Test"], key="pvs_fmt")

        pvs_rows = pconn.execute("""
            SELECT pvs.*, p.name, p.team, p.role
            FROM player_venue_stats pvs
            JOIN players p ON pvs.player_id = p.player_id
            WHERE p.name LIKE ? AND pvs.format=?
            ORDER BY pvs.avg_score DESC NULLS LAST
        """, (f"%{player_search}%", fmt_pvs)).fetchall()

        if pvs_rows:
            import pandas as pd
            pvs_df = pd.DataFrame([{
                "Player":  r["name"],
                "Team":    r["team"],
                "Venue":   r["venue_id"].replace("-"," ").title(),
                "Innings": r["innings"],
                "Avg":     round(r["avg_score"] or 0, 1),
                "SR":      round(r["avg_sr"] or 0, 1),
                "High":    r["highest_score"] or "-",
                "50s":     r["fifties"],
                "100s":    r["hundreds"],
                "L3 avg":  round(r["avg_last_3"] or 0, 1),
                "Wkts":    r["bowl_wickets"] or "-",
                "Eco":     round(r["bowl_economy"] or 0, 2) if r["bowl_economy"] else "-",
            } for r in pvs_rows])

            st.dataframe(pvs_df, width="stretch", hide_index=True,
                         column_config={
                             "Avg": st.column_config.NumberColumn("Avg", format="%.1f"),
                             "SR":  st.column_config.NumberColumn("SR",  format="%.1f"),
                         })

            # Highlight best venue
            if len(pvs_df) > 1:
                best = pvs_df.loc[pvs_df["Avg"].idxmax()]
                st.success(f"Best venue: **{best['Venue']}** — avg {best['Avg']:.0f} in {best['Innings']} innings")
        else:
            st.info(f"No venue data found for '{player_search}' in {fmt_pvs}. Try 'Kohli', 'Root' or 'Bumrah'.")

    # ── TAB 4: PLAYING XI ────────────────────────────────────
    with tab4:
        st.subheader("Playing XI — auto-fetch after toss")
        st.caption("Press the button after toss is announced. Takes ~5 seconds.")

        conn_ce2 = get_db()
        matches_xi = conn_ce2.execute(
            "SELECT match_id, date, step, label, team_a, team_b, format FROM matches ORDER BY date, step LIMIT 30"
        ).fetchall()

        xi_opts = {
            f"Step {m['step']} | {m['date']} | {m['team_a']} vs {m['team_b']} [{m['format']}]": dict(m)
            for m in matches_xi
        }
        sel_xi = st.selectbox("Match", list(xi_opts.keys()), key="xi_match")
        sm_xi  = xi_opts[sel_xi]

        # ── SECTION 1: Auto-fetch button ──────────────────────
        st.markdown("#### 1. Auto-fetch from ESPNcricinfo")
        st.caption("Works best ~10 min after toss when ESPNcricinfo has updated the page.")

        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🌐 Fetch XI from ESPNcricinfo", type="primary", key="xi_fetch"):
                sys.path.insert(0, os.path.join(ROOT, "scripts"))
                try:
                    from fetch_playingxi import fetch_and_store_xi
                    with st.spinner(f"Searching ESPNcricinfo for {sm_xi['team_a']} vs {sm_xi['team_b']}..."):
                        result = fetch_and_store_xi(
                            match_id   = sm_xi["match_id"],
                            match_date = sm_xi["date"],
                            team_a     = sm_xi["team_a"],
                            team_b     = sm_xi["team_b"],
                        )

                    if result["success"]:
                        st.success(f"✅ Fetched via {result['method']} — {result['count']} players saved")
                        if result.get("toss_winner"):
                            st.info(f"🪙 Toss: **{result['toss_winner']}** won and chose to **{result['toss_choice']}**")
                        for team, players in result.get("players", {}).items():
                            st.write(f"**{team}:** {', '.join(players)}")
                    else:
                        st.warning("Auto-fetch failed — ESPNcricinfo may not have updated yet. Try pasting the XI below.")

                    with st.expander("Fetch log"):
                        for line in result.get("log", []):
                            st.text(line)

                except ImportError as e:
                    st.error(f"Missing dependency: {e}\nRun: pip install requests beautifulsoup4")
                except Exception as e:
                    st.error(f"Fetch error: {e}")

        # ── SECTION 2: Paste XI text ──────────────────────────
        st.markdown("#### 2. Paste XI text (most reliable)")
        st.caption(
            "Copy the XI from Cricbuzz, ESPNcricinfo or any news article and paste below. "
            "Format: `India: Rohit Sharma, Shubman Gill(c), Virat Kohli...`"
        )

        xi_paste = st.text_area(
            "Paste playing XI text here",
            placeholder=(
                "India: Rohit Sharma, Shubman Gill(c), Virat Kohli, Shreyas Iyer, "
                "KL Rahul(wk), Washington Sundar, Axar Patel, Kuldeep Yadav, "
                "Jasprit Bumrah, Gurnoor Brar, Prasidh Krishna\n\n"
                "England: Jacob Bethell, Ben Duckett, Joe Root, Harry Brook(c), "
                "Jos Buttler(wk), Sam Curran, Will Jacks, Jofra Archer, "
                "Liam Dawson, Josh Tongue, Adil Rashid"
            ),
            height=120,
            key="xi_paste"
        )

        col1, col2 = st.columns([2, 1])
        with col1:
            dry_run = st.checkbox("Dry run (preview only, no save)", key="xi_dry")
        with col2:
            if st.button("💾 Parse & save XI", type="primary", key="xi_parse",
                         disabled=not xi_paste):
                sys.path.insert(0, os.path.join(ROOT, "scripts"))
                try:
                    from fetch_playingxi import fetch_and_store_xi
                    with st.spinner("Parsing XI..."):
                        result = fetch_and_store_xi(
                            match_id   = sm_xi["match_id"],
                            match_date = sm_xi["date"],
                            team_a     = sm_xi["team_a"],
                            team_b     = sm_xi["team_b"],
                            xi_text    = xi_paste,
                            dry_run    = dry_run,
                        )

                    if result["success"]:
                        label = "Preview" if dry_run else "Saved"
                        st.success(f"✅ {label} — {result['count']} players {'would be ' if dry_run else ''}written")
                        for team, players in result.get("players", {}).items():
                            st.write(f"**{team}:** {', '.join(players)}")
                    else:
                        st.error("Could not parse XI. Check the format and try again.")

                    with st.expander("Parse log"):
                        for line in result.get("log", []):
                            st.text(line)

                except Exception as e:
                    st.error(f"Parse error: {e}")

        st.divider()

        # ── SECTION 3: Current XI display ─────────────────────
        st.markdown("#### 3. Current XI in database")

        existing = pconn.execute("""
            SELECT xi.*, p.role, p.bowling_style
            FROM playing_xi xi
            LEFT JOIN players p ON xi.player_id = p.player_id
            WHERE xi.match_id=?
            ORDER BY xi.team, xi.batting_position NULLS LAST
        """, (sm_xi["match_id"],)).fetchall()

        if existing:
            import pandas as pd
            xi_df = pd.DataFrame([{
                "Team":      r["team"],
                "Player":    r["player_name"],
                "Role":      r["role"] or "—",
                "Style":     r["bowling_style"] or "—",
                "Available": "✅" if r["is_available"] else "❌",
                "©":         "©" if r["is_captain"] else "",
                "🧤":        "🧤" if r["is_keeper"] else "",
                "Source":    r["source"] or "manual",
                "Note":      r["injury_note"] or "",
            } for r in existing])
            st.dataframe(xi_df, width="stretch", hide_index=True)

            # Source badge
            sources = set(r["source"] for r in existing if r["source"])
            for src in sources:
                if src == "auto-scraped":
                    st.caption("🌐 Fetched automatically from ESPNcricinfo")
                elif src == "manual":
                    st.caption("✏️ Entered manually")
        else:
            st.info(f"No XI entered yet for this match. Use the fetch button or paste text above.")

        st.divider()

        # ── SECTION 4: Mark injuries ───────────────────────────
        st.markdown("#### 4. Mark injury / non-selection")
        st.caption("Quick update after late changes — scratches the player from the signal calculation.")

        all_players = pconn.execute(
            "SELECT player_id, name, team FROM players ORDER BY team, name"
        ).fetchall()
        player_opts = {f"{p['name']} ({p['team']})": dict(p) for p in all_players}

        col1, col2 = st.columns(2)
        with col1:
            sel_player = st.selectbox("Player", list(player_opts.keys()), key="xi_player")
        with col2:
            inj_note = st.text_input("Reason", placeholder="e.g. hamstring — late withdrawal", key="xi_note")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("❌ Mark OUT", key="xi_unavail", ):
                p = player_opts[sel_player]
                pconn.execute("""
                    INSERT OR REPLACE INTO playing_xi
                    (match_id, match_date, team, player_id, player_name,
                     is_available, injury_note, source)
                    VALUES (?,?,?,?,?,0,?,'manual')
                """, (sm_xi["match_id"], sm_xi["date"],
                      p["team"], p["player_id"], p["name"],
                      inj_note or "unavailable"))
                pconn.commit()
                st.error(f"❌ {p['name']} marked OUT")
                st.rerun()

        with col2:
            if st.button("✅ Mark available", key="xi_avail", ):
                p = player_opts[sel_player]
                pconn.execute("""
                    UPDATE playing_xi SET is_available=1, injury_note=NULL
                    WHERE match_id=? AND player_id=?
                """, (sm_xi["match_id"], p["player_id"]))
                pconn.commit()
                st.success(f"✅ {p['name']} marked available")
                st.rerun()

        with col3:
            if st.button("🗑 Clear all XI", key="xi_clear", ):
                pconn.execute("DELETE FROM playing_xi WHERE match_id=?", (sm_xi["match_id"],))
                pconn.commit()
                st.warning("Cleared XI for this match")
                st.rerun()

    pconn.close()

# ══════════════════════════════════════════════════════════════════════════
# PAGE: BANKROLL TRACKER
# ══════════════════════════════════════════════════════════════════════════
elif page == "📈 Bankroll tracker":
    st.title("📈 Bankroll tracker")
    st.markdown("Two-phase compound growth — **€5,000 → €124,040** across 193 bets")
    st.divider()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Start", "€5,000")
    c2.metric("Target", "€124,040")
    c3.metric("Total bets", "193")
    c4.metric("Growth", "24.8×")

    # Build compound curve
    import pandas as pd, numpy as np
    steps = list(range(194))
    bk_curve = [5000.0]
    for i in range(1, 131):
        bk_curve.append(round(bk_curve[-1] * 1.02, 2))
    for i in range(131, 194):
        bk_curve.append(round(bk_curve[-1] * 1.01, 2))

    df = pd.DataFrame({
        "Step": steps,
        "Bankroll": bk_curve,
        "Phase": ["Phase 1 (2%)" if i <= 130 else "Phase 2 (1%)" for i in steps]
    })

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[df["Phase"]=="Phase 1 (2%)"]["Step"],
        y=df[df["Phase"]=="Phase 1 (2%)"]["Bankroll"],
        name="Phase 1 — 2%/bet",
        line=dict(color="#00C8A0", width=2.5),
        fill="tozeroy", fillcolor="rgba(0,200,160,0.06)"
    ))
    fig.add_trace(go.Scatter(
        x=df[df["Phase"]=="Phase 2 (1%)"]["Step"],
        y=df[df["Phase"]=="Phase 2 (1%)"]["Bankroll"],
        name="Phase 2 — 1%/bet",
        line=dict(color="#3A8EE8", width=2.5),
        fill="tozeroy", fillcolor="rgba(58,142,232,0.06)"
    ))
    # Current position
    fig.add_vline(x=st.session_state.step, line_dash="dash",
                  line_color="#E8A020", annotation_text="Current")
    fig.update_layout(
        height=300, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#8AA0B8"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(title="Bet step", gridcolor="#1E2A38"),
        yaxis=dict(title="Bankroll (€)", gridcolor="#1E2A38",
                   tickformat="€,.0f"),
        margin=dict(l=0, r=0, t=20, b=0)
    )
    st.plotly_chart(fig, width="stretch")

    # Monthly breakdown
    st.subheader("Monthly breakdown")
    months = [
        ("Jul 2026", 34, 5000,  9800),
        ("Aug 2026", 51, 9800,  27000),
        ("Sep 2026", 38, 27000, 52856),
        ("Oct 2026", 17, 52856, 62800),
        ("Nov 2026", 32, 62800, 99000),
        ("Dec 2026", 21, 99000, 124040),
    ]
    mo_df = pd.DataFrame(months, columns=["Month","Bets","Start","End"])
    mo_df["Profit"] = mo_df["End"] - mo_df["Start"]
    mo_df["Return %"] = ((mo_df["End"] / mo_df["Start"] - 1) * 100).round(1)
    mo_df["Start"] = mo_df["Start"].apply(lambda x: f"€{x:,}")
    mo_df["End"]   = mo_df["End"].apply(lambda x: f"€{x:,}")
    mo_df["Profit"]= mo_df["Profit"].apply(lambda x: f"+€{x:,}")
    st.dataframe(mo_df, width="stretch", hide_index=True)

    # Milestones
    st.subheader("Key milestones")
    milestones = [
        (10000, 36, "Aug 1",  "The Hundred M12"),
        (20000, 71, "Aug 18", "CPL M10"),
        (30000, 91, "Sep 3",  "CPL M25"),
        (50000,117, "Sep 19", "Eng vs SL 3rd ODI"),
        (70000,137, "Oct 28", "India in NZ 3rd T20I"),
        (100000,176,"Nov 19", "India in NZ 1st Test"),
        (124040,193,"Dec 31", "BBL M18 — season finale"),
    ]
    ms_df = pd.DataFrame(milestones,
                         columns=["Target","Step","Date","Match"])
    ms_df["Target"] = ms_df["Target"].apply(lambda x: f"€{x:,}")
    reached = bankroll >= 5000
    st.dataframe(ms_df, width="stretch", hide_index=True)

# ══════════════════════════════════════════════════════════════════════════
# PAGE: ELO RATINGS
# ══════════════════════════════════════════════════════════════════════════
elif page == "🧬 ELO ratings":
    st.title("🧬 ELO ratings")
    st.markdown("Team strength ratings built from 2020–2026 match history (6,581 matches)")
    st.divider()

    import pandas as pd

    tab1, tab2, tab3 = st.tabs(["📊 All ratings", "⚔️ Matchup lookup", "📈 H2H records"])

    with tab1:
        fmt_sel = st.selectbox("Format", ["ODI","T20I","T20","Test"])
        gen_sel = st.radio("Gender", ["male","female"], horizontal=True,
                           format_func=lambda x: "Men's" if x=="male" else "Women's")

        rows = query("""
            SELECT team_id, rating, wins, losses, matches_played,
                   peak_rating, last_match_date, last_result
            FROM elo_ratings
            WHERE format=? AND gender=?
            ORDER BY rating DESC
        """, (fmt_sel, gen_sel))

        if rows:
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in rows])
            df["Win %"] = (df["wins"] / df["matches_played"] * 100).round(1)
            df["rating"] = df["rating"].round(1)
            df["peak_rating"] = df["peak_rating"].round(1)
            df = df.rename(columns={
                "team_id":"Team","rating":"ELO Rating",
                "wins":"Wins","losses":"Losses",
                "matches_played":"Played","peak_rating":"Peak",
                "last_match_date":"Last Match","last_result":"Last Result"
            })
            df = df[["Team","ELO Rating","Win %","Wins","Losses","Played","Peak","Last Match"]]
            st.dataframe(df, width="stretch", hide_index=True,
                        column_config={
                            "ELO Rating": st.column_config.ProgressColumn(
                                "ELO Rating", min_value=1200, max_value=1900, format="%.0f"
                            ),
                            "Win %": st.column_config.NumberColumn("Win %", format="%.1f%%"),
                        })
        else:
            st.info("No ELO data found. Run `python elo_engine/build.py --demo` first.")

    with tab2:
        st.subheader("Head-to-head ELO comparison")
        col1, col2 = st.columns(2)

        all_teams = [r["team_id"] for r in query(
            "SELECT DISTINCT team_id FROM elo_ratings ORDER BY team_id")]

        with col1:
            team_a = st.selectbox("Team A", all_teams,
                                  index=all_teams.index("India") if "India" in all_teams else 0)
        with col2:
            team_b = st.selectbox("Team B", all_teams,
                                  index=all_teams.index("England") if "England" in all_teams else 1)

        fmt_m  = st.selectbox("Format ", ["ODI","T20I","T20","Test"], key="fmt_m")
        gen_m  = st.radio("Gender ", ["male","female"], horizontal=True, key="gen_m",
                          format_func=lambda x: "Men's" if x=="male" else "Women's")
        venue  = st.text_input("Venue country (for home advantage)", "England")

        ra = get_elo(team_a, gen_m, fmt_m)
        rb = get_elo(team_b, gen_m, fmt_m)

        # Home
        from elo_config import HOME_COUNTRY_MAP, TEAM_NAME_MAP
        def norm(t): return TEAM_NAME_MAP.get(t.strip(), t.strip())
        home = None
        for team, countries in HOME_COUNTRY_MAP.items():
            if venue in countries:
                nt = norm(team)
                if nt == team_a: home = team_a
                elif nt == team_b: home = team_b
                break

        wp_a = elo_win_prob(ra, rb, home, team_a)
        delta = ra - rb + (100 if home == team_a else -100 if home == team_b else 0)
        factor = elo_factor(delta)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{team_a} ELO", f"{ra:.0f}")
        c2.metric(f"{team_b} ELO", f"{rb:.0f}")
        c3.metric(f"{team_a} win prob", f"{wp_a:.1%}")
        c4.metric("ELO factor", f"{factor}/10")

        if home:
            st.info(f"🏠 Home advantage: **{home}** (+100 ELO pts)")

        # H2H
        h2h = query("""
            SELECT * FROM h2h_full
            WHERE ((team_a=? AND team_b=?) OR (team_a=? AND team_b=?))
              AND gender=? AND format=?
        """, (team_a, team_b, team_b, team_a, gen_m, fmt_m))

        if h2h:
            h = dict(h2h[0])
            is_a = h["team_a"] == team_a
            aw = h["team_a_wins"] if is_a else h["team_b_wins"]
            bw = h["team_b_wins"] if is_a else h["team_a_wins"]
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.metric(f"{team_a} wins", aw)
                st.metric("Last 5 results", h["last_5_results"] or "N/A")
            with col2:
                st.metric(f"{team_b} wins", bw)
                st.metric("Current streak",
                          f"{h['current_winner']} ×{h['current_streak']}")
        else:
            st.warning("No H2H data for this matchup/format.")

    with tab3:
        st.subheader("All H2H records")
        fmt_h = st.selectbox("Format  ", ["ODI","T20I","T20","Test"], key="fmt_h")
        gen_h = st.radio("Gender  ", ["male","female"], horizontal=True, key="gen_h",
                         format_func=lambda x: "Men's" if x=="male" else "Women's")

        h2h_rows = query("""
            SELECT team_a, team_b, matches_played,
                   team_a_wins, team_b_wins, no_results,
                   team_a_win_pct, last_5_results,
                   current_winner, current_streak, last_match_date
            FROM h2h_full
            WHERE gender=? AND format=?
            ORDER BY matches_played DESC
        """, (gen_h, fmt_h))

        if h2h_rows:
            hdf = pd.DataFrame([dict(r) for r in h2h_rows])
            hdf = hdf.rename(columns={
                "team_a":"Team A","team_b":"Team B",
                "matches_played":"Played",
                "team_a_wins":"A Wins","team_b_wins":"B Wins",
                "no_results":"NR","team_a_win_pct":"A Win %",
                "last_5_results":"Last 5",
                "current_winner":"Streak Leader","current_streak":"Streak",
                "last_match_date":"Last Match"
            })
            st.dataframe(hdf, width="stretch", hide_index=True)
            st.caption(f"{len(h2h_rows)} matchup records")
        else:
            st.info("No H2H data found for this format.")

# ══════════════════════════════════════════════════════════════════════════
# PAGE: RISK FRAMEWORK
# ══════════════════════════════════════════════════════════════════════════
elif page == "🛡 Risk framework":
    st.title("🛡 Risk framework")
    st.markdown("Three automatic protection layers — run on every bet")
    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.success("**Layer 1 — Kelly fraction**\n\n¼ Kelly Phase 1 · ⅛ Kelly Phase 2\n\nNeed 50+ consecutive losses to halve bankroll.")
    with c2:
        st.warning("**Layer 2 — 5% daily cap**\n\nMax total stake any day ≤ 5% of bankroll.\n\nOverrides Kelly on busy multi-match days.")
    with c3:
        st.error("**Layer 3 — 15% weekly stop-loss**\n\nDown 15% in 7 days → pause 3 days.\n\nMandatory. Not optional.")

    st.divider()
    st.subheader("Live risk calculator")

    col1, col2 = st.columns(2)
    with col1:
        bk_r  = st.slider("Bankroll (€) ", 1000, 80000, int(bankroll), 100,
                          format="€%d", key="r_bk")
        staked= st.slider("Total staked today (€)", 0, int(bk_r * 0.10),
                          167, 10, format="€%d", key="r_st")

    cap   = round(bk_r * 0.05, 2)
    rem   = max(0, cap - staked)
    stop  = round(bk_r * 0.85, 2)
    pct   = round(staked / cap * 100, 1) if cap > 0 else 0

    with col2:
        c1, c2, c3 = st.columns(3)
        c1.metric("Daily cap (5%)", f"€{cap:,.2f}")
        c2.metric("Remaining today",
                  f"€{rem:,.2f}",
                  "✓ Safe" if rem > 0 else "⚠ At cap")
        c3.metric("Stop-loss trigger", f"€{stop:,.2f}",
                  f"Buffer: €{round(bk_r - staked - stop, 2):,.2f}")

    st.progress(min(1.0, pct / 100),
                text=f"{pct:.1f}% of daily cap used · €{staked:,.2f} of €{cap:,.2f}")

    st.divider()
    st.subheader("6 non-negotiable rules")
    rules = [
        ("green","1","Max 5% of bankroll on any single day","All matches combined. Daily cap overrides Kelly when multiple bets stack up."),
        ("green","2","Max 2% per match (all entries combined)","Pre-match + in-play on same match = one exposure limit."),
        ("orange","3","In-play only if EV still positive","Odds collapse to 1.25 after good start = no edge = do not add."),
        ("orange","4","Never add in-play after pre-match loss indicator","England post 340+? Do not chase India in the chase."),
        ("red","5","Stop-loss: down 15% in 7 days → pause 3 days","Mandatory. Resets emotional state and forces model review."),
        ("red","6","Never chase losses by increasing stake","Each bet sized independently by Kelly. Yesterday = irrelevant."),
    ]
    for colour, num, title, desc in rules:
        if colour == "green":
            st.success(f"**{num}. {title}**\n\n{desc}")
        elif colour == "orange":
            st.warning(f"**{num}. {title}**\n\n{desc}")
        else:
            st.error(f"**{num}. {title}**\n\n{desc}")

# ══════════════════════════════════════════════════════════════════════════
# PAGE: MATCH SCHEDULE
# ══════════════════════════════════════════════════════════════════════════
elif page == "📋 Match schedule":
    st.title("📋 Match schedule")
    st.markdown("193 confirmed matches · Jul 14 – Dec 31 2026")
    st.divider()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("International", "76")
    c2.metric("The Hundred", "68")
    c3.metric("BBL + WBBL", "61")
    c4.metric("Total", "193")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        cat_f = st.multiselect("Category",
            ["International","Franchise","Domestic","ACC"],
            default=["International","Franchise","Domestic","ACC"])
    with col2:
        phase_f = st.multiselect("Phase", [1, 2],
            default=[1, 2],
            format_func=lambda x: f"Phase {x}")
    with col3:
        search = st.text_input("Search team or series", "")

    # Load from DB
    matches = query("""
        SELECT step, date, label, team_a, team_b,
               format, category, phase, city, series
        FROM matches
        ORDER BY step
    """)

    import pandas as pd
    df = pd.DataFrame([dict(m) for m in matches])

    # Apply filters
    if cat_f:
        df = df[df["category"].isin(cat_f)]
    if phase_f:
        df = df[df["phase"].isin(phase_f)]
    if search:
        mask = (df["team_a"].str.contains(search, case=False) |
                df["team_b"].str.contains(search, case=False) |
                df["series"].str.contains(search, case=False, na=False))
        df = df[mask]

    st.caption(f"Showing {len(df)} matches")

    # Paginate — 15 per page
    PER_PAGE = 15
    total_pages = max(1, math.ceil(len(df) / PER_PAGE))

    if "sched_page" not in st.session_state:
        st.session_state.sched_page = 1
    if st.session_state.sched_page > total_pages:
        st.session_state.sched_page = 1

    pg = st.session_state.sched_page
    start_i = (pg - 1) * PER_PAGE
    page_df = df.iloc[start_i:start_i + PER_PAGE].copy()

    page_df = page_df.rename(columns={
        "step":"Step","date":"Date","label":"Match",
        "team_a":"Team A","team_b":"Team B",
        "format":"Format","category":"Category",
        "phase":"Phase","city":"City"
    })
    page_df = page_df[["Step","Date","Team A","Team B","Match","Format","Category","Phase","City"]]

    st.dataframe(page_df, width="stretch", hide_index=True,
                 column_config={
                     "Step": st.column_config.NumberColumn("Step", width="small"),
                     "Phase": st.column_config.NumberColumn("Phase", width="small"),
                 })

    # Pagination controls
    col_prev, col_pages, col_next = st.columns([1, 8, 1])
    with col_prev:
        if st.button("◀", disabled=(pg == 1)):
            st.session_state.sched_page -= 1
            st.rerun()
    with col_pages:
        page_buttons = st.columns(min(total_pages, 13))
        for i in range(min(total_pages, 13)):
            page_num = i + 1
            label = str(page_num) if page_num != pg else f"**{page_num}**"
            if page_buttons[i].button(label, key=f"pg_{page_num}"):
                st.session_state.sched_page = page_num
                st.rerun()
    with col_next:
        if st.button("▶", disabled=(pg == total_pages)):
            st.session_state.sched_page += 1
            st.rerun()

    st.caption(f"Page {pg} of {total_pages}")

# ══════════════════════════════════════════════════════════════════════════
# PAGE: LOG RESULT
# ══════════════════════════════════════════════════════════════════════════
elif page == "✏️ Log result":
    st.title("✏️ Log match result")
    st.markdown("Update the outcome of a bet and automatically update ELO ratings and bankroll.")
    st.divider()

    conn = get_db()

    # ── Section 1: Log bet outcome ─────────────────────────────────────
    st.subheader("1. Record bet outcome")

    # ── Filters to narrow down the match list ────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_cat = st.multiselect(
            "Filter by category",
            ["International","Franchise","Domestic","ACC"],
            default=["International","Franchise","Domestic","ACC"],
            key="log_cat"
        )
    with col2:
        filter_search = st.text_input("Search team name", "",
                                       placeholder="e.g. India, Perth...",
                                       key="log_search")
    with col3:
        filter_month = st.selectbox(
            "Filter by month",
            ["All","Jul 2026","Aug 2026","Sep 2026",
             "Oct 2026","Nov 2026","Dec 2026"],
            key="log_month"
        )

    # Build query dynamically
    month_map = {
        "Jul 2026": "2026-07", "Aug 2026": "2026-08",
        "Sep 2026": "2026-09", "Oct 2026": "2026-10",
        "Nov 2026": "2026-11", "Dec 2026": "2026-12",
    }

    sql = """
        SELECT match_id, date, step, phase, label, team_a, team_b,
               format, category, city
        FROM matches
        WHERE 1=1
    """
    params = []

    if filter_cat:
        placeholders = ",".join("?" * len(filter_cat))
        sql += f" AND category IN ({placeholders})"
        params.extend(filter_cat)

    if filter_search:
        sql += " AND (team_a LIKE ? OR team_b LIKE ? OR series LIKE ?)"
        s = f"%{filter_search}%"
        params.extend([s, s, s])

    if filter_month != "All" and filter_month in month_map:
        sql += " AND date LIKE ?"
        params.append(f"{month_map[filter_month]}%")

    sql += " ORDER BY step ASC"

    all_matches = conn.execute(sql, params).fetchall()

    st.caption(f"{len(all_matches)} matches found")

    if not all_matches:
        st.warning("No matches found with these filters.")
        st.stop()

    # Build dropdown options
    match_options = {
        f"Step {m['step']:>3} | {m['date']} | {m['team_a']} vs {m['team_b']} — {m['label']} [{m['format']}]": dict(m)
        for m in all_matches
    }

    selected_label = st.selectbox(
        f"Select match ({len(all_matches)} shown)",
        list(match_options.keys()),
        key="log_match_sel"
    )
    selected_match = match_options[selected_label]

    col1, col2, col3 = st.columns(3)
    with col1:
        outcome = st.radio("Result", ["win", "loss", "void"],
                           format_func=lambda x: {"win":"✅ Win","loss":"❌ Loss","void":"⬜ Void/NR"}[x])
    with col2:
        odds_taken = st.number_input("Odds taken", min_value=1.01, max_value=20.0,
                                     value=2.08, step=0.01, format="%.2f")
    with col3:
        stake_placed = st.number_input("Stake placed (€)", min_value=0.0,
                                       max_value=float(bankroll),
                                       value=round(bankroll * 0.033, 2),
                                       step=1.0, format="%.2f")

    # Calculate P&L
    if outcome == "win":
        pnl = round(stake_placed * (odds_taken - 1), 2)
    elif outcome == "loss":
        pnl = -stake_placed
    else:
        pnl = 0.0

    bk_after = round(bankroll + pnl, 2)

    # Show preview
    col1, col2, col3 = st.columns(3)
    col1.metric("P&L", f"€{pnl:+,.2f}",
                delta_color="normal" if pnl >= 0 else "inverse")
    col2.metric("Bankroll after", f"€{bk_after:,.2f}")
    col3.metric("Step", f"{selected_match['step']}/193")

    notes = st.text_input("Notes (optional)", placeholder="e.g. India won by 6 wickets")

    if st.button("💾 Save bet result", type="primary"):
        try:
            conn.execute("""
                INSERT INTO bet_log
                (match_id, bet_date, step, phase, bankroll_before,
                 stake, odds_taken, outcome, profit_loss, bankroll_after, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                selected_match["match_id"],
                selected_match["date"],
                selected_match["step"],
                selected_match.get("phase", 1),
                bankroll,
                stake_placed,
                odds_taken,
                outcome,
                pnl,
                bk_after,
                notes
            ))

            # Update bankroll tracker
            conn.execute("""
                INSERT OR REPLACE INTO bankroll
                (date, step, phase, opening_balance, closing_balance,
                 bets_placed, daily_pnl, cumulative_pnl)
                VALUES (?,?,?,?,?,1,?,?)
            """, (
                selected_match["date"],
                selected_match["step"],
                selected_match.get("phase", 1),
                bankroll,
                bk_after,
                pnl,
                pnl
            ))

            conn.commit()

            # Update session bankroll
            st.session_state.bankroll = bk_after
            st.session_state.step = selected_match["step"] + 1

            if outcome == "win":
                st.success(f"✅ Recorded! Bankroll updated: €{bankroll:,.2f} → €{bk_after:,.2f} (+€{pnl:,.2f})")
            elif outcome == "loss":
                st.error(f"❌ Recorded. Bankroll updated: €{bankroll:,.2f} → €{bk_after:,.2f} (€{pnl:,.2f})")
            else:
                st.info(f"⬜ Void recorded. Bankroll unchanged at €{bankroll:,.2f}")

        except Exception as e:
            st.error(f"Error saving: {e}")

    st.divider()

    # ── Section 2: Update ELO after match ─────────────────────────────
    st.subheader("2. Update ELO ratings")
    st.markdown("After logging the bet, also update ELO so future decisions use fresh ratings.")

    col1, col2 = st.columns(2)
    with col1:
        elo_team_a = st.text_input("Team A", value=selected_match.get("team_a","India"))
        elo_team_b = st.text_input("Team B", value=selected_match.get("team_b","England"))
        elo_winner = st.selectbox("Winner",
            [elo_team_a, elo_team_b, "no_result"],
            format_func=lambda x: x if x != "no_result" else "No result / Abandoned")
    with col2:
        elo_format = st.selectbox("Format ",
            ["ODI","T20I","T20","Test"],
            index=["ODI","T20I","T20","Test"].index(
                selected_match.get("format","ODI")
                if selected_match.get("format","ODI") in ["ODI","T20I","T20","Test"]
                else "ODI"))
        elo_gender = st.radio("Gender ", ["male","female"], horizontal=True,
                              format_func=lambda x: "Men's" if x=="male" else "Women's")
        elo_venue  = st.text_input("Venue country",
                                   value=selected_match.get("city","England"))
        elo_mtype  = st.selectbox("Match type",
                                  ["bilateral","icc_event","domestic"])

    # Show current ELO before update
    ra_cur = get_elo(elo_team_a, elo_gender, elo_format)
    rb_cur = get_elo(elo_team_b, elo_gender, elo_format)
    col1, col2 = st.columns(2)
    col1.metric(f"{elo_team_a} current ELO", f"{ra_cur:.0f}")
    col2.metric(f"{elo_team_b} current ELO", f"{rb_cur:.0f}")

    if st.button("🔄 Update ELO ratings", type="secondary"):
        try:
            from elo_config import k_factor as kf_func, TEAM_NAME_MAP, HOME_COUNTRY_MAP

            def norm_t(t): return TEAM_NAME_MAP.get(t.strip(), t.strip())

            ta = norm_t(elo_team_a)
            tb = norm_t(elo_team_b)
            winner = norm_t(elo_winner) if elo_winner not in ("no_result",) else "no_result"

            # Home detection
            home = None
            for team, countries in HOME_COUNTRY_MAP.items():
                nt = TEAM_NAME_MAP.get(team, team)
                if elo_venue in countries:
                    if nt == ta: home = ta
                    elif nt == tb: home = tb
                    break

            k = kf_func(elo_mtype, ta, tb)
            ea = elo_win_prob(ra_cur, rb_cur, home, ta)
            eb = 1 - ea

            sa = 1.0 if winner == ta else 0.0 if winner != "no_result" else ea
            sb = 1.0 if winner == tb else 0.0 if winner != "no_result" else eb

            ra_new = round(ra_cur + k * (sa - ea), 2)
            rb_new = round(rb_cur + k * (sb - eb), 2)

            now = datetime.now().isoformat()
            match_date = selected_match["date"]

            for team, r_old, r_new, opp, exp, s in [
                (ta, ra_cur, ra_new, tb, ea, sa),
                (tb, rb_cur, rb_new, ta, eb, sb)
            ]:
                result = "win" if s == 1.0 else "loss" if s == 0.0 else "nr"
                from INTERNATIONAL_TEAMS import INTERNATIONAL_TEAMS
                team_type = "international" if team in INTERNATIONAL_TEAMS else "franchise"

                row = conn.execute("""
                    SELECT peak_rating, matches_played, wins, losses
                    FROM elo_ratings WHERE team_id=? AND gender=? AND format=?
                """, (team, elo_gender, elo_format)).fetchone()

                peak   = max(row["peak_rating"] if row else 1500, r_new)
                played = (row["matches_played"] if row else 0) + 1
                wins   = (row["wins"] if row else 0) + (1 if result == "win" else 0)
                losses = (row["losses"] if row else 0) + (1 if result == "loss" else 0)

                conn.execute("""
                    INSERT OR REPLACE INTO elo_ratings
                    (team_id, team_type, gender, format, rating, matches_played,
                     wins, losses, peak_rating, last_match_date,
                     last_opponent, last_result, last_updated)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (team, team_type, elo_gender, elo_format,
                      r_new, played, wins, losses, peak,
                      match_date, opp, result, now))

            conn.commit()

            col1, col2 = st.columns(2)
            col1.metric(f"{elo_team_a} new ELO", f"{ra_new:.0f}",
                        f"{ra_new - ra_cur:+.1f}")
            col2.metric(f"{elo_team_b} new ELO", f"{rb_new:.0f}",
                        f"{rb_new - rb_cur:+.1f}")
            st.success(f"✅ ELO ratings updated! K={k}")

        except Exception as e:
            st.error(f"ELO update error: {e}")
            st.info("Tip: Make sure team names match exactly — e.g. 'India', 'England', 'Perth Scorchers'")

    st.divider()

    # ── Section 3: Bet history ─────────────────────────────────────────
    st.subheader("3. Bet history")

    history = conn.execute("""
        SELECT bl.bet_date, bl.step, bl.stake, bl.odds_taken,
               bl.outcome, bl.profit_loss, bl.bankroll_before,
               bl.bankroll_after, bl.notes,
               m.team_a, m.team_b, m.label
        FROM bet_log bl
        LEFT JOIN matches m ON bl.match_id = m.match_id
        ORDER BY bl.step DESC
        LIMIT 20
    """).fetchall()

    if history:
        import pandas as pd
        hdf = pd.DataFrame([dict(h) for h in history])
        hdf["Match"] = hdf["team_a"] + " vs " + hdf["team_b"]
        hdf["P&L"] = hdf["profit_loss"].apply(lambda x: f"€{x:+,.2f}")
        hdf["Bankroll after"] = hdf["bankroll_after"].apply(lambda x: f"€{x:,.2f}")
        hdf = hdf[["step","bet_date","Match","label","stake",
                   "odds_taken","outcome","P&L","Bankroll after","notes"]]
        hdf.columns = ["Step","Date","Match","Label","Stake","Odds","Result","P&L","Bankroll","Notes"]
        st.dataframe(hdf, width="stretch", hide_index=True)

        # Summary
        wins_  = sum(1 for h in history if h["outcome"] == "win")
        losses_= sum(1 for h in history if h["outcome"] == "loss")
        total_pnl = sum(h["profit_loss"] or 0 for h in history)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Bets logged", len(history))
        c2.metric("Wins", wins_)
        c3.metric("Losses", losses_)
        c4.metric("Total P&L", f"€{total_pnl:+,.2f}")
    else:
        st.info("No bets logged yet. Use the form above to record your first result.")

# ══════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS & UPDATES
# ══════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Settings & updates":
    import datetime as dt
    import subprocess

    st.title("⚙️ Settings & updates")
    st.markdown(
        "Press buttons to refresh each component of the engine. "
        "Recommended: run **Full Sunday refresh** once a week."
    )
    st.divider()

    conn = get_db()

    # ── DB status summary ──────────────────────────────────────
    st.subheader("📊 Current database status")

    def db_stat(sql, label):
        try:
            return conn.execute(sql).fetchone()[0]
        except Exception:
            return "—"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ELO ratings",    db_stat("SELECT COUNT(*) FROM elo_ratings WHERE matches_played > 0", ""))
    col2.metric("ELO history",    db_stat("SELECT COUNT(*) FROM elo_history", ""))
    col3.metric("H2H records",    db_stat("SELECT COUNT(*) FROM h2h_full", ""))
    col4.metric("Matches in DB",  db_stat("SELECT COUNT(*) FROM matches", ""))

    col1, col2, col3, col4 = st.columns(4)
    last_elo = db_stat("SELECT MAX(last_updated) FROM elo_ratings", "")
    last_h2h = db_stat("SELECT MAX(last_updated) FROM h2h_full", "")
    col1.metric("Last ELO update", str(last_elo)[:10] if last_elo else "never")
    col2.metric("Last H2H update", str(last_h2h)[:10] if last_h2h else "never")

    # In-play DB
    try:
        ip_conn = sqlite3.connect(os.path.join(ROOT, "db", "inplay_engine.db"))
        n_cells = ip_conn.execute("SELECT COUNT(*) FROM wp_lookup").fetchone()[0]
        last_built = ip_conn.execute("SELECT MAX(built_at) FROM wp_build_log").fetchone()[0]
        ip_conn.close()
        col3.metric("WP table cells", f"{n_cells:,}")
        col4.metric("WP table built", str(last_built)[:10] if last_built else "never")
    except Exception:
        col3.metric("WP table cells", "—")
        col4.metric("WP table built", "—")

    st.divider()

    # ── Individual update buttons ──────────────────────────────
    st.subheader("🔧 Individual updates")

    # ── 1. ELO rebuild ────────────────────────────────────────
    with st.expander("🧬 Rebuild ELO ratings (from 2024)", expanded=False):
        st.markdown(
            "Rebuilds all ELO ratings and H2H records from 2024 data in the match log. "
            "Run after adding real Cricsheet data, or after manually logging multiple results."
        )
        col1, col2 = st.columns([2, 1])
        with col1:
            cutoff = st.selectbox("Data cutoff year", [2024, 2023, 2022],
                                  index=0, key="elo_cutoff")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            run_elo = st.button("🔄 Rebuild ELO", key="btn_elo", type="primary")

        if run_elo:
            with st.spinner("Rebuilding ELO ratings from scratch..."):
                try:
                    cutoff_date = f"{cutoff}-01-01"
                    # Reset ratings
                    conn.execute("UPDATE elo_ratings SET rating=1500.0, matches_played=0, wins=0, losses=0")
                    # Delete history before cutoff
                    conn.execute("DELETE FROM elo_history WHERE match_date < ?", (cutoff_date,))
                    conn.execute("DELETE FROM elo_match_log WHERE match_date < ?", (cutoff_date,))

                    # Rebuild from history
                    ratings = {}
                    history = conn.execute("""
                        SELECT team_id, gender, format, result, match_date,
                               rating_after, k_factor
                        FROM elo_history WHERE match_date >= ?
                        ORDER BY match_date
                    """, (cutoff_date,)).fetchall()

                    for h in history:
                        key = (h[0], h[1], h[2])
                        ratings[key] = h[5]  # rating_after

                    for (team, gender, fmt), rating in ratings.items():
                        wl = conn.execute("""
                            SELECT SUM(CASE WHEN result='win' THEN 1 ELSE 0 END),
                                   SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END),
                                   COUNT(*)
                            FROM elo_history
                            WHERE team_id=? AND gender=? AND format=?
                              AND match_date >= ?
                        """, (team, gender, fmt, cutoff_date)).fetchone()

                        intl_teams = {'India','England','Australia','Pakistan',
                                      'West Indies','New Zealand','South Africa',
                                      'Sri Lanka','Bangladesh','Afghanistan','Zimbabwe','Ireland',
                                      'India Women','England Women','Australia Women'}
                        team_type = 'international' if team in intl_teams else 'franchise'

                        conn.execute("""
                            INSERT OR REPLACE INTO elo_ratings
                            (team_id, team_type, gender, format, rating,
                             matches_played, wins, losses, peak_rating, last_updated)
                            VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))
                        """, (team, team_type, gender, fmt, round(rating, 2),
                              wl[2] or 0, wl[0] or 0, wl[1] or 0, round(rating, 2)))

                    conn.commit()
                    n_updated = len(ratings)
                    st.success(f"✅ ELO rebuilt — {n_updated} team-format ratings updated from {cutoff}+ data")

                    # Show top 5
                    top = conn.execute("""
                        SELECT team_id, format, rating FROM elo_ratings
                        WHERE matches_played > 0 AND format='ODI' AND gender='male'
                        ORDER BY rating DESC LIMIT 5
                    """).fetchall()
                    if top:
                        import pandas as pd
                        st.dataframe(pd.DataFrame(top, columns=["Team","Format","ELO"]),
                                     width="stretch", hide_index=True)
                except Exception as e:
                    st.error(f"ELO rebuild error: {e}")

    # ── 2. Win probability table rebuild ──────────────────────
    with st.expander("👁 Rebuild win probability table", expanded=False):
        st.markdown(
            "Rebuilds the in-play lookup table from Cricsheet data. "
            "**Demo mode** uses synthetic data — works immediately with no files needed. "
            "**Production mode** requires real Cricsheet CSVs uploaded to the server."
        )
        mode = st.radio("Build mode", ["Demo (no files needed)", "Production (Cricsheet CSVs)"],
                        key="wp_mode", horizontal=True)
        data_dir = ""
        if "Production" in mode:
            data_dir = st.text_input("Cricsheet CSV directory path",
                                     placeholder="/path/to/cricsheet_csvs",
                                     key="wp_dir")

        col1, col2 = st.columns([2, 1])
        with col1:
            st.caption(
                "Demo generates 3,200 simulated matches (~8,500 probability cells). "
                "Production with real Cricsheet data generates 40,000+ cells with higher accuracy."
            )
        with col2:
            run_wp = st.button("🔄 Rebuild WP table", key="btn_wp", type="primary")

        if run_wp:
            with st.spinner("Building win probability table... (this takes 1-3 minutes)"):
                try:
                    sys.path.insert(0, os.path.join(ROOT, "inplay_engine"))
                    from build_wp_table import get_conn as ip_get_conn, build_demo, process_cricsheet

                    ip_conn = ip_get_conn()

                    if "Production" in mode and data_dir and os.path.exists(data_dir):
                        process_cricsheet(data_dir, ip_conn)
                        method = f"Cricsheet data from {data_dir}"
                    else:
                        build_demo(ip_conn)
                        method = "Demo mode (synthetic 2024+ data)"

                    n_cells = ip_conn.execute("SELECT COUNT(*) FROM wp_lookup").fetchone()[0]
                    ip_conn.close()
                    st.success(f"✅ Win probability table rebuilt — {n_cells:,} cells via {method}")

                    # Show sample
                    ip_conn2 = sqlite3.connect(os.path.join(ROOT, "db", "inplay_engine.db"))
                    ip_conn2.row_factory = sqlite3.Row
                    samples = ip_conn2.execute("""
                        SELECT format, balls_remaining, wickets_lost,
                               runs_needed, win_pct, sample_size, confidence
                        FROM wp_lookup WHERE sample_size >= 30
                        ORDER BY RANDOM() LIMIT 6
                    """).fetchall()
                    if samples:
                        import pandas as pd
                        sdf = pd.DataFrame([dict(s) for s in samples])
                        sdf["win_pct"] = sdf["win_pct"].apply(lambda x: f"{x:.1f}%")
                        st.dataframe(sdf, width="stretch", hide_index=True)
                    ip_conn2.close()

                except Exception as e:
                    st.error(f"WP rebuild error: {e}")

    # ── 3. Weather refresh ─────────────────────────────────────
    with st.expander("🌤 Refresh weather data", expanded=False):
        st.markdown(
            "Fetches fresh weather forecasts from Open-Meteo (free, no API key) "
            "for all matches in the next 7 days."
        )
        if st.button("🔄 Refresh weather", key="btn_wx", type="primary"):
            with st.spinner("Fetching weather from Open-Meteo..."):
                try:
                    import importlib.util, json
                    spec = importlib.util.spec_from_file_location(
                        "fetch_weather",
                        os.path.join(ROOT, "scripts", "03_fetch_weather.py")
                    )
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    today = dt.date.today().isoformat()
                    week_end = (dt.date.today() + dt.timedelta(days=7)).isoformat()
                    upcoming = conn.execute("""
                        SELECT DISTINCT m.venue_id, m.date, v.latitude, v.longitude, v.name
                        FROM matches m
                        JOIN venues v ON v.venue_id = m.venue_id
                        WHERE m.date BETWEEN ? AND ?
                    """, (today, week_end)).fetchall()

                    updated = 0
                    failed  = []
                    for row in upcoming:
                        try:
                            result = mod.fetch_weather(row[2], row[3], row[1])
                            if result:
                                conn.execute("""
                                    INSERT OR REPLACE INTO weather
                                    (venue_id, match_date, fetched_at, rain_prob_pct,
                                     temp_celsius, condition, dl_risk)
                                    VALUES (?,?,datetime('now'),?,?,?,?)
                                """, (row[0], row[1],
                                      result.get("rain_prob", 0),
                                      result.get("temp", 20),
                                      result.get("condition", "unknown"),
                                      result.get("dl_risk", "low")))
                                updated += 1
                        except Exception:
                            failed.append(row[4])

                    conn.commit()
                    st.success(f"✅ Weather updated for {updated} venue-date combinations")
                    if failed:
                        st.warning(f"Failed: {', '.join(failed)}")
                except Exception as e:
                    st.warning(f"Weather fetch not available: {e}\n\nOpen-Meteo fetch requires network access to api.open-meteo.com")

    # ── 4. Clear old data ──────────────────────────────────────
    with st.expander("🗑 Clear old data", expanded=False):
        st.markdown("Remove stale records from the database.")
        st.warning("⚠️ This cannot be undone. Make sure you have a backup.")

        col1, col2 = st.columns(2)
        with col1:
            clear_year = st.selectbox("Delete data before year",
                                      [2024, 2025], index=0, key="clear_year")
        with col2:
            confirm = st.checkbox(f"I confirm: delete all data before {clear_year}", key="clear_confirm")

        if confirm and st.button("🗑 Clear old data", key="btn_clear", type="secondary"):
            cutoff = f"{clear_year}-01-01"
            deleted_hist = conn.execute("DELETE FROM elo_history WHERE match_date < ?", (cutoff,)).rowcount
            deleted_log  = conn.execute("DELETE FROM elo_match_log WHERE match_date < ?", (cutoff,)).rowcount
            conn.commit()
            st.success(f"✅ Deleted {deleted_hist} history records and {deleted_log} match log entries before {clear_year}")

    st.divider()

    # ── FULL SUNDAY REFRESH ────────────────────────────────────
    st.subheader("🗓 Full Sunday refresh")
    st.markdown("""
    Runs all updates in one go. Recommended weekly cadence:

    | Step | What it does | Time |
    |---|---|---|
    | 1 | Rebuild ELO from 2024+ history | ~10 sec |
    | 2 | Rebuild win probability table (demo) | ~90 sec |
    | 3 | Refresh weather for next 7 days | ~15 sec |

    **Total: ~2 minutes.** Press the button and come back.
    """)

    col1, col2 = st.columns([1, 2])
    with col1:
        sunday_mode = st.radio("WP table mode",
                               ["Demo", "Cricsheet (if available)"],
                               key="sun_mode", horizontal=False)
        cricsheet_path = ""
        if "Cricsheet" in sunday_mode:
            cricsheet_path = st.text_input("Cricsheet path", key="sun_cs_path",
                                           placeholder="/path/to/csvs")

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_sunday = st.button("🔄 Run full Sunday refresh",
                               type="primary", key="btn_sunday")

    if run_sunday:
        progress = st.progress(0, text="Starting refresh...")
        log = []

        # Step 1: ELO
        progress.progress(5, text="Step 1/3 — Rebuilding ELO ratings...")
        try:
            conn.execute("UPDATE elo_ratings SET rating=1500.0, matches_played=0, wins=0, losses=0")
            conn.execute("DELETE FROM elo_history WHERE match_date < '2024-01-01'")
            conn.execute("DELETE FROM elo_match_log WHERE match_date < '2024-01-01'")

            ratings = {}
            for h in conn.execute("""
                SELECT team_id, gender, format, result, rating_after
                FROM elo_history WHERE match_date >= '2024-01-01'
                ORDER BY match_date
            """).fetchall():
                ratings[(h[0], h[1], h[2])] = h[4]

            for (team, gender, fmt), rating in ratings.items():
                wl = conn.execute("""
                    SELECT SUM(CASE WHEN result='win' THEN 1 ELSE 0 END),
                           SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END),
                           COUNT(*)
                    FROM elo_history
                    WHERE team_id=? AND gender=? AND format=? AND match_date >= '2024-01-01'
                """, (team, gender, fmt)).fetchone()
                conn.execute("""
                    INSERT OR REPLACE INTO elo_ratings
                    (team_id, team_type, gender, format, rating,
                     matches_played, wins, losses, peak_rating, last_updated)
                    VALUES (?,
                        CASE WHEN ? IN ('India','England','Australia','Pakistan',
                        'West Indies','New Zealand','South Africa','Sri Lanka',
                        'Bangladesh','Afghanistan','Zimbabwe','Ireland')
                        THEN 'international' ELSE 'franchise' END,
                        ?,?,?,?,?,?,?,datetime('now'))
                """, (team, team, gender, fmt, round(rating,2),
                      wl[2] or 0, wl[0] or 0, wl[1] or 0, round(rating,2)))

            conn.commit()
            log.append(f"✅ ELO: {len(ratings)} ratings rebuilt from 2024+ data")
        except Exception as e:
            log.append(f"❌ ELO failed: {e}")

        progress.progress(35, text="Step 2/3 — Rebuilding win probability table...")

        # Step 2: WP table
        try:
            sys.path.insert(0, os.path.join(ROOT, "inplay_engine"))
            from build_wp_table import get_conn as ip_get_conn, build_demo, process_cricsheet

            ip_conn = ip_get_conn()
            use_cricsheet = ("Cricsheet" in sunday_mode
                             and cricsheet_path
                             and os.path.exists(cricsheet_path))
            if use_cricsheet:
                process_cricsheet(cricsheet_path, ip_conn)
                log.append(f"✅ WP table: rebuilt from real Cricsheet data at {cricsheet_path}")
            else:
                build_demo(ip_conn)
                n_cells = ip_conn.execute("SELECT COUNT(*) FROM wp_lookup").fetchone()[0]
                log.append(f"✅ WP table: {n_cells:,} cells rebuilt (demo mode)")
            ip_conn.close()
        except Exception as e:
            log.append(f"❌ WP table failed: {e}")

        progress.progress(75, text="Step 3/3 — Refreshing weather...")

        # Step 3: Weather (best effort)
        try:
            import requests as req_lib
            today_str = dt.date.today().isoformat()
            week_str  = (dt.date.today() + dt.timedelta(days=7)).isoformat()
            venues = conn.execute("""
                SELECT DISTINCT m.venue_id, m.date, v.latitude, v.longitude
                FROM matches m JOIN venues v ON v.venue_id = m.venue_id
                WHERE m.date BETWEEN ? AND ? AND v.latitude IS NOT NULL
            """, (today_str, week_str)).fetchall()

            wx_updated = 0
            for venue_id, mdate, lat, lon in venues:
                try:
                    r = req_lib.get(
                        f"https://api.open-meteo.com/v1/forecast"
                        f"?latitude={lat}&longitude={lon}"
                        f"&daily=precipitation_probability_max,temperature_2m_max"
                        f"&timezone=auto&start_date={mdate}&end_date={mdate}",
                        timeout=5
                    )
                    if r.status_code == 200:
                        data = r.json()
                        rain = data["daily"]["precipitation_probability_max"][0]
                        temp = data["daily"]["temperature_2m_max"][0]
                        cond = "rain" if rain > 60 else "cloudy" if rain > 30 else "clear"
                        dl   = "high" if rain > 60 else "medium" if rain > 30 else "low"
                        conn.execute("""
                            INSERT OR REPLACE INTO weather
                            (venue_id, match_date, fetched_at,
                             rain_prob_pct, temp_celsius, condition, dl_risk)
                            VALUES (?,?,datetime('now'),?,?,?,?)
                        """, (venue_id, mdate, rain, temp, cond, dl))
                        wx_updated += 1
                except Exception:
                    pass
            conn.commit()
            log.append(f"✅ Weather: {wx_updated} venue-dates updated")
        except Exception as e:
            log.append(f"⚠️ Weather: skipped ({e})")

        progress.progress(100, text="Done ✅")

        # Results
        st.divider()
        st.subheader("Refresh complete")
        for line in log:
            if line.startswith("✅"):
                st.success(line)
            elif line.startswith("⚠️"):
                st.warning(line)
            else:
                st.error(line)

        # Updated stats
        col1, col2, col3 = st.columns(3)
        col1.metric("ELO ratings active",
                    conn.execute("SELECT COUNT(*) FROM elo_ratings WHERE matches_played>0").fetchone()[0])
        col2.metric("H2H records",
                    conn.execute("SELECT COUNT(*) FROM h2h_full").fetchone()[0])
        try:
            ip_c = sqlite3.connect(os.path.join(ROOT, "db", "inplay_engine.db"))
            col3.metric("WP table cells", f"{ip_c.execute('SELECT COUNT(*) FROM wp_lookup').fetchone()[0]:,}")
            ip_c.close()
        except Exception:
            col3.metric("WP table cells", "—")

        st.caption(f"Last refresh: {dt.datetime.now().strftime('%A %d %b %Y %H:%M')}")

    st.divider()

    # ── Config settings ────────────────────────────────────────
    st.subheader("⚙️ Engine configuration")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**In-play thresholds**")
        add_thresh = st.slider("ADD edge threshold (%)", 3, 15, 6, 1,
                               help="Minimum edge required to ADD in-play")
        hedge_odds = st.slider("HEDGE odds trigger", 1.10, 1.50, 1.28, 0.01,
                               format="%.2f",
                               help="Lay to lock profit when odds drop below this")
        exit_thresh = st.slider("EXIT edge threshold (%)", -20, -5, -10, 1,
                                help="Exit position when model is this far wrong")
    with col2:
        st.markdown("**Daily brief**")
        week_days = st.slider("Brief horizon (days ahead)", 3, 14, 7, 1,
                              help="How many days ahead to show in daily brief")
        min_conf = st.slider("Min confidence to show BET", 60, 80, 72, 1,
                             help="Confidence score threshold for BET verdict")
        st.markdown("**ELO engine**")
        elo_blend = st.slider("ELO blend in in-play (%)", 10, 50, 30, 5,
                              help="How much ELO vs historical table in WP calculation")

    if st.button("💾 Save configuration", key="btn_save_config"):
        # Store in session state for this session
        st.session_state["add_thresh"]  = add_thresh / 100
        st.session_state["hedge_odds"]  = hedge_odds
        st.session_state["exit_thresh"] = exit_thresh / 100
        st.session_state["week_days"]   = week_days
        st.session_state["min_conf"]    = min_conf
        st.session_state["elo_blend"]   = elo_blend / 100
        st.success("✅ Configuration saved for this session")
        st.caption("Note: config resets on app restart. Persistent config storage coming in a future update.")
