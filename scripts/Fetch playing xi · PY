"""
scripts/fetch_playing_xi.py
============================
Fetches confirmed playing XI from ESPNcricinfo after toss.
Called from Streamlit UI — no terminal needed.

4 strategies in order:
  1. ESPNcricinfo JSON embedded in page
  2. ESPNcricinfo HTML scrape
  3. Google search for XI text
  4. Parse from manually pasted text
"""

import sqlite3, os, sys, re, time, json
from datetime import datetime
from difflib import SequenceMatcher

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError("pip install requests beautifulsoup4")

ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRICKET_DB = os.path.join(ROOT, "db", "cricket_engine.db")
PLAYER_DB  = os.path.join(ROOT, "db", "player_engine.db")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.5",
}

KNOWN_TEAMS = [
    "India","England","Australia","Pakistan","West Indies",
    "New Zealand","South Africa","Sri Lanka","Bangladesh",
    "Afghanistan","Zimbabwe","Ireland",
]

# ── Fuzzy name match ──────────────────────────────────────────
def fuzzy_match(scraped: str, known_players: list) -> dict | None:
    clean = re.sub(r'\([cwk]+\)|†|\*', '', scraped, flags=re.I).strip().lower()
    best_score, best = 0, None
    for p in known_players:
        for cand in [p.get("name",""), p.get("short_name",""),
                     (p.get("name","") or "").split()[-1]]:
            if not cand: continue
            s = SequenceMatcher(None, clean, cand.lower()).ratio()
            if clean == cand.lower().split()[-1]: s = max(s, 0.88)
            if s > best_score:
                best_score, best = s, p
    return best if best_score >= 0.72 else None

