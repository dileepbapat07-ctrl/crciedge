"""
scripts/espn_common.py
========================
Shared ESPNcricinfo hs-consumer-api helpers, using the CONFIRMED-WORKING
endpoint structure verified from matryer/xbar-plugins/Sports/live_cricket.2m.py
(an actively maintained, real-world working integration).

Key corrections vs earlier (broken) assumptions in this project:
  1. Match list endpoint is /v1/pages/matches/current?lang=en&latest=true
     — NOT /matches/live, /matches/recent, or /matches/results (those
     paths don't exist / are unreliable on hs-consumer-api).
  2. The matches list is top-level `data["matches"]` — NOT nested under
     `data["content"]["matches"]` as previously assumed.
  3. Each match's teams are in a `match["teams"]` LIST of
     `{"team": {"id":.., "name":..}}` objects — NOT `match["team1"]` /
     `match["team2"]` singular fields.
  4. Full match detail (score, toss, innings) needs a SEPARATE call:
     /v1/pages/match/home?lang=en&seriesId={sid}&matchId={mid}
     using seriesId = match["series"]["objectId"], matchId = match["objectId"]
"""

import requests
from difflib import SequenceMatcher
import re

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Referer": "https://www.espncricinfo.com/",
}

CURRENT_MATCHES_URL = "https://hs-consumer-api.espncricinfo.com/v1/pages/matches/current?lang=en&latest=true"
MATCH_HOME_URL       = "https://hs-consumer-api.espncricinfo.com/v1/pages/match/home?lang=en&seriesId={sid}&matchId={mid}"


def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or "").lower().replace(" women", "").replace(" men", "")).strip()


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _team_key(name: str) -> str:
    words = [w for w in _norm(name).split() if len(w) > 2]
    return words[0] if words else _norm(name)[:4]


def get_match_teams(match: dict) -> tuple[str, str]:
    """
    Extract (team1_name, team2_name) from a match object.
    Handles the confirmed `match["teams"]` list-of-dicts structure.
    """
    teams_list = match.get("teams", [])
    names = []
    for t in teams_list:
        team_obj = t.get("team", {}) if isinstance(t, dict) else {}
        name = team_obj.get("name", "")
        if name:
            names.append(name)
    while len(names) < 2:
        names.append("")
    return names[0], names[1]


def fetch_current_matches() -> list[dict]:
    """
    Fetch the current matches list from the confirmed-working endpoint.
    Returns the raw list of match objects (empty list on failure).
    """
    try:
        r = requests.get(CURRENT_MATCHES_URL, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("matches", []) or []
    except Exception:
        return []


def find_match(team_a: str, team_b: str) -> dict | None:
    """
    Search the current matches list for one matching team_a vs team_b.
    Returns the raw match object (with objectId, series.objectId etc)
    or None if not found.
    """
    ta_k, tb_k = _team_key(team_a), _team_key(team_b)
    matches = fetch_current_matches()

    for m in matches:
        t1, t2 = get_match_teams(m)
        combined = (t1 + " " + t2).lower()
        if ta_k in combined and tb_k in combined:
            return m
    return None


def fetch_match_detail(match_obj: dict) -> dict:
    """
    Given a match object from the current-matches list, fetch full detail
    (score, toss, innings) via the match/home endpoint.
    Returns {} on failure.
    """
    mid = match_obj.get("objectId")
    sid = (match_obj.get("series", {}) or {}).get("objectId")
    if not mid or not sid:
        return {}

    try:
        r = requests.get(
            MATCH_HOME_URL.format(sid=sid, mid=mid),
            headers=HEADERS, timeout=8
        )
        if r.status_code != 200:
            return {}
        data = r.json()
        return data.get("match", {}) or {}
    except Exception:
        return {}


def diagnose() -> dict:
    """
    Quick diagnostic — ping the current-matches endpoint and report
    exactly what comes back, for debugging from the Streamlit UI.
    """
    result = {"url": CURRENT_MATCHES_URL, "status": None, "n_matches": None,
               "sample_teams": [], "error": None, "top_level_keys": None}
    try:
        r = requests.get(CURRENT_MATCHES_URL, headers=HEADERS, timeout=8)
        result["status"] = r.status_code
        if r.status_code == 200:
            data = r.json()
            result["top_level_keys"] = list(data.keys())
            matches = data.get("matches", [])
            result["n_matches"] = len(matches)
            for m in matches[:8]:
                t1, t2 = get_match_teams(m)
                result["sample_teams"].append(f"{t1} vs {t2}")
        else:
            result["error"] = f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        result["error"] = str(e)
    return result


if __name__ == "__main__":
    import json
    print("Testing current matches fetch...")
    d = diagnose()
    print(json.dumps(d, indent=2))
