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
        "📈 Bankroll tracker",
        "🧬 ELO ratings",
        "🛡 Risk framework",
        "📋 Match schedule",
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
    st.title("📅 Daily brief")
    today = date.today().strftime("%A, %d %B %Y")
    st.markdown(f"**{today}** · Bankroll **€{bankroll:,.2f}** · Phase {ph} · {'2%' if ph==1 else '1%'} target/bet")
    st.divider()

    # Top metrics
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Bankroll", f"€{bankroll:,.2f}")
    c2.metric("This week bets", "3")
    c3.metric("Total stake", "€374")
    c4.metric("Max profit", "€403", "+€403")

    st.subheader("This week's verdicts")

    # ── Match cards ──────────────────────────────────────────────────────
    weekly = [
        {
            "label": "1st ODI — INDIA vs England",
            "meta": "Edgbaston, Birmingham · Today · Step 1",
            "verdict": "BET",
            "odds": 2.08,
            "conf": 74,
            "ev": 14.4,
            "stake": round(bankroll * 0.033, 2),
            "reason": (
                "India won last **5 ODIs** vs England (8-2 in last 10). "
                "Rohit avg 89.4 at Edgbaston. Kohli avg 123 in last 7 ODI innings. "
                "Weather: ☀️ Clear 29°C, rain <5%. ELO: India 1799 vs England 1551 (+249 delta)."
            ),
            "card": "bet-card",
        },
        {
            "label": "2nd ODI — INDIA vs England (D/N)",
            "meta": "Sophia Gardens, Cardiff · Thu 16 Jul · Step 3",
            "verdict": "BET",
            "odds": 2.05,
            "conf": 72,
            "ev": 8.7,
            "stake": round(bankroll * 0.028, 2),
            "reason": (
                "D/N Cardiff — dew in 2nd innings benefits chaser. "
                "India's 5-match ODI winning streak vs England continues. "
                "Confirm Betfair odds Thursday morning before placing."
            ),
            "card": "bet-card",
        },
        {
            "label": "3rd ODI — INDIA vs England (Lord's)",
            "meta": "Lord's, London · Sun 19 Jul · Step 5 · Series decider",
            "verdict": "BET",
            "odds": 2.10,
            "conf": 72,
            "ev": 9.2,
            "stake": round(bankroll * 0.028, 2),
            "reason": (
                "Lord's series decider. India's historical record at Lord's strong. "
                "High importance match. Confirm odds Sunday morning."
            ),
            "card": "bet-card",
        },
        {
            "label": "WI vs New Zealand — 3 ODIs",
            "meta": "Providence & Barbados · Jul 14, 16, 19",
            "verdict": "SKIP",
            "odds": 1.68,
            "conf": 51,
            "ev": -3.2,
            "stake": 0,
            "reason": (
                "WI priced 1.65–1.72 — market already overprices them. "
                "Negative EV on all three. No value available this week."
            ),
            "card": "skip-card",
        },
    ]

    for m in weekly:
        css = m["card"]
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"""
            <div class="{css}">
              <div class="card-title">{m['label']}</div>
              <div class="card-meta">{m['meta']}</div>
              <div style="display:flex;gap:16px;margin-top:8px;font-size:13px">
                <span>Odds: <strong>{m['odds']}</strong></span>
                <span>Confidence: <strong>{m['conf']}/100</strong></span>
                <span>EV: <strong style="color:{'#1DB87A' if m['ev']>0 else '#E84040'}">{m['ev']:+.1f}%</strong></span>
                <span>Stake: <strong>€{m['stake']:,.2f}</strong></span>
              </div>
              <div class="card-reason">{m['reason']}</div>
            </div>
            """, unsafe_allow_html=True)

    # Supplementary markets
    st.markdown("""
    <div class="supp-box">
    <strong style="color:#3A8EE8">📊 Supplementary markets — Betfair/Sky Bet (Edgbaston today)</strong><br><br>
    Both teams 300+ runs: <strong>7/4 (2.75)</strong> — flat pitch, clear 29°C, all top batters playing<br>
    Both teams 325+: <strong>4/1 (5.00)</strong> — speculative, England scored 400 here last summer<br>
    Kohli top India scorer: <strong>5/2 (3.50)</strong> — avg 123 in last 7 ODI innings<br>
    KL Rahul top bat India: <strong>8/1 (9.00)</strong> — value if he opens
    </div>
    """, unsafe_allow_html=True)

    # In-play rules
    st.divider()
    st.subheader("In-play rules — today's match")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.success("**Entry 1 — Pre-match**\n\nBet India at 2.08 before 11:00 BST. Max exposure today: 3.3% of bankroll.")
    with c2:
        st.warning("**Entry 2 — Innings break (optional)**\n\nOnly if England post 260–290. Add max €83 at odds 1.75–1.95. Total stays under 5% cap.")
    with c3:
        st.error("**No entry after 15 overs**\n\nNever add after 15 overs of the chase. One match = max 2 entries = max 5% bankroll.")

