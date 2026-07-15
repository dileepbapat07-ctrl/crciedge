-- ============================================================
-- Player Analytics Engine — player_engine.db
-- Independent from cricket_engine.db
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── 1. PLAYERS — master registry ─────────────────────────────
CREATE TABLE IF NOT EXISTS players (
    player_id       TEXT PRIMARY KEY,       -- e.g. "kohli-virat-ind"
    name            TEXT NOT NULL,
    short_name      TEXT,                   -- "Kohli", "Root"
    team            TEXT NOT NULL,
    gender          TEXT DEFAULT 'male',
    role            TEXT,                   -- bat/bowl/all/wk
    batting_style   TEXT,                   -- RHB / LHB
    bowling_style   TEXT,                   -- RF/RFM/RM/OB/LB/SLA/SLO/none
    batting_position INTEGER,               -- typical batting position 1-11
    is_key_player   INTEGER DEFAULT 0,      -- 1 = top 4 batter or premier bowler
    icc_rank_bat    INTEGER,
    icc_rank_bowl   INTEGER,
    last_updated    TEXT DEFAULT (datetime('now'))
);

-- ── 2. PLAYER MATCH STATS — one row per player per match ─────
CREATE TABLE IF NOT EXISTS player_match_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT NOT NULL,
    match_id        TEXT NOT NULL,
    match_date      TEXT NOT NULL,
    team            TEXT NOT NULL,
    opponent        TEXT NOT NULL,
    venue_id        TEXT,
    format          TEXT NOT NULL,          -- ODI/T20I/T20/Test
    innings         INTEGER,                -- 1 or 2
    -- batting
    runs_scored     INTEGER,
    balls_faced     INTEGER,
    fours           INTEGER DEFAULT 0,
    sixes           INTEGER DEFAULT 0,
    dots_faced      INTEGER DEFAULT 0,
    strike_rate     REAL,
    dot_pct         REAL,                   -- dots / balls faced
    boundary_pct    REAL,                   -- (4s+6s) / balls faced
    dismissal_type  TEXT,                   -- bowled/caught/lbw/run_out/not_out/dnb
    dismissed_by    TEXT,                   -- bowler name
    -- bowling
    overs_bowled    REAL,
    wickets         INTEGER DEFAULT 0,
    runs_conceded   INTEGER,
    economy         REAL,
    dot_balls_bowled INTEGER DEFAULT 0,
    extras_bowled   INTEGER DEFAULT 0,
    -- fielding
    catches         INTEGER DEFAULT 0,
    run_outs        INTEGER DEFAULT 0,
    -- metadata
    source          TEXT DEFAULT 'manual',  -- manual/cricsheet/scraped
    UNIQUE(player_id, match_id, innings)
);

-- ── 3. PLAYER VENUE STATS — career record at each ground ─────
CREATE TABLE IF NOT EXISTS player_venue_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT NOT NULL,
    venue_id        TEXT NOT NULL,
    format          TEXT NOT NULL,
    -- batting
    innings         INTEGER DEFAULT 0,
    runs_total      INTEGER DEFAULT 0,
    balls_total     INTEGER DEFAULT 0,
    highest_score   INTEGER,
    fifties         INTEGER DEFAULT 0,
    hundreds        INTEGER DEFAULT 0,
    not_outs        INTEGER DEFAULT 0,
    avg_score       REAL,                   -- runs / (innings - not_outs)
    avg_sr          REAL,
    avg_dot_pct     REAL,
    avg_boundary_pct REAL,
    avg_last_3      REAL,                   -- average in last 3 innings here
    -- bowling
    bowl_innings    INTEGER DEFAULT 0,
    bowl_wickets    INTEGER DEFAULT 0,
    bowl_runs       INTEGER DEFAULT 0,
    bowl_economy    REAL,
    -- last visit
    last_played_here TEXT,
    last_score_here INTEGER,
    last_updated    TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, venue_id, format)
);

