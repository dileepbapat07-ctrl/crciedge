-- ============================================================
-- Cricket Betting Engine — Offline Database Schema
-- SQLite · cricket_engine.db
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── 1. MATCHES ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matches (
    match_id        TEXT PRIMARY KEY,         -- e.g. "2026-07-14-ENG-IND-ODI-1"
    date            TEXT NOT NULL,             -- ISO 8601 e.g. "2026-07-14"
    step            INTEGER,                   -- bankroll step 1-193
    phase           INTEGER,                   -- 1 or 2
    label           TEXT,                      -- "2nd ODI"
    team_a          TEXT NOT NULL,
    team_b          TEXT NOT NULL,
    format          TEXT NOT NULL,             -- Test/ODI/T20I/T20/100-ball
    series          TEXT,
    category        TEXT,                      -- International/Franchise/Domestic/ACC
    gender          TEXT,                      -- Men's/Women's/Both
    venue_id        TEXT,                      -- FK → venues.venue_id
    city            TEXT,
    country         TEXT,
    status          TEXT DEFAULT 'upcoming',   -- upcoming/completed/abandoned
    result_winner   TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ── 2. VENUES ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS venues (
    venue_id            TEXT PRIMARY KEY,      -- e.g. "edgbaston-birmingham"
    name                TEXT NOT NULL,
    city                TEXT,
    country             TEXT,
    latitude            REAL,
    longitude           REAL,
    capacity            INTEGER,
    surface             TEXT                   -- grass/drop-in/artificial
);

-- ── 3. VENUE STATS (from Cricsheet) ───────────────────────────
CREATE TABLE IF NOT EXISTS venue_stats (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id            TEXT NOT NULL,
    format              TEXT NOT NULL,         -- T20/ODI/Test
    gender              TEXT NOT NULL,         -- male/female
    matches_played      INTEGER DEFAULT 0,
    bat_first_wins      INTEGER DEFAULT 0,
    bat_second_wins     INTEGER DEFAULT 0,
    no_results          INTEGER DEFAULT 0,
    bat_first_win_pct   REAL,                  -- computed
    avg_first_innings   REAL,                  -- average 1st innings total
    avg_second_innings  REAL,
    avg_powerplay_score REAL,                  -- overs 1-6 average
    avg_death_score     REAL,                  -- overs 16-20 average (T20)
    toss_win_bat_pct    REAL,                  -- % toss winners who chose to bat
    toss_advantage_pct  REAL,                  -- % toss winners who won match
    highest_score       INTEGER,
    lowest_score        INTEGER,
    last_updated        TEXT DEFAULT (datetime('now')),
    UNIQUE(venue_id, format, gender)
);

-- ── 4. TEAMS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS teams (
    team_id             TEXT PRIMARY KEY,      -- e.g. "india-men"
    name                TEXT NOT NULL,
    short_name          TEXT,                  -- IND/ENG/AUS
    country             TEXT,
    gender              TEXT,
    icc_rank_test       INTEGER,
    icc_rank_odi        INTEGER,
    icc_rank_t20        INTEGER,
    icc_rating_test     REAL,
    icc_rating_odi      REAL,
    icc_rating_t20      REAL,
    rankings_updated    TEXT
);

-- ── 5. TEAM FORM ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS team_form (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id             TEXT NOT NULL,
    format              TEXT NOT NULL,
    last_5_results      TEXT,                  -- e.g. "W,W,L,W,W"
    last_5_win_pct      REAL,
    last_10_win_pct     REAL,
    avg_score_last_5    REAL,
    avg_conceded_last_5 REAL,
    form_score          REAL,                  -- computed 1-10
    as_of_date          TEXT,
    UNIQUE(team_id, format, as_of_date)
);

-- ── 6. HEAD TO HEAD ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS h2h (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    team_a              TEXT NOT NULL,
    team_b              TEXT NOT NULL,
    format              TEXT NOT NULL,
    gender              TEXT NOT NULL,
    matches_played      INTEGER DEFAULT 0,
    team_a_wins         INTEGER DEFAULT 0,
    team_b_wins         INTEGER DEFAULT 0,
    no_results          INTEGER DEFAULT 0,
    team_a_win_pct      REAL,
    avg_margin_runs     REAL,                  -- when chasing
    avg_margin_wickets  REAL,                  -- when defending
    last_5_team_a_wins  INTEGER,               -- last 5 meetings
    last_match_winner   TEXT,
    last_match_date     TEXT,
    last_updated        TEXT DEFAULT (datetime('now')),
    UNIQUE(team_a, team_b, format, gender)
);

-- ── 7. H2H AT VENUE ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS h2h_venue (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    team_a              TEXT NOT NULL,
    team_b              TEXT NOT NULL,
    venue_id            TEXT NOT NULL,
    format              TEXT NOT NULL,
    matches_played      INTEGER DEFAULT 0,
    team_a_wins         INTEGER DEFAULT 0,
    team_b_wins         INTEGER DEFAULT 0,
    avg_first_innings   REAL,
    UNIQUE(team_a, team_b, venue_id, format)
);

-- ── 8. PLAYER AVAILABILITY ────────────────────────────────────
CREATE TABLE IF NOT EXISTS player_availability (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id            TEXT,
    team_id             TEXT NOT NULL,
    player_name         TEXT NOT NULL,
    role                TEXT,                  -- batsman/bowler/allrounder/keeper
    is_available        INTEGER DEFAULT 1,     -- 1=yes 0=no
    injury_note         TEXT,
    source              TEXT,                  -- cricbuzz-scrape/manual
    updated_at          TEXT DEFAULT (datetime('now'))
);

-- ── 9. WEATHER CACHE ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weather (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id            TEXT NOT NULL,
    match_date          TEXT NOT NULL,
    fetched_at          TEXT,
    rain_prob_pct       REAL,                  -- 0-100
    humidity_pct        REAL,
    wind_kmh            REAL,
    cloud_cover_pct     REAL,
    temp_celsius        REAL,
    condition           TEXT,                  -- clear/cloudy/rain/storm
    dl_risk             TEXT,                  -- low/medium/high
    UNIQUE(venue_id, match_date)
);

-- ── 10. ODDS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS odds (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id            TEXT NOT NULL,
    fetched_at          TEXT,
    bookmaker           TEXT,                  -- betfair/bet365/williamhill
    market              TEXT,                  -- match_winner/totals/handicap
    selection           TEXT,                  -- team_a/team_b/over/under
    decimal_odds        REAL,
    implied_prob        REAL,                  -- 1/odds
    closing_odds        REAL,                  -- filled after match starts
    UNIQUE(match_id, bookmaker, market, selection, fetched_at)
);

-- ── 11. CONFIDENCE SCORES (engine output) ─────────────────────
CREATE TABLE IF NOT EXISTS confidence_scores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id            TEXT NOT NULL,
    computed_at         TEXT DEFAULT (datetime('now')),
    -- individual factor scores
    score_value_edge    REAL,
    score_form          REAL,
    score_h2h           REAL,
    score_venue         REAL,
    score_weather       REAL,
    score_toss          REAL,
    score_players       REAL,
    score_market        REAL,
    score_importance    REAL,
    score_volatility    REAL,
    -- aggregate
    confidence_score    REAL,                  -- 0-100
    ev_pct              REAL,                  -- expected value %
    kelly_pct           REAL,                  -- Kelly fraction
    recommended_stake   REAL,                  -- in EUR
    verdict             TEXT,                  -- BET/REDUCE/SKIP/STOP
    verdict_reason      TEXT,
    UNIQUE(match_id, computed_at)
);