# ══════════════════════════════════════════════════════════════════════════
# PAGE: DECISION ENGINE
# ══════════════════════════════════════════════════════════════════════════
elif page == "🎯 Decision engine":
    st.title("🎯 Decision engine")
    st.markdown("Enter match details to get a real-time Kelly stake and verdict.")
    st.divider()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Market inputs")
        odds  = st.slider("Decimal odds", 1.40, 3.50, 2.08, 0.01,
                          format="%.2f")
        wp    = st.slider("Your win probability (%)", 30, 75, 55) / 100
        bk_e  = st.slider("Bankroll (€)", 1000, 80000, int(bankroll), 100,
                          format="€%d")
        ph_e  = st.radio("Phase", [1, 2],
                         format_func=lambda x: f"Phase {x} ({'¼' if x==1 else '⅛'} Kelly)",
                         horizontal=True, index=ph - 1)

        st.subheader("Condition factors")
        form    = st.slider("Team form (1–10)", 1.0, 10.0, 7.0, 0.5)
        h2h_s   = st.slider("H2H / ELO factor (1–10)", 1.0, 10.0, 6.0, 0.5)
        weather = st.slider("Weather (1–10)", 1, 10, 9)
        players = st.slider("Player availability (1–10)", 1, 10, 8)

    with col2:
        st.subheader("Engine output")
        stake, ev, kf_pct = kelly(odds, wp, bk_e, ph_e)
        conf = confidence(ev, form, h2h_s, weather, players)
        v, vc = verdict(conf, ev)
        impl = round(1 / odds * 100, 1)
        edge = round(wp * 100 - impl, 1)

        # Verdict box
        if v == "BET":
            st.success(f"### ✅ {v}")
        elif v == "REDUCE":
            st.warning(f"### ⚡ {v} STAKE")
        else:
            st.info(f"### ⏸ {v}")

        # Metrics
        m1, m2 = st.columns(2)
        m1.metric("Recommended stake", f"€{stake:,.2f}", f"{kf_pct:.1f}% of bankroll")
        m2.metric("Expected value", f"{ev:+.1f}%",
                  "Positive edge ✓" if ev > 0 else "No edge ✗")

        m3, m4 = st.columns(2)
        m3.metric("Confidence score", f"{conf}/100",
                  "Above BET threshold" if conf >= 72 else
                  "Above REDUCE threshold" if conf >= 52 else "Below threshold")
        m4.metric("Your edge over market", f"{edge:+.1f}%",
                  f"Mkt implied: {impl}%")

        m5, m6 = st.columns(2)
        m5.metric("Profit if win", f"+€{round(stake * (odds-1), 2):,.2f}")
        m6.metric("Loss if lose", f"-€{stake:,.2f}")

        # Confidence bar
        st.divider()
        bar_col = "green" if conf >= 72 else "orange" if conf >= 52 else "red"
        st.markdown(f"**Confidence breakdown** — {conf}/100")
        st.progress(conf / 100)

        # Factor chart
        import pandas as pd
        factors_df = pd.DataFrame({
            "Factor": ["Value edge (EV)","Team form","H2H/ELO","Weather","Players","Market"],
            "Score":  [
                round(min(10, max(0, 5 + ev * 0.15)), 1),
                form, h2h_s, weather, players, 8.5
            ],
            "Weight": ["22%","14%","10%","10%","10%","8%"]
        })
        st.dataframe(factors_df, use_container_width=True, hide_index=True)

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
    st.plotly_chart(fig, use_container_width=True)

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
    st.dataframe(mo_df, use_container_width=True, hide_index=True)

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
    st.dataframe(ms_df, use_container_width=True, hide_index=True)

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
            st.dataframe(df, use_container_width=True, hide_index=True,
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
            st.dataframe(hdf, use_container_width=True, hide_index=True)
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

    st.dataframe(page_df, use_container_width=True, hide_index=True,
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
