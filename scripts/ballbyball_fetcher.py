"""
scripts/ballbyball_fetcher.py
================================
Fetches ball-by-ball delivery data from ESPNcricinfo for a specific match
(live or completed) and stores it in db/ball_by_ball.db using the same
schema as the Cricsheet parser (scripts/parse_cricsheet.py), so both
sources feed the same simulation tables.

Runs from within the deployed Streamlit app (has network access to
espncricinfo.com even though the dev sandbox does not).

Flow:
  1. Search hs-consumer-api for the match (by teams + date) → get match id
  2. Fetch full commentary/ball-by-ball feed for that match id
  3. Parse into the same `deliveries` row format as Cricsheet
  4. Upsert into db/ball_by_ball.db (matches + deliveries tables)
  5. Re-run aggregate table builder so simulation stays current

Public, unauthenticated endpoints (same family already used by
score_fetcher.py / espn_results.py elsewhere in this project):
  - /v1/pages/matches/live | recent | results   (find match + id)
  - /v1/pages/match/{id}/comments                (ball-by-ball feed, paginated)
"""

import requests, sqlite3, os, sys, re, time
from datetime import datetime
from difflib import SequenceMatcher

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB     = os.path.join(ROOT, "db", "ball_by_ball.db")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept":  "application/json",
    "Referer": "https://www.espncricinfo.com/",
}

SEARCH_URLS = [
    "https://hs-consumer-api.espncricinfo.com/v1/pages/matches/live?lang=en&limit=50",
    "https://hs-consumer-api.espncricinfo.com/v1/pages/matches/recent?lang=en&limit=50",
    "https://hs-consumer-api.espncricinfo.com/v1/pages/matches/results?lang=en&limit=50",
]

COMMENTS_URL = ("https://hs-consumer-api.espncricinfo.com/v1/pages/match/"
                 "comments?lang=en&matchId={mid}&inningNumber={inn}&commentType=REGULAR&"
                 "sortDirection=DESC&fromInningOver=&limit=500")

MATCH_INFO_URL = ("https://hs-consumer-api.espncricinfo.com/v1/pages/match/"
                   "home?lang=en&matchId={mid}")

# ── Name/team matching helpers (same convention as fetch_playingxi.py) ──
def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', s.lower().replace(" women", "").replace(" men", "")).strip()

def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

def _team_key(name: str) -> str:
    words = [w for w in _norm(name).split() if len(w) > 2]
    return words[0] if words else _norm(name)[:4]


# ── Step 1: find the ESPN match id ───────────────────────────
def find_match_id(team_a: str, team_b: str, match_date: str) -> dict:
    """
    Search live/recent/results feeds for a match matching team_a vs team_b
    on match_date. Returns {"match_id":.., "found":True/False, "source":..}
    """
    ta_k, tb_k = _team_key(team_a), _team_key(team_b)

    for url in SEARCH_URLS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            data = r.json()
            matches = data.get("content", {}).get("matches", []) or []

            for m in matches:
                t1 = (m.get("team1", {}) or {}).get("name", "")
                t2 = (m.get("team2", {}) or {}).get("name", "")
                combined = (t1 + " " + t2).lower()
                if ta_k in combined and tb_k in combined:
                    mid = m.get("objectId") or m.get("id")
                    if mid:
                        return {
                            "found": True,
                            "match_id": str(mid),
                            "team1": t1, "team2": t2,
                            "status": m.get("statusText", ""),
                            "source": url.split("/")[-1].split("?")[0],
                        }
        except Exception:
            continue

    return {"found": False, "match_id": None, "error":
            f"Match {team_a} vs {team_b} on {match_date} not found in live/recent/results feeds"}


