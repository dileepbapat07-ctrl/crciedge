"""
scripts/parse_cricsheet.py
===========================
Parse Cricsheet JSON zip → ball_by_ball.db

Usage:
  python3 parse_cricsheet.py --zip path/to/hnd_json.zip
  python3 parse_cricsheet.py --zip path/to/hnd_json.zip --dir /path/to/output/

Supports The Hundred (100-ball) and T20 formats.
Each ball stored as one row. Pre-aggregated stats tables built after ingestion.
"""

import sqlite3, json, zipfile, os, sys, argparse, datetime, tempfile

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from pathlib import Path

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_OUT = os.path.join(ROOT, "db", "ball_by_ball.db")

# ── Schema ────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS deliveries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT,
    match_date      TEXT,
    season          TEXT,
    competition     TEXT,
    gender          TEXT,
    venue           TEXT,
    city            TEXT,
    innings         INTEGER,       -- 1 or 2
    batting_team    TEXT,
    bowling_team    TEXT,
    over_num        INTEGER,       -- 0-based (100b: 0-9, T20: 0-19)
    ball_num        INTEGER,       -- within over (0-based)
    total_ball      INTEGER,       -- absolute ball number in innings
    batter          TEXT,
    non_striker     TEXT,
    bowler          TEXT,
    runs_batter     INTEGER,
    runs_extras     INTEGER,
    runs_total      INTEGER,
    is_wicket       INTEGER,       -- 0/1
    wicket_kind     TEXT,          -- bowled/caught/lbw/run out etc
    wicket_player   TEXT,          -- dismissed batter
    wide            INTEGER,
    noball          INTEGER,
    bye             INTEGER,
    legbye          INTEGER,
    phase           TEXT           -- powerplay/middle/death
);

CREATE TABLE IF NOT EXISTS matches (
    match_id        TEXT PRIMARY KEY,
    match_date      TEXT,
    season          TEXT,
    competition     TEXT,
    gender          TEXT,
    venue           TEXT,
    city            TEXT,
    team1           TEXT,
    team2           TEXT,
    toss_winner     TEXT,
    toss_decision   TEXT,
    winner          TEXT,
    win_by_runs     INTEGER,
    win_by_wickets  INTEGER,
    player_of_match TEXT,
    team1_score     TEXT,
    team2_score     TEXT
);

-- Pre-aggregated: batter stats per venue
CREATE TABLE IF NOT EXISTS batter_venue_stats (
    batter          TEXT,
    venue           TEXT,
    competition     TEXT,
    innings         INTEGER,
    balls_faced     INTEGER,
    runs            INTEGER,
    avg             REAL,
    sr              REAL,
    fours           INTEGER,
    sixes           INTEGER,
    dismissals      INTEGER,
    PRIMARY KEY (batter, venue, competition, innings)
);

-- Pre-aggregated: bowler stats per venue
CREATE TABLE IF NOT EXISTS bowler_venue_stats (
    bowler          TEXT,
    venue           TEXT,
    competition     TEXT,
    innings         INTEGER,
    balls_bowled    INTEGER,
    runs_conceded   INTEGER,
    wickets         INTEGER,
    economy         REAL,
    avg             REAL,
    PRIMARY KEY (bowler, venue, competition, innings)
);

-- Pre-aggregated: phase stats per venue
CREATE TABLE IF NOT EXISTS venue_phase_stats (
    venue           TEXT,
    competition     TEXT,
    innings         INTEGER,
    phase           TEXT,
    matches         INTEGER,
    total_balls     INTEGER,
    total_runs      INTEGER,
    total_wickets   INTEGER,
    runs_per_ball   REAL,
    wicket_rate     REAL,
    PRIMARY KEY (venue, competition, innings, phase)
);

