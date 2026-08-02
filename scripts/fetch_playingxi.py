"""
scripts/fetch_playingxi.py
===========================
Fetches confirmed playing XI from ESPNcricinfo after toss.
Maps scraped names to our central player database using fuzzy matching + aliases.

Called from "Confirm toss & XI" button in Match Dashboard.
No separate auto-fetch button needed.

Flow:
  1. Scrape ESPNcricinfo match page for confirmed XI names
  2. Fuzzy-match each name to players in our DB (using name + aliases)
  3. Write matched players to playing_xi table
  4. Unmatched players written as name-only entries

Matching priority:
  exact match on name → alias match → fuzzy match (≥0.72 similarity)
"""

import sqlite3, os, re, json
from difflib import SequenceMatcher
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_DB   = os.path.join(ROOT, "db", "cricket_engine.db")
PLAYER_DB = os.path.join(ROOT, "db", "player_engine.db")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/html, */*",
}

# ── Name normalisation ────────────────────────────────────────
def norm(name: str) -> str:
    """Lowercase, strip captain/keeper markers, strip excess whitespace."""
    n = name.lower()
    n = re.sub(r'\s*[†\*\(c\)\(wk\)]+', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

def last_name(name: str) -> str:
    parts = norm(name).split()
    return parts[-1] if parts else ""

# ── Player DB lookup ─────────────────────────────────────────
def load_players(team: str) -> list[dict]:
    """
    Load ALL players from DB for name matching.
    team param used only for ranking — players are format/team agnostic.
    One record per player regardless of what competition they play in.
    """
    pconn = sqlite3.connect(PLAYER_DB)
    pconn.row_factory = sqlite3.Row

    rows = pconn.execute("""
        SELECT player_id, name, short_name, team, nationality,
               current_franchise, role, batting_position,
               is_key_player, name_aliases,
               t20_avg, t20_sr, t20_runs, t20_matches
        FROM players
        ORDER BY
            -- Prioritise: same franchise > same nationality > anyone
            CASE WHEN current_franchise=? THEN 0
                 WHEN nationality=? OR team=? THEN 1
                 ELSE 2 END,
            is_key_player DESC,
            COALESCE(t20_matches,0) DESC
    """, (team, team, team)).fetchall()

    pconn.close()
    players = []
    for r in rows:
        p = dict(r)
        candidates = [p["name"], p["short_name"] or ""]
        if p["name_aliases"]:
            candidates += [a.strip() for a in p["name_aliases"].split(",")]
        p["_candidates"] = [c for c in candidates if c]
        players.append(p)
    return players

def match_player(scraped_name: str, players: list[dict]) -> Optional[dict]:
    """
    Match a scraped name to a player in our DB.
    Returns the best match or None if below threshold.
    """
    sn = norm(scraped_name)
    sl = last_name(scraped_name)

    best_score = 0.0
    best_player = None

    for p in players:
        for cand in p["_candidates"]:
            if not cand:
                continue
            # Exact match (after normalisation)
            if norm(cand) == sn:
                return p
            # Last name exact match — high confidence
            if last_name(cand) == sl and sl:
                score = 0.90
            else:
                score = similarity(scraped_name, cand)

            if score > best_score:
                best_score = score
                best_player = p

    if best_score >= 0.72:
        return best_player
    return None

# ── Scrape ESPNcricinfo ───────────────────────────────────────
def _scrape_espn_xi(team_a: str, team_b: str, match_date: str) -> dict:
    """
    Scrape ESPNcricinfo for confirmed playing XI + toss, using the
    confirmed-working endpoint structure (espn_common.py — verified
    against matryer/xbar-plugins live_cricket.2m.py).

    Returns {"team_a_xi": [...names...], "team_b_xi": [...names...],
             "toss_winner": "...", "toss_choice": "bat/field"}
    """
    if not HAS_REQUESTS:
        return {}

    result = {}

    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from espn_common import find_match, fetch_match_detail, get_match_teams, _sim

        match_obj = find_match(team_a, team_b)
        if not match_obj:
            result["_error"] = "Match not found in ESPN current-matches feed"
            return result

        detail = fetch_match_detail(match_obj)
        if not detail:
            result["_error"] = "Found match but could not fetch detail"
            return result

        t1, t2 = get_match_teams(detail) if detail.get("teams") else get_match_teams(match_obj)

        # Playing XI — try common field names on the match detail payload
        for team_data in (detail.get("teams", []) or []):
            team_obj = team_data.get("team", {}) or {}
            tname = team_obj.get("name", "")
            xi_raw = (team_data.get("playingXI") or team_data.get("playing11") or
                      team_data.get("squad") or [])
            xi = [p.get("name", "") for p in xi_raw if isinstance(p, dict) and p.get("name")]
            if xi:
                if _sim(tname, team_a) >= _sim(tname, team_b):
                    result["team_a_xi"] = xi
                else:
                    result["team_b_xi"] = xi

        # Toss info
        toss = detail.get("toss", {}) or {}
        if toss:
            result["toss_winner"] = (toss.get("winnerTeamName", "") or
                                      (toss.get("winner", {}) or {}).get("name", ""))
            result["toss_choice"] = (toss.get("decision", "") or "").lower()

    except Exception as e:
        result["_error"] = str(e)

    return result

def _parse_xi_text(text: str, team_a: str, team_b: str) -> dict:
    """
    Parse playing XI from pasted text.
    Handles formats like:
      "India: Rohit, Gill, Kohli, ..."
      "1. Rohit Sharma 2. Shubman Gill ..."
      Player names separated by commas or newlines
    """
    result = {}
    lines = text.strip().split("\n")

    current_team = None
    xi_a, xi_b = [], []

    ta_k = team_a.lower().replace(" women","").split()[-1]
    tb_k = team_b.lower().replace(" women","").split()[-1]

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Detect team header: "India:" or "India Playing XI:"
        if ":" in line and len(line.split(":")[0]) < 40:
            header = line.split(":")[0].lower()
            names_part = line.split(":",1)[1]
            if ta_k in header:
                current_team = "a"
                names = re.split(r'[,\n]+', names_part)
                xi_a += [n.strip() for n in names if len(n.strip()) > 2]
            elif tb_k in header:
                current_team = "b"
                names = re.split(r'[,\n]+', names_part)
                xi_b += [n.strip() for n in names if len(n.strip()) > 2]
            continue

        # Numbered list: "1. Rohit Sharma"
        m = re.match(r'^(\d+)[.)]\s*(.+)$', line)
        if m:
            name = m.group(2).strip()
            if current_team == "a": xi_a.append(name)
            elif current_team == "b": xi_b.append(name)
            continue

        # Plain name lines
        if current_team == "a" and len(line) > 2:
            xi_a.append(line)
        elif current_team == "b" and len(line) > 2:
            xi_b.append(line)

    # Toss
    toss_m = re.search(
        r'([\w\s]+?)\s+won\s+the\s+toss\s+and\s+elected\s+to\s+(bat|field)',
        text, re.IGNORECASE
    )
    if toss_m:
        result["toss_winner"] = toss_m.group(1).strip()
        result["toss_choice"] = toss_m.group(2).strip().lower()

    if xi_a: result["team_a_xi"] = xi_a
    if xi_b: result["team_b_xi"] = xi_b
    return result

# ── Write to playing_xi table ─────────────────────────────────
def _write_xi(match_id: str, match_date: str,
              team: str, names: list[str], players_db: list[dict]) -> tuple[int, list]:
    """Match names to DB players and write to playing_xi."""
    pconn = sqlite3.connect(PLAYER_DB)
    log = []
    written = 0

    # Clear existing XI for this match+team
    pconn.execute(
        "DELETE FROM playing_xi WHERE match_id=? AND team=?",
        (match_id, team)
    )

    for i, name in enumerate(names):
        name = name.strip()
        if not name or len(name) < 2:
            continue

        player = match_player(name, players_db)

        # Detect captain/keeper from markers
        is_cap = bool(re.search(r'\(c\)|\*', name, re.IGNORECASE))
        is_wk  = bool(re.search(r'\(wk\)|†', name, re.IGNORECASE))

        if player:
            pid = player["player_id"]
            bat_pos = player.get("batting_position") or (i+1)
            log.append(f"✅ {name} → {player['name']} ({pid})")
        else:
            pid = None
            bat_pos = i + 1
            log.append(f"⚠ {name} → no match in DB (written as name-only)")

        pconn.execute("""
            INSERT OR REPLACE INTO playing_xi
            (match_id, match_date, team, player_id, player_name,
             batting_position, is_available, is_captain, is_keeper,
             source, entered_at)
            VALUES (?,?,?,?,?,?,1,?,?,?,datetime('now'))
        """, (match_id, match_date, team, pid, name,
              bat_pos, 1 if is_cap else 0, 1 if is_wk else 0,
              "auto_fetch"))
        written += 1

    pconn.commit()
    pconn.close()
    return written, log

# ── Main entry point ──────────────────────────────────────────
def fetch_and_store_xi(
    match_id:   str,
    match_date: str,
    team_a:     str,
    team_b:     str,
    xi_text:    str = "",
) -> dict:
    """
    Single entry point. Called from "Confirm toss & XI" button.

    1. If xi_text provided → parse it
    2. Else → scrape ESPNcricinfo
    3. Map names to player DB
    4. Write to playing_xi table
    """
    log = []
    result = {"success": False, "count": 0, "players": {},
              "toss_winner": "", "toss_choice": "", "log": log}

    # Get XI names
    xi_data = {}
    if xi_text and len(xi_text.strip()) > 10:
        log.append("📋 Parsing pasted XI text...")
        xi_data = _parse_xi_text(xi_text, team_a, team_b)
        if xi_data.get("team_a_xi") or xi_data.get("team_b_xi"):
            log.append(f"✅ Parsed from text: {len(xi_data.get('team_a_xi',[]))} + {len(xi_data.get('team_b_xi',[]))} players")
        else:
            log.append("⚠ Could not parse text — trying web scrape")
            xi_text = ""  # fall through to scrape

    if not xi_data.get("team_a_xi") and not xi_data.get("team_b_xi"):
        log.append(f"🌐 Fetching XI from ESPNcricinfo: {team_a} vs {team_b}...")
        xi_data = _scrape_espn_xi(team_a, team_b, match_date)
        if xi_data.get("_error"):
            log.append(f"⚠ Scrape error: {xi_data['_error']}")
        if xi_data.get("team_a_xi"):
            log.append(f"✅ Fetched {len(xi_data['team_a_xi'])} players for {team_a}")
        if xi_data.get("team_b_xi"):
            log.append(f"✅ Fetched {len(xi_data['team_b_xi'])} players for {team_b}")

    if not xi_data.get("team_a_xi") and not xi_data.get("team_b_xi"):
        log.append("❌ No XI found — paste XI text in the box above")
        return result

    result["toss_winner"] = xi_data.get("toss_winner", "")
    result["toss_choice"] = xi_data.get("toss_choice", "")

    total = 0
    all_players = {}

    # Match and write team A
    if xi_data.get("team_a_xi"):
        players_a = load_players(team_a)
        n, write_log = _write_xi(match_id, match_date, team_a,
                                  xi_data["team_a_xi"], players_a)
        log += write_log
        total += n
        all_players[team_a] = xi_data["team_a_xi"]

    # Match and write team B
    if xi_data.get("team_b_xi"):
        players_b = load_players(team_b)
        n, write_log = _write_xi(match_id, match_date, team_b,
                                  xi_data["team_b_xi"], players_b)
        log += write_log
        total += n
        all_players[team_b] = xi_data["team_b_xi"]

    result["success"] = total > 0
    result["count"]   = total
    result["players"] = all_players
    result["method"]  = "text" if xi_text else "scraped"

    return result


if __name__ == "__main__":
    # Test
    r = fetch_and_store_xi(
        match_id   = "20260714-IND-ENG-ODI-1STODIM",
        match_date = "2026-07-14",
        team_a     = "India",
        team_b     = "England",
        xi_text    = """India: Rohit Sharma (c), Shubman Gill, Virat Kohli, Shreyas Iyer, KL Rahul (wk), Washington Sundar, Shivam Dube, Axar Patel, Gurnoor Brar, Jasprit Bumrah, Prasidh Krishna
England: Ben Duckett, Phil Salt (wk), Joe Root, Harry Brook (c), Liam Livingstone, Jamie Smith, Chris Woakes, Brydon Carse, Rehan Ahmed, Jofra Archer, Mark Wood"""
    )
    print(f"\nResult: success={r['success']} count={r['count']}")
    for line in r["log"]:
        print(f"  {line}")