# ── Strategy 1: ESPNcricinfo direct scrape ────────────────────
def scrape_espncricinfo(team_a: str, team_b: str, match_date: str) -> dict | None:
    """Search Google for the ESPNcricinfo XI page then scrape it."""
    date_obj = datetime.strptime(match_date, "%Y-%m-%d")
    q = f"{team_a} vs {team_b} playing XI {date_obj.strftime('%B %Y')} espncricinfo"
    search_url = f"https://www.google.com/search?q={requests.utils.quote(q)}&num=5"

    try:
        r = requests.get(search_url, headers=HEADERS, timeout=10)
        # Find espncricinfo match URLs
        urls = re.findall(
            r'https://www\.espncricinfo\.com/series/[^\s"&>]+',
            r.text
        )
        match_urls = [u for u in urls if any(
            x in u for x in ["playing-xi","scorecard","full-scorecard"]
        )]
        if not match_urls and urls:
            # Build XI URL from any match URL
            base = re.sub(r'/[^/]+-\d+$', '', urls[0])
            match_urls = [base + "/match-playing-xi"]
    except Exception as e:
        return None

    for url in match_urls[:2]:
        if "playing-xi" not in url:
            url = re.sub(r'/[^/]+$', '/match-playing-xi', url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            result = _parse_cricinfo_page(soup)
            if result and result.get("players"):
                return result
        except Exception:
            continue
        time.sleep(1)

    return None

def _parse_cricinfo_page(soup) -> dict:
    """Try multiple parse strategies on the ESPNcricinfo page."""
    result = {"players": {}, "captains": {}, "keepers": {}, "toss_winner": None, "toss_choice": None}

    # Strategy A: Embedded JSON state
    for script in soup.find_all("script"):
        text = script.string or ""
        for pattern in [
            r'"playingXI"\s*:\s*(\[.*?\])',
            r'"players"\s*:\s*(\[.*?\])',
            r'"squad"\s*:\s*(\[.*?\])',
        ]:
            m = re.search(pattern, text, re.DOTALL)
            if m:
                try:
                    players = json.loads(m.group(1))
                    for p in players:
                        if isinstance(p, dict):
                            name = p.get("name") or p.get("fullName","")
                            team = p.get("teamName") or p.get("team","")
                            if name and team:
                                result["players"].setdefault(team, []).append(name)
                except Exception:
                    pass
        if result["players"]:
            break

    # Strategy B: HTML player cards
    if not result["players"]:
        page_text = soup.get_text(" ", strip=True)
        result = _parse_xi_text(page_text)

    # Toss
    toss_text = soup.get_text()
    tm = re.search(
        r"([\w\s]+?)\s+won the toss\s+and\s+(?:elected|chose)\s+to\s+(bat|field)",
        toss_text, re.I
    )
    if tm:
        result["toss_winner"] = tm.group(1).strip()
        result["toss_choice"] = tm.group(2).strip()

    return result

# ── Strategy 2: Parse from any text ──────────────────────────
def _parse_xi_text(text: str) -> dict:
    """
    Parse XI from raw text. Handles formats:
      "India: Rohit Sharma, Shubman Gill(c), KL Rahul(wk)..."
      "India Playing XI: 1.Rohit 2.Gill..."
      "India XI - Rohit Sharma, Gill, Kohli..."
    """
    result = {"players": {}, "captains": {}, "keepers": {}}

    for team in KNOWN_TEAMS:
        patterns = [
            # "India: Name, Name, ..."
            rf"{re.escape(team)}\s*(?:Playing\s*XI|XI|squad)?[:\-–]\s*"
            rf"([A-Z][a-zA-Z\s\(\)†]+(?:,\s*[A-Z][a-zA-Z\s\(\)†]+){{6,11}})",
            # "India (Playing XI): ..."
            rf"{re.escape(team)}\s*\([^)]*\)[:\s]*"
            rf"([A-Z][a-zA-Z\s\(\)†]+(?:,\s*[A-Z][a-zA-Z\s\(\)†]+){{6,11}})",
        ]

        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if not m:
                continue

            raw = m.group(1)
            names = []
            for part in re.split(r',|\d+[\.\)]', raw):
                part = part.strip()
                if not part or len(part) < 4:
                    continue
                is_cap = bool(re.search(r'\(c\)', part, re.I))
                is_wk  = bool(re.search(r'\(wk\)|\(w\)|†', part, re.I))
                clean  = re.sub(r'\([cwk]+\)|†|\*', '', part, flags=re.I).strip()
                if len(clean) > 3 and re.match(r'^[A-Z]', clean):
                    names.append(clean)
                    if is_cap: result["captains"][team] = clean
                    if is_wk:  result["keepers"][team]  = clean

            if len(names) >= 8:
                result["players"][team] = names[:11]
                break

    return result

# ── Write XI to DB ────────────────────────────────────────────
def write_xi(match_id: str, match_date: str, xi_data: dict,
             dry_run: bool = False) -> tuple[int, list]:
    """
    Writes XI to playing_xi table.
    Returns (count_inserted, log_lines)
    """
    log = []
    if not xi_data.get("players"):
        return 0, ["No player data parsed"]

    pconn = sqlite3.connect(PLAYER_DB)
    pconn.row_factory = sqlite3.Row
    known = [dict(p) for p in pconn.execute(
        "SELECT player_id, name, short_name, team FROM players"
    ).fetchall()]

    count = 0
    for team, names in xi_data["players"].items():
        log.append(f"**{team}** ({len(names)} players)")
        for raw in names:
            clean = re.sub(r'\([cwk]+\)|†|\*', '', raw, flags=re.I).strip()
            if len(clean) < 3: continue

            is_cap = clean == xi_data.get("captains",{}).get(team,"")
            is_wk  = clean == xi_data.get("keepers", {}).get(team,"")

            matched = fuzzy_match(clean, known)
            if matched:
                pid, pname = matched["player_id"], matched["name"]
                log.append(f"  ✅ {clean} → {pname}")
            else:
                pid   = f"unk-{re.sub(r'[^a-z]','',clean.lower())[:12]}-{team[:3].lower()}"
                pname = clean
                log.append(f"  🆕 {clean} (new player added)")
                if not dry_run:
                    pconn.execute("""
                        INSERT OR IGNORE INTO players
                        (player_id, name, short_name, team, gender)
                        VALUES (?,?,?,?,'male')
                    """, (pid, clean, clean.split()[-1], team))

            if not dry_run:
                pconn.execute("""
                    INSERT OR REPLACE INTO playing_xi
                    (match_id, match_date, team, player_id, player_name,
                     is_available, is_captain, is_keeper, source, entered_at)
                    VALUES (?,?,?,?,?,1,?,?,'auto-scraped',datetime('now'))
                """, (match_id, match_date, team, pid, pname,
                      1 if is_cap else 0, 1 if is_wk else 0))
                count += 1

    if not dry_run:
        pconn.commit()
    pconn.close()
    return count, log

# ── Main entry point called from Streamlit ────────────────────
def fetch_and_store_xi(
    match_id:   str,
    match_date: str,
    team_a:     str,
    team_b:     str,
    xi_text:    str = None,   # manually pasted text
    dry_run:    bool = False,
) -> dict:
    """
    Returns:
    {
      "success": True/False,
      "method": "scraped"/"text"/"failed",
      "toss_winner": "England",
      "toss_choice": "bat",
      "players": {"India": [...], "England": [...]},
      "count": 22,
      "log": ["line1", "line2", ...],
    }
    """
    log = []

    # Method A: parse pasted text (fastest, most reliable)
    if xi_text and len(xi_text) > 20:
        log.append("Parsing from pasted text...")
        xi_data = _parse_xi_text(xi_text)
        if xi_data.get("players"):
            count, write_log = write_xi(match_id, match_date, xi_data, dry_run)
            return {
                "success": True, "method": "text",
                "toss_winner": xi_data.get("toss_winner"),
                "toss_choice": xi_data.get("toss_choice"),
                "players": xi_data["players"],
                "count": count, "log": log + write_log,
            }
        log.append("⚠ Could not parse XI from text — trying web scrape...")

    # Method B: scrape ESPNcricinfo
    log.append(f"Searching ESPNcricinfo for {team_a} vs {team_b}...")
    xi_data = scrape_espncricinfo(team_a, team_b, match_date)
    if xi_data and xi_data.get("players"):
        count, write_log = write_xi(match_id, match_date, xi_data, dry_run)
        return {
            "success": True, "method": "scraped",
            "toss_winner": xi_data.get("toss_winner"),
            "toss_choice": xi_data.get("toss_choice"),
            "players": xi_data["players"],
            "count": count, "log": log + write_log,
        }

    log.append("⚠ Auto-fetch failed. Please paste the XI text below.")
    return {"success": False, "method": "failed", "log": log, "count": 0, "players": {}}