CREATE INDEX IF NOT EXISTS idx_del_match  ON deliveries(match_id);
CREATE INDEX IF NOT EXISTS idx_del_batter ON deliveries(batter);
CREATE INDEX IF NOT EXISTS idx_del_bowler ON deliveries(bowler);
CREATE INDEX IF NOT EXISTS idx_del_venue  ON deliveries(venue);
CREATE INDEX IF NOT EXISTS idx_del_phase  ON deliveries(phase);
"""

def get_phase(over: int, total_overs: int) -> str:
    """Return phase label based on over number."""
    if total_overs <= 10:  # 100-ball (10 sets)
        if over <= 1:   return "powerplay"
        if over <= 6:   return "middle"
        return "death"
    else:  # T20 (20 overs)
        if over <= 5:   return "powerplay"
        if over <= 14:  return "middle"
        return "death"

def parse_match(data: dict, competition: str) -> tuple[dict, list]:
    """Parse one Cricsheet JSON match file. Returns (match_row, [delivery_rows])."""
    info = data.get("info", {})
    innings_data = data.get("innings", [])

    match_date = ""
    dates = info.get("dates", [])
    if dates:
        match_date = dates[0] if isinstance(dates[0], str) else str(dates[0])

    season   = str(info.get("season", ""))
    venue    = info.get("venue", "")
    city     = info.get("city", "")
    gender   = info.get("gender", "male")
    teams    = info.get("teams", ["", ""])
    outcome  = info.get("outcome", {})
    toss     = info.get("toss", {})
    potm     = info.get("player_of_match", [])

    # Derive match_id from date + teams
    ta = teams[0].replace(" ", "_")[:8] if teams else "UNK"
    tb = teams[1].replace(" ", "_")[:8] if len(teams) > 1 else "UNK"
    match_id = f"{match_date}_{ta}_{tb}_{competition[:3].upper()}"

    # Determine total overs
    overs_cfg = info.get("overs", 20)
    if "balls_per_over" in info:
        balls_po = info["balls_per_over"]
        total_overs = overs_cfg
    else:
        balls_po = 6
        total_overs = overs_cfg

    # Match row
    winner_info = outcome.get("winner", "")
    by_info     = outcome.get("by", {})
    match_row = {
        "match_id":        match_id,
        "match_date":      match_date,
        "season":          season,
        "competition":     competition,
        "gender":          gender,
        "venue":           venue,
        "city":            city,
        "team1":           teams[0] if teams else "",
        "team2":           teams[1] if len(teams) > 1 else "",
        "toss_winner":     toss.get("winner", ""),
        "toss_decision":   toss.get("decision", ""),
        "winner":          winner_info,
        "win_by_runs":     by_info.get("runs"),
        "win_by_wickets":  by_info.get("wickets"),
        "player_of_match": potm[0] if potm else "",
        "team1_score":     "",
        "team2_score":     "",
    }

    # Delivery rows
    deliveries = []
    for inn_idx, inning in enumerate(innings_data):
        batting_team = inning.get("team", "")
        bowling_team = teams[0] if batting_team == (teams[1] if len(teams) > 1 else "") else (teams[1] if len(teams) > 1 else "")

        total_ball = 0
        for over_obj in inning.get("overs", []):
            over_num = over_obj.get("over", 0)
            phase    = get_phase(over_num, total_overs)

            for ball_idx, delivery in enumerate(over_obj.get("deliveries", [])):
                total_ball += 1
                runs   = delivery.get("runs", {})
                extras = delivery.get("extras", {})
                wkts   = delivery.get("wickets", [])

                is_wicket   = 1 if wkts else 0
                wicket_kind = wkts[0].get("kind", "") if wkts else ""
                wicket_plyr = wkts[0].get("player_out", "") if wkts else ""

                deliveries.append({
                    "match_id":     match_id,
                    "match_date":   match_date,
                    "season":       season,
                    "competition":  competition,
                    "gender":       gender,
                    "venue":        venue,
                    "city":         city,
                    "innings":      inn_idx + 1,
                    "batting_team": batting_team,
                    "bowling_team": bowling_team,
                    "over_num":     over_num,
                    "ball_num":     ball_idx,
                    "total_ball":   total_ball,
                    "batter":       delivery.get("batter", ""),
                    "non_striker":  delivery.get("non_striker", ""),
                    "bowler":       delivery.get("bowler", ""),
                    "runs_batter":  runs.get("batter", 0),
                    "runs_extras":  runs.get("extras", 0),
                    "runs_total":   runs.get("total", 0),
                    "is_wicket":    is_wicket,
                    "wicket_kind":  wicket_kind,
                    "wicket_player": wicket_plyr,
                    "wide":         extras.get("wides", 0),
                    "noball":       extras.get("noballs", 0),
                    "bye":          extras.get("byes", 0),
                    "legbye":       extras.get("legbyes", 0),
                    "phase":        phase,
                })

    return match_row, deliveries


def build_aggregate_tables(conn: sqlite3.Connection):
    """Build pre-aggregated summary tables for fast simulation queries."""
    print("  Building batter_venue_stats...", end=" ", flush=True)
    conn.execute("DELETE FROM batter_venue_stats")
    conn.execute("""
        INSERT INTO batter_venue_stats
        SELECT
            batter, venue, competition, innings,
            COUNT(*) as balls_faced,
            SUM(runs_batter) as runs,
            CASE WHEN SUM(is_wicket) > 0
                 THEN CAST(SUM(runs_batter) AS REAL) / SUM(is_wicket)
                 ELSE SUM(runs_batter) END as avg,
            ROUND(CAST(SUM(runs_batter)*100.0 AS REAL) / COUNT(*), 1) as sr,
            SUM(CASE WHEN runs_batter=4 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN runs_batter=6 THEN 1 ELSE 0 END) as sixes,
            SUM(is_wicket) as dismissals
        FROM deliveries
        WHERE wide=0 AND noball=0
        GROUP BY batter, venue, competition, innings
        HAVING balls_faced >= 10
    """)
    print("✓")

    print("  Building bowler_venue_stats...", end=" ", flush=True)
    conn.execute("DELETE FROM bowler_venue_stats")
    conn.execute("""
        INSERT INTO bowler_venue_stats
        SELECT
            bowler, venue, competition, innings,
            COUNT(*) as balls_bowled,
            SUM(runs_total) as runs_conceded,
            SUM(is_wicket) as wickets,
            ROUND(CAST(SUM(runs_total)*6.0 AS REAL) / COUNT(*), 2) as economy,
            CASE WHEN SUM(is_wicket) > 0
                 THEN CAST(SUM(runs_total) AS REAL) / SUM(is_wicket)
                 ELSE NULL END as avg
        FROM deliveries
        GROUP BY bowler, venue, competition, innings
        HAVING balls_bowled >= 10
    """)
    print("✓")

    print("  Building venue_phase_stats...", end=" ", flush=True)
    conn.execute("DELETE FROM venue_phase_stats")
    conn.execute("""
        INSERT INTO venue_phase_stats
        SELECT
            venue, competition, innings, phase,
            COUNT(DISTINCT match_id) as matches,
            COUNT(*) as total_balls,
            SUM(runs_total) as total_runs,
            SUM(is_wicket) as total_wickets,
            ROUND(CAST(SUM(runs_total) AS REAL) / COUNT(*), 4) as runs_per_ball,
            ROUND(CAST(SUM(is_wicket) AS REAL) / COUNT(*), 4) as wicket_rate
        FROM deliveries
        GROUP BY venue, competition, innings, phase
    """)
    print("✓")
    conn.commit()


def ingest_zip(zip_path: str, competition: str = "The Hundred", db_path: str = DB_OUT):
    """Main ingestion function. Parse zip → SQLite."""
    print(f"\nIngesting: {zip_path}")
    print(f"  Competition: {competition}")
    print(f"  Output DB:   {db_path}")

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()

    match_ins = 0
    ball_ins  = 0
    skipped   = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        json_files = [f for f in zf.namelist() if f.endswith(".json")]
        print(f"  Files in zip: {len(json_files)}")

        for i, fname in enumerate(json_files):
            if i % 20 == 0:
                print(f"  Parsed {i}/{len(json_files)} matches...", end="\r")
            try:
                with zf.open(fname) as f:
                    data = json.load(f)
                match_row, deliveries = parse_match(data, competition)

                # Skip if already in DB
                exists = conn.execute(
                    "SELECT 1 FROM matches WHERE match_id=?",
                    (match_row["match_id"],)
                ).fetchone()
                if exists:
                    skipped += 1
                    continue

                conn.execute("""
                    INSERT OR REPLACE INTO matches VALUES
                    (:match_id,:match_date,:season,:competition,:gender,
                     :venue,:city,:team1,:team2,:toss_winner,:toss_decision,
                     :winner,:win_by_runs,:win_by_wickets,:player_of_match,
                     :team1_score,:team2_score)
                """, match_row)

                conn.executemany("""
                    INSERT INTO deliveries
                    (match_id,match_date,season,competition,gender,venue,city,
                     innings,batting_team,bowling_team,over_num,ball_num,total_ball,
                     batter,non_striker,bowler,runs_batter,runs_extras,runs_total,
                     is_wicket,wicket_kind,wicket_player,wide,noball,bye,legbye,phase)
                    VALUES
                    (:match_id,:match_date,:season,:competition,:gender,:venue,:city,
                     :innings,:batting_team,:bowling_team,:over_num,:ball_num,:total_ball,
                     :batter,:non_striker,:bowler,:runs_batter,:runs_extras,:runs_total,
                     :is_wicket,:wicket_kind,:wicket_player,:wide,:noball,:bye,:legbye,:phase)
                """, deliveries)

                match_ins += 1
                ball_ins  += len(deliveries)

            except Exception as e:
                print(f"\n  ⚠ Error parsing {fname}: {e}")

        conn.commit()

    print(f"\n  ✅ Done!")
    print(f"     Matches inserted : {match_ins}")
    print(f"     Balls inserted   : {ball_ins:,}")
    print(f"     Skipped (dup)    : {skipped}")

    print("\nBuilding aggregate tables...")
    build_aggregate_tables(conn)

    # Summary
    n_m = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    n_b = conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
    n_v = conn.execute("SELECT COUNT(DISTINCT venue) FROM deliveries").fetchone()[0]
    print(f"\nDB summary: {n_m} matches · {n_b:,} balls · {n_v} venues")

    conn.close()
    return match_ins, ball_ins


# ── Known Cricsheet datasets — one-time bulk download ──────────
DATASETS = {
    "hundred":      {"label": "The Hundred (all seasons, 345 matches)",
                      "url": "https://cricsheet.org/downloads/hnd_json.zip",
                      "competition": "The Hundred", "size_mb": 1.3},
    "t20_internationals": {"label": "T20 Internationals — all (5,591 matches)",
                      "url": "https://cricsheet.org/downloads/t20s_json.zip",
                      "competition": "T20I", "size_mb": 22.2},
    "t20_2026":     {"label": "2026 season — all formats incl. in-progress Hundred (1,532 matches)",
                      "url": "https://cricsheet.org/downloads/2026_json.zip",
                      "competition": "2026 Season", "size_mb": None},
    "ipl":          {"label": "Indian Premier League — all (1,243 matches)",
                      "url": "https://cricsheet.org/downloads/ipl_json.zip",
                      "competition": "IPL", "size_mb": 5.2},
    "bbl":          {"label": "Big Bash League — all (662 matches)",
                      "url": "https://cricsheet.org/downloads/bbl_json.zip",
                      "competition": "BBL", "size_mb": 2.7},
    "cpl":          {"label": "Caribbean Premier League — all (407 matches)",
                      "url": "https://cricsheet.org/downloads/cpl_json.zip",
                      "competition": "CPL", "size_mb": 1.7},
}


def download_zip(url: str, dest_path: str, progress_cb=None) -> tuple[bool, str]:
    """
    Download a zip file with streaming (works from the deployed app's
    network context, which may differ from a dev sandbox).
    progress_cb(bytes_downloaded, total_bytes) called periodically if given.
    """
    if not HAS_REQUESTS:
        return False, "requests library not available"

    try:
        with requests.get(url, stream=True, timeout=30,
                           headers={"User-Agent": "Mozilla/5.0 CricketEngine/1.0"}) as r:
            if r.status_code != 200:
                return False, f"HTTP {r.status_code} from {url}"

            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb:
                            progress_cb(downloaded, total)

        if not zipfile.is_zipfile(dest_path):
            return False, (f"Downloaded file is not a valid zip "
                            f"(got {os.path.getsize(dest_path)} bytes — likely blocked/error page)")

        return True, f"Downloaded {os.path.getsize(dest_path):,} bytes"

    except requests.exceptions.Timeout:
        return False, "Download timed out (30s) — network may be blocking cricsheet.org"
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection failed — cricsheet.org may not be reachable from this environment: {e}"
    except Exception as e:
        return False, f"Download error: {e}"


def download_and_ingest(dataset_key: str, db_path: str = DB_OUT, progress_cb=None) -> dict:
    """
    One-call convenience: download a known dataset by key (see DATASETS)
    and ingest it into ball_by_ball.db. Returns a result dict for UI display.
    """
    if dataset_key not in DATASETS:
        return {"success": False, "error": f"Unknown dataset: {dataset_key}"}

    ds = DATASETS[dataset_key]
    result = {"success": False, "dataset": dataset_key, "label": ds["label"],
              "matches": 0, "balls": 0, "error": None}

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        ok, msg = download_zip(ds["url"], tmp_path, progress_cb)
        result["download_msg"] = msg
        if not ok:
            result["error"] = msg
            return result

        match_ins, ball_ins = ingest_zip(tmp_path, competition=ds["competition"], db_path=db_path)
        result["success"] = True
        result["matches"] = match_ins
        result["balls"]   = ball_ins

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Cricsheet JSON zip into ball_by_ball.db")
    parser.add_argument("--zip", required=True, help="Path to Cricsheet JSON zip file")
    parser.add_argument("--competition", default="The Hundred", help="Competition name")
    parser.add_argument("--db", default=DB_OUT, help="Output DB path")
    args = parser.parse_args()

    if not os.path.exists(args.zip):
        print(f"❌ File not found: {args.zip}")
        sys.exit(1)

    ingest_zip(args.zip, args.competition, args.db)