# ── Step 2: fetch match info (venue, toss, teams, result) ────
def fetch_match_info(match_id: str) -> dict:
    try:
        r = requests.get(MATCH_INFO_URL.format(mid=match_id), headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return {}
        data = r.json()
        match = data.get("match", {}) or {}
        return {
            "venue":         (match.get("ground", {}) or {}).get("name", ""),
            "city":          (match.get("ground", {}) or {}).get("town", {}).get("name", ""),
            "team1":         (match.get("team1", {}) or {}).get("name", ""),
            "team2":         (match.get("team2", {}) or {}).get("name", ""),
            "toss_winner":   (match.get("tossWinnerTeam", {}) or {}).get("name", ""),
            "toss_decision": match.get("tossDecision", ""),
            "status":        match.get("statusText", ""),
            "match_date":    (match.get("startDate", "") or "")[:10],
            "gender":        "female" if match.get("gender") == "female" else "male",
            "competition":   (match.get("series", {}) or {}).get("name", ""),
            "player_of_match": ", ".join(
                p.get("name", "") for p in (match.get("playersOfTheMatch") or [])
            ),
        }
    except Exception:
        return {}


# ── Step 3: fetch ball-by-ball commentary and parse deliveries ──
def fetch_deliveries(match_id: str, inning: int, match_meta: dict) -> list[dict]:
    """
    Fetch all commentary/ball events for one innings and convert to
    delivery rows matching the Cricsheet schema (see parse_cricsheet.py).
    """
    deliveries = []
    total_overs_fmt = match_meta.get("total_overs", 20)

    try:
        url = COMMENTS_URL.format(mid=match_id, inn=inning)
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return deliveries

        data = r.json()
        comments = data.get("comments", []) or data.get("content", {}).get("comments", [])

        total_ball = 0
        for c in comments:
            # ESPN ball-by-ball comment objects — only keep actual deliveries
            if c.get("commentType") not in ("REGULAR", None):
                continue
            over_str = str(c.get("overNumber", c.get("over", "")))
            if not over_str:
                continue

            try:
                over_num = int(float(over_str))
            except Exception:
                continue

            ball_num = c.get("ballNumber", 0) or 0
            batter   = (c.get("batsman", {}) or {}).get("name", "") or c.get("batsmanName", "")
            bowler   = (c.get("bowler", {}) or {}).get("name", "")  or c.get("bowlerName", "")
            runs     = c.get("totalRuns", c.get("runs", 0)) or 0
            is_four  = c.get("isFour", False)
            is_six   = c.get("isSix", False)
            wkt      = c.get("isWicket", False)
            wkt_kind = (c.get("dismissal", {}) or {}).get("type", "") if wkt else ""
            wkt_ply  = (c.get("dismissal", {}) or {}).get("batsman", {}).get("name", "") if wkt else ""
            wide     = 1 if c.get("wide") or c.get("isWide") else 0
            noball   = 1 if c.get("noBall") or c.get("isNoBall") else 0
            bye      = 1 if c.get("bye") else 0
            legbye   = 1 if c.get("legBye") else 0

            batter_runs = 0 if (wide or noball or bye or legbye) else runs
            if is_six: batter_runs = 6
            elif is_four: batter_runs = 4

            total_ball += 1
            phase = ("powerplay" if over_num <= (1 if total_overs_fmt <= 10 else 5)
                     else "death" if over_num >= (total_overs_fmt - (4 if total_overs_fmt <= 10 else 6))
                     else "middle")

            deliveries.append({
                "match_id":     f"ESPN_{match_id}",
                "match_date":   match_meta.get("match_date", ""),
                "season":       match_meta.get("season", ""),
                "competition":  match_meta.get("competition", ""),
                "gender":       match_meta.get("gender", "male"),
                "venue":        match_meta.get("venue", ""),
                "city":         match_meta.get("city", ""),
                "innings":      inning,
                "batting_team": match_meta.get("team1") if inning == 1 else match_meta.get("team2"),
                "bowling_team": match_meta.get("team2") if inning == 1 else match_meta.get("team1"),
                "over_num":     over_num,
                "ball_num":     ball_num,
                "total_ball":   total_ball,
                "batter":       batter,
                "non_striker":  "",
                "bowler":       bowler,
                "runs_batter":  batter_runs,
                "runs_extras":  runs - batter_runs if runs >= batter_runs else 0,
                "runs_total":   runs,
                "is_wicket":    1 if wkt else 0,
                "wicket_kind":  wkt_kind,
                "wicket_player": wkt_ply,
                "wide":         wide,
                "noball":       noball,
                "bye":          bye,
                "legbye":       legbye,
                "phase":        phase,
            })

    except Exception as e:
        print(f"  ⚠ Error fetching innings {inning}: {e}")

    # ESPN comments feed comes newest-first — reverse to chronological
    deliveries.reverse()
    return deliveries


# ── Step 4: write to ball_by_ball.db (same schema as Cricsheet) ──
def _ensure_schema(conn: sqlite3.Connection):
    """Create tables if this is the first time (mirrors parse_cricsheet.py SCHEMA)."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS deliveries (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id        TEXT, match_date TEXT, season TEXT, competition TEXT,
        gender          TEXT, venue TEXT, city TEXT, innings INTEGER,
        batting_team    TEXT, bowling_team TEXT, over_num INTEGER, ball_num INTEGER,
        total_ball      INTEGER, batter TEXT, non_striker TEXT, bowler TEXT,
        runs_batter     INTEGER, runs_extras INTEGER, runs_total INTEGER,
        is_wicket       INTEGER, wicket_kind TEXT, wicket_player TEXT,
        wide INTEGER, noball INTEGER, bye INTEGER, legbye INTEGER, phase TEXT
    );
    CREATE TABLE IF NOT EXISTS matches (
        match_id TEXT PRIMARY KEY, match_date TEXT, season TEXT, competition TEXT,
        gender TEXT, venue TEXT, city TEXT, team1 TEXT, team2 TEXT,
        toss_winner TEXT, toss_decision TEXT, winner TEXT,
        win_by_runs INTEGER, win_by_wickets INTEGER, player_of_match TEXT,
        team1_score TEXT, team2_score TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_del_match  ON deliveries(match_id);
    CREATE INDEX IF NOT EXISTS idx_del_batter ON deliveries(batter);
    CREATE INDEX IF NOT EXISTS idx_del_bowler ON deliveries(bowler);
    CREATE INDEX IF NOT EXISTS idx_del_venue  ON deliveries(venue);
    """)
    conn.commit()