-- ── 12. BET LOG (track every bet placed) ──────────────────────
CREATE TABLE IF NOT EXISTS bet_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id            TEXT NOT NULL,
    bet_date            TEXT NOT NULL,
    step                INTEGER,
    phase               INTEGER,
    bankroll_before     REAL,
    stake               REAL,
    market              TEXT,
    selection           TEXT,
    odds_taken          REAL,
    confidence_score    REAL,
    verdict             TEXT,
    outcome             TEXT,                  -- win/loss/void/pending
    profit_loss         REAL,
    bankroll_after      REAL,
    clv                 REAL,                  -- closing line value
    notes               TEXT,
    placed_at           TEXT DEFAULT (datetime('now'))
);

-- ── 13. BANKROLL TRACKER ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS bankroll (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                TEXT NOT NULL,
    step                INTEGER,
    phase               INTEGER,
    opening_balance     REAL,
    closing_balance     REAL,
    bets_placed         INTEGER DEFAULT 0,
    bets_won            INTEGER DEFAULT 0,
    bets_lost           INTEGER DEFAULT 0,
    daily_pnl           REAL,
    cumulative_pnl      REAL,
    target_balance      REAL,                  -- what compound model says
    variance_from_target REAL
);

-- ── INDEXES ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_matches_date     ON matches(date);
CREATE INDEX IF NOT EXISTS idx_matches_teams    ON matches(team_a, team_b);
CREATE INDEX IF NOT EXISTS idx_venue_stats_vid  ON venue_stats(venue_id, format);
CREATE INDEX IF NOT EXISTS idx_h2h_teams        ON h2h(team_a, team_b, format);
CREATE INDEX IF NOT EXISTS idx_confidence_mid   ON confidence_scores(match_id);
CREATE INDEX IF NOT EXISTS idx_bet_log_date     ON bet_log(bet_date);
CREATE INDEX IF NOT EXISTS idx_odds_mid         ON odds(match_id);