-- ── 4. PLAYER VS PLAYER — batter vs bowler matchup ───────────
CREATE TABLE IF NOT EXISTS player_vs_player (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batter_id       TEXT NOT NULL,
    bowler_id       TEXT NOT NULL,
    format          TEXT NOT NULL,
    -- stats
    balls           INTEGER DEFAULT 0,      -- balls bowler has bowled to this batter
    runs            INTEGER DEFAULT 0,
    dots            INTEGER DEFAULT 0,
    fours           INTEGER DEFAULT 0,
    sixes           INTEGER DEFAULT 0,
    dismissals      INTEGER DEFAULT 0,
    -- computed
    strike_rate     REAL,
    dot_pct         REAL,
    dismissal_rate  REAL,                   -- dismissals per ball
    batter_advantage REAL,                  -- SR vs career SR (positive = batter wins)
    -- recent
    last_5_results  TEXT,                   -- e.g. "12,0,45,W,8" (runs or W)
    last_meeting_date TEXT,
    -- edge signal
    bowler_dominates INTEGER DEFAULT 0,     -- 1 if bowler has clear edge
    batter_dominates INTEGER DEFAULT 0,
    last_updated    TEXT DEFAULT (datetime('now')),
    UNIQUE(batter_id, bowler_id, format)
);

-- ── 5. PLAYER FORM — rolling recent form ─────────────────────
CREATE TABLE IF NOT EXISTS player_form (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT NOT NULL,
    format          TEXT NOT NULL,
    as_of_date      TEXT NOT NULL,
    -- batting form
    last_5_scores   TEXT,                   -- "45,12,87,0,33"
    last_5_avg      REAL,
    last_5_sr       REAL,
    last_10_avg     REAL,
    last_10_sr      REAL,
    -- bowling form
    last_5_wickets  TEXT,                   -- "2,0,3,1,2"
    last_5_economy  REAL,
    last_10_economy REAL,
    -- computed signal
    form_score      REAL,                   -- 0-10
    trend           TEXT,                   -- up/flat/down
    peak_recent     INTEGER DEFAULT 0,      -- 1 if best form in last 2 years
    last_updated    TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, format, as_of_date)
);

-- ── 6. PLAYING XI — confirmed team per match ─────────────────
CREATE TABLE IF NOT EXISTS playing_xi (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT NOT NULL,
    match_date      TEXT,
    team            TEXT NOT NULL,
    player_id       TEXT NOT NULL,
    player_name     TEXT,
    batting_position INTEGER,
    is_available    INTEGER DEFAULT 1,      -- 0 = injured/rested/not selected
    is_captain      INTEGER DEFAULT 0,
    is_keeper       INTEGER DEFAULT 0,
    injury_note     TEXT,
    source          TEXT DEFAULT 'manual',
    entered_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(match_id, team, player_id)
);

-- ── 7. PLAYER SIGNAL OUTPUT — cached per match ───────────────
CREATE TABLE IF NOT EXISTS player_signal (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT NOT NULL,
    computed_at     TEXT,
    team_a          TEXT NOT NULL,
    team_b          TEXT NOT NULL,
    format          TEXT NOT NULL,
    venue_id        TEXT,
    -- per-team scores
    team_a_batting_score  REAL,            -- 0-10 batting strength
    team_a_bowling_score  REAL,            -- 0-10 bowling strength
    team_a_venue_score    REAL,            -- 0-10 key players' venue record
    team_a_form_score     REAL,            -- 0-10 recent form
    team_a_matchup_score  REAL,            -- 0-10 head-to-head player matchups
    team_a_availability   REAL,            -- 0-10 squad availability
    team_a_overall        REAL,            -- 0-10 combined signal
    team_b_batting_score  REAL,
    team_b_bowling_score  REAL,
    team_b_venue_score    REAL,
    team_b_form_score     REAL,
    team_b_matchup_score  REAL,
    team_b_availability   REAL,
    team_b_overall        REAL,
    -- final output for decision engine
    signal_factor         REAL,            -- 0-10 for team_a advantage
    signal_ev_adj         REAL,            -- EV adjustment % based on player edge
    key_insights          TEXT,            -- JSON list of insight strings
    UNIQUE(match_id, computed_at)
);

-- ── INDEXES ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pms_player   ON player_match_stats(player_id, format);
CREATE INDEX IF NOT EXISTS idx_pms_match    ON player_match_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_pvs_player   ON player_venue_stats(player_id, venue_id);
CREATE INDEX IF NOT EXISTS idx_pvp_matchup  ON player_vs_player(batter_id, bowler_id);
CREATE INDEX IF NOT EXISTS idx_pf_player    ON player_form(player_id, format);
CREATE INDEX IF NOT EXISTS idx_xi_match     ON playing_xi(match_id, team);
CREATE INDEX IF NOT EXISTS idx_sig_match    ON player_signal(match_id);
