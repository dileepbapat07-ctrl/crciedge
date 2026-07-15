-- ============================================================
-- ELO Engine Schema — additions to cricket_engine.db
-- ============================================================

-- ── ELO RATINGS TABLE ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS elo_ratings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         TEXT NOT NULL,          -- e.g. "India", "Melbourne Stars"
    team_type       TEXT NOT NULL,          -- international / franchise
    gender          TEXT NOT NULL,          -- male / female
    format          TEXT NOT NULL,          -- Test / ODI / T20I / T20
    rating          REAL DEFAULT 1500.0,
    matches_played  INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    peak_rating     REAL DEFAULT 1500.0,
    peak_date       TEXT,
    last_match_date TEXT,
    last_opponent   TEXT,
    last_result     TEXT,                   -- win / loss / nr
    last_updated    TEXT DEFAULT (datetime('now')),
    UNIQUE(team_id, gender, format)
);

-- ── ELO HISTORY (every update logged) ────────────────────────
CREATE TABLE IF NOT EXISTS elo_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_date      TEXT NOT NULL,
    team_id         TEXT NOT NULL,
    gender          TEXT NOT NULL,
    format          TEXT NOT NULL,
    opponent        TEXT NOT NULL,
    venue_country   TEXT,
    home_away       TEXT,                   -- home / away / neutral
    rating_before   REAL,
    rating_after    REAL,
    rating_change   REAL,
    result          TEXT,                   -- win / loss / nr
    k_factor        REAL,
    expected_score  REAL,
    match_type      TEXT                    -- bilateral / icc_event / domestic
);

-- ── H2H COMPREHENSIVE (generated from ELO history) ───────────
CREATE TABLE IF NOT EXISTS h2h_full (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_a          TEXT NOT NULL,
    team_b          TEXT NOT NULL,
    gender          TEXT NOT NULL,
    format          TEXT NOT NULL,
    -- overall
    matches_played  INTEGER DEFAULT 0,
    team_a_wins     INTEGER DEFAULT 0,
    team_b_wins     INTEGER DEFAULT 0,
    no_results      INTEGER DEFAULT 0,
    team_a_win_pct  REAL,
    -- recent (2020 onwards)
    recent_played   INTEGER DEFAULT 0,
    recent_a_wins   INTEGER DEFAULT 0,
    recent_b_wins   INTEGER DEFAULT 0,
    recent_a_pct    REAL,
    -- last 5
    last_5_results  TEXT,                   -- e.g. "A,B,A,A,B"
    last_5_a_wins   INTEGER DEFAULT 0,
    -- streaks
    current_winner  TEXT,
    current_streak  INTEGER DEFAULT 0,
    -- metadata
    last_match_date TEXT,
    last_match_winner TEXT,
    last_updated    TEXT DEFAULT (datetime('now')),
    UNIQUE(team_a, team_b, gender, format)
);

-- ── ELO MATCH LOG (raw processed matches) ────────────────────
CREATE TABLE IF NOT EXISTS elo_match_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_date      TEXT NOT NULL,
    team_a          TEXT NOT NULL,
    team_b          TEXT NOT NULL,
    winner          TEXT,                   -- team name or "no_result"
    gender          TEXT NOT NULL,
    format          TEXT NOT NULL,
    venue_country   TEXT,
    match_type      TEXT,                   -- bilateral/icc_event/domestic
    series          TEXT,
    elo_a_before    REAL,
    elo_b_before    REAL,
    elo_a_after     REAL,
    elo_b_after     REAL,
    k_factor        REAL,
    source          TEXT DEFAULT 'cricsheet'
);

CREATE INDEX IF NOT EXISTS idx_elo_ratings_team   ON elo_ratings(team_id, format);
CREATE INDEX IF NOT EXISTS idx_elo_history_team   ON elo_history(team_id, format);
CREATE INDEX IF NOT EXISTS idx_h2h_full_teams     ON h2h_full(team_a, team_b, format);
CREATE INDEX IF NOT EXISTS idx_elo_match_log_date ON elo_match_log(match_date);