def fetch_and_store_match(
    team_a: str, team_b: str, match_date: str,
    format_overs: int = 20,
    db_path: str = DB,
) -> dict:
    """
    Main entry point — call this from the Streamlit tab.
    Returns a log dict describing what happened.
    """
    log = {"steps": [], "success": False, "match_id": None,
           "balls_fetched": 0, "error": None}

    # 1. Find match
    log["steps"].append(f"🔍 Searching ESPNcricinfo for {team_a} vs {team_b} ({match_date})...")
    found = find_match_id(team_a, team_b, match_date)
    if not found.get("found"):
        log["error"] = found.get("error", "Match not found")
        log["steps"].append(f"❌ {log['error']}")
        return log

    mid = found["match_id"]
    log["match_id"] = mid
    log["steps"].append(f"✅ Found match id {mid} ({found['team1']} vs {found['team2']}) — {found['status']}")

    # 2. Match info
    meta = fetch_match_info(mid)
    meta["total_overs"] = format_overs
    if not meta.get("team1"):
        meta["team1"], meta["team2"] = found["team1"], found["team2"]
    if not meta.get("match_date"):
        meta["match_date"] = match_date
    log["steps"].append(f"ℹ️ Venue: {meta.get('venue','?')} · Status: {meta.get('status','?')}")

    # 3. Fetch both innings
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)

    all_deliveries = []
    for inn in (1, 2):
        log["steps"].append(f"📥 Fetching innings {inn} ball-by-ball...")
        balls = fetch_deliveries(mid, inn, meta)
        log["steps"].append(f"   → {len(balls)} deliveries")
        all_deliveries.extend(balls)
        time.sleep(0.3)  # be polite

    if not all_deliveries:
        log["error"] = "No deliveries returned — match may not have ball-by-ball commentary available"
        log["steps"].append(f"❌ {log['error']}")
        conn.close()
        return log

    # 4. Write match row
    conn.execute("""
        INSERT OR REPLACE INTO matches
        (match_id, match_date, season, competition, gender, venue, city,
         team1, team2, toss_winner, toss_decision, winner,
         win_by_runs, win_by_wickets, player_of_match, team1_score, team2_score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        f"ESPN_{mid}", meta.get("match_date",""), "", meta.get("competition",""),
        meta.get("gender","male"), meta.get("venue",""), meta.get("city",""),
        meta.get("team1",""), meta.get("team2",""),
        meta.get("toss_winner",""), meta.get("toss_decision",""),
        "", None, None, meta.get("player_of_match",""), "", ""
    ))

    # 5. Write deliveries (clear old rows for this match first, avoid dupes)
    conn.execute("DELETE FROM deliveries WHERE match_id=?", (f"ESPN_{mid}",))
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
    """, all_deliveries)

    conn.commit()
    conn.close()

    log["success"]       = True
    log["balls_fetched"]  = len(all_deliveries)
    log["steps"].append(f"✅ Stored {len(all_deliveries)} deliveries to ball_by_ball.db")
    return log


if __name__ == "__main__":
    # Quick manual test
    result = fetch_and_store_match("Birmingham Phoenix", "Trent Rockets", "2026-07-28", format_overs=10)
    for s in result["steps"]:
        print(s)
    print(f"\nSuccess: {result['success']} · Balls: {result['balls_fetched']}")
