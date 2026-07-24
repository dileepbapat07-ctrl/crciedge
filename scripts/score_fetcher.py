"""
scripts/score_fetcher.py
=========================
Fetches live cricket scores using multiple strategies in order.

Strategy 1: cricketdata.org API (free, 500 req/day, no key needed for basic)
Strategy 2: ESPN Cricinfo JSON endpoint (unofficial but stable)
Strategy 3: Cricbuzz unofficial endpoint
Strategy 4: Parse from any text pasted by user

Returns a structured ScoreResult — same format regardless of source.

USAGE:
    from scripts.score_fetcher import fetch_live_score, ScoreResult
    result = fetch_live_score("India", "England", "2026-07-22", "ODI")
    if result.success:
        print(result.score, result.wickets, result.balls_done)
"""

import re, os, sys, json
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

@dataclass
class ScoreResult:
    success:      bool   = False
    source:       str    = ""         # which strategy worked
    # batting team
    batting_team: str    = ""
    bowling_team: str    = ""
    # score
    score:        int    = 0
    wickets:      int    = 0
    balls_done:   int    = 0          # converted from overs
    overs_str:    str    = ""         # raw "44.2" or "7.3"
    # 2nd innings
    innings:      int    = 1
    target:       Optional[int] = None
    runs_needed:  Optional[int] = None
    # toss
    toss_winner:  str    = ""
    toss_choice:  str    = ""         # bat / field
    # status
    match_status: str    = ""         # "Live", "Complete", "Innings Break"
    result_str:   str    = ""         # "India won by 6 wickets"
    # raw
    raw_text:     str    = ""
    error:        str    = ""

def overs_to_balls(overs_str: str) -> int:
    """Convert '7.3' → 45, '12' → 72"""
    try:
        if "." in str(overs_str):
            parts = str(overs_str).split(".")
            return int(parts[0]) * 6 + int(parts[1])
        return int(float(overs_str)) * 6
    except Exception:
        return 0

def parse_score_from_text(text: str, team_a: str = "", team_b: str = "") -> ScoreResult:
    """
    Parse a score from any freeform text.
    Strict patterns to avoid false positives like "4/5 wickets" or "4/5 run rate".

    Valid cricket score formats:
      "51/3 (7.3 ov)"       — runs/wickets (overs)
      "143/10 (99 balls)"   — all out
      "258 all out (48.2)"  — all out with overs
      "ENG: 125/3"          — team prefix
      "157/4 (95b)"         — 100-ball format balls
    """
    r = ScoreResult()
    r.raw_text = text[:500]

    # ── False positive guard ──────────────────────────────────
    # Skip if the X/Y is followed by "wickets", "run rate", "rr", "wkts" nearby
    def is_false_positive(match_start, text):
        """Check if score match is actually a wicket count or run rate."""
        context_after = text[match_start:match_start+40].lower()
        false_triggers = ["wicket", "wkts", "wkt", "run rate", "/over", " rr ", "for "]
        return any(t in context_after for t in false_triggers)

    # ── Strategy 1: Full score with overs — most reliable ─────
    # "51/3 (7.3 ov)" or "51/3 (44 balls)" or "51/3 (7.3)"
    full_pattern = re.compile(
        r'(\d{1,3})/(\d{1,2})\s*\(\s*(\d{1,3})(?:\.([0-6]))?\s*(ov(?:ers?)?|o|balls?|b)\s*\)',
        re.IGNORECASE
    )
    for m in full_pattern.finditer(text):
        runs    = int(m.group(1))
        wickets = int(m.group(2))
        number  = int(m.group(3))
        fraction= int(m.group(4)) if m.group(4) else 0
        unit    = m.group(5).lower()

        if runs > 700 or wickets > 10:
            continue
        if runs < 1 and number == 0:
            continue
        if is_false_positive(m.end(), text):
            continue

        # Determine if unit is balls or overs
        is_balls = unit.startswith('b') and not unit.startswith('bo')
        if is_balls:
            r.balls_done = number
            r.overs_str  = f"{number//6}.{number%6}"
        else:
            r.overs_str  = f"{number}.{fraction}" if fraction else str(number)
            r.balls_done = number * 6 + fraction

        r.score   = runs
        r.wickets = wickets
        r.success = True
        r.source  = "text_parse"
        break

    # ── Strategy 2: Score without overs — less reliable ───────
    if not r.success:
        # Must have context: team name OR preceded by colon/space-at-start-of-line
        bare_pattern = re.compile(
            r'(?:^|:\s*|(?:' + '|'.join([
                re.escape(t) for t in
                ["India","England","Australia","Pakistan","West Indies","New Zealand",
                 "South Africa","Sri Lanka","Bangladesh","Afghanistan","Zimbabwe",
                 "MI London","Welsh Fire","Southern Brave","Trent Rockets",
                 "Birmingham Phoenix","Manchester Originals","Sunrisers","London Spirit",
                 "Trinbago","Barbados","Guyana","Jamaica","St Kitts","Saint Lucia",
                 "Antigua","Adelaide","Brisbane","Hobart","Melbourne","Perth","Sydney"]
            ]) + r')\s+)(\d{2,3})/(\d{1,2})(?!\s*(?:ov|ball|run|wkt|wkts|wicket|over|rr))',
            re.IGNORECASE | re.MULTILINE
        )
        for m in bare_pattern.finditer(text):
            # Get the last group
            groups = [g for g in m.groups() if g is not None]
            if len(groups) < 2:
                continue
            runs_s, wkts_s = groups[-2], groups[-1]
            try:
                runs    = int(runs_s)
                wickets = int(wkts_s)
            except ValueError:
                continue
            if runs > 700 or wickets > 10 or runs < 5:
                continue
            r.score   = runs
            r.wickets = wickets
            r.success = True
            r.source  = "text_parse"
            break

    # ── Strategy 3: "X all out (overs)" ──────────────────────
    if not r.success:
        ao = re.search(
            r'(\d{2,3})\s+(?:all\s+out|ao|a/o)\s*\(?\s*(\d{1,3})(?:\.([0-6]))?\s*(?:ov(?:ers?)?|o)?\s*\)?',
            text, re.IGNORECASE
        )
        if ao:
            runs  = int(ao.group(1))
            overs = int(ao.group(2))
            balls_extra = int(ao.group(3)) if ao.group(3) else 0
            if runs <= 700:
                r.score      = runs
                r.wickets    = 10
                r.overs_str  = f"{overs}.{balls_extra}" if balls_extra else str(overs)
                r.balls_done = overs * 6 + balls_extra
                r.success    = True
                r.source     = "text_parse"

    if not r.success:
        return r

    # ── Target / runs needed ──────────────────────────────────
    tgt = re.search(
        r'(?:target|chasing|need[s]?|require[s]?)\s*[:\s]*(\d{2,3})',
        text, re.IGNORECASE
    )
    if tgt:
        r.target  = int(tgt.group(1))
        r.innings = 2

    rn = re.search(
        r'need[s]?\s+(\d{1,3})\s+(?:more\s+)?runs?\s+(?:from|in|off)\s+(\d{1,3})\s+balls?',
        text, re.IGNORECASE
    )
    if rn:
        r.runs_needed = int(rn.group(1))
        r.innings = 2

    # ── Innings number ────────────────────────────────────────
    inn = re.search(r'(\d)(?:st|nd|rd|th)\s+innings?', text, re.IGNORECASE)
    if inn:
        r.innings = int(inn.group(1))

    # ── Toss ──────────────────────────────────────────────────
    toss = re.search(
        r'([\w\s]+?)\s+won\s+the\s+toss\s+and\s+(?:elected|chose)\s+to\s+(bat|field)',
        text, re.IGNORECASE
    )
    if toss:
        r.toss_winner = toss.group(1).strip()
        r.toss_choice = toss.group(2).strip()

    # ── Result ────────────────────────────────────────────────
    result = re.search(
        r'[\w\s]+?\s+(?:won|beat|defeated)\s+[\w\s]+?\s+by\s+[\w\d\s]+',
        text, re.IGNORECASE
    )
    if result:
        r.result_str   = result.group(0).strip()
        r.match_status = "Complete"

    # ── Batting team ──────────────────────────────────────────
    if team_a and team_b and r.score > 0:
        score_idx = text.find(str(r.score))
        if score_idx >= 0:
            ctx = text[max(0, score_idx-150):score_idx+50].lower()
            ta_word = team_a.lower().split()[-1]
            tb_word = team_b.lower().split()[-1]
            if ta_word in ctx:
                r.batting_team = team_a
                r.bowling_team = team_b
            elif tb_word in ctx:
                r.batting_team = team_b
                r.bowling_team = team_a

    return r

# ── Strategy 1: cricketdata.org ───────────────────────────────
def _get_cricketdata_key() -> str:
    """Get cricketdata.org API key from Streamlit secrets or use test key."""
    try:
        import streamlit as st
        if "CRICKETDATA_KEY" in st.secrets:
            return st.secrets["CRICKETDATA_KEY"]
    except Exception:
        pass
    return "TESTKEY0273"  # fallback public test key


def _team_keys(team_a: str, team_b: str):
    """
    Generate robust search keys for matching team names in API responses.
    Handles "Sri Lanka Women" -> ["sri lanka", "sri", "lanka"]
    Avoids using just "women" which matches every women's match.
    """
    def keys(name: str):
        # Remove "Women", "Men", "W", suffixes
        clean = name.lower()
        clean = clean.replace(" women","").replace(" men","").strip()
        clean = clean.replace("super giants","supergiant").replace(" ","-")
        # Return meaningful words — skip single-char and generic words
        words = [w for w in clean.replace("-"," ").split()
                 if len(w) > 2 and w not in ("the","and","for")]
        # First meaningful word is the primary key
        primary = words[0] if words else clean[:4]
        return primary, clean  # (primary_word, full_clean)

    ta_p, ta_f = keys(team_a)
    tb_p, tb_f = keys(team_b)
    return ta_p, tb_p, ta_f, tb_f

def _try_cricketdata(team_a: str, team_b: str, fmt: str) -> ScoreResult:
    """
    cricketdata.org gives 500 free req/day.
    No API key needed for the basic current matches endpoint.
    """
    if not HAS_REQUESTS:
        return ScoreResult(error="requests not installed")
    try:
        key = _get_cricketdata_key()
        # cricketdata.org API — 500 free calls/day with registered key
        r = requests.get(
            f"https://api.cricapi.com/v1/currentMatches?apikey={key}&offset=0",
            headers=HEADERS, timeout=6
        )
        if r.status_code != 200:
            return ScoreResult(error=f"cricketdata HTTP {r.status_code}")

        data = r.json()
        if data.get("status") != "success":
            return ScoreResult(error="cricketdata: no success status")

        # Find matching match
        ta_low = team_a.lower(); tb_low = team_b.lower()
        for match in data.get("data", []):
            teams_str = " ".join(t.lower() for t in match.get("teams", []))
            ta_p, tb_p, ta_f, tb_f = _team_keys(team_a, team_b)
            if ta_p in teams_str and tb_p in teams_str:
                # Found the match
                score_list = match.get("score", [])
                if not score_list:
                    return ScoreResult(error="no score yet", source="cricketdata")

                latest = score_list[-1]
                res = ScoreResult(success=True, source="cricketdata.org")
                res.score     = latest.get("r", 0)
                res.wickets   = latest.get("w", 0)
                ov = str(latest.get("o", "0"))
                res.overs_str  = ov
                res.balls_done = overs_to_balls(ov)
                res.innings    = len(score_list)
                res.match_status = match.get("status", "")

                # Target from status string
                status = match.get("status", "")
                tgt = re.search(r"target[:\s]+(\d+)", status, re.IGNORECASE)
                if tgt:
                    res.target = int(tgt.group(1))
                    res.runs_needed = res.target - res.score

                # Batting team
                batting = match.get("toss", {})
                res.toss_winner = batting.get("winner", "")
                res.toss_choice = batting.get("decision", "")

                return res

        return ScoreResult(error=f"cricketdata: {team_a} vs {team_b} not found in current matches")

    except Exception as e:
        return ScoreResult(error=f"cricketdata exception: {e}")

# ── Strategy 2: ESPN Cricinfo unofficial JSON ─────────────────
def _try_espn(team_a: str, team_b: str, match_date: str) -> ScoreResult:
    """
    ESPN's unofficial API returns JSON for current matches.
    Endpoint changes occasionally but usually stable within a season.
    """
    if not HAS_REQUESTS:
        return ScoreResult(error="requests not installed")
    try:
        # ESPN Cricket live matches endpoint
        r = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/cricket/scoreboard",
            headers=HEADERS, timeout=6
        )
        if r.status_code != 200:
            return ScoreResult(error=f"ESPN HTTP {r.status_code}")

        data = r.json()
        ta_low = team_a.lower(); tb_low = team_b.lower()

        for event in data.get("events", []):
            name = event.get("name", "").lower()
            if any(ta_low.split()[-1] in name.split() or
                   tb_low.split()[-1] in name.split() for _ in [1]):
                # Try to parse score from event
                comps = event.get("competitions", [{}])
                if not comps:
                    continue
                comp = comps[0]
                competitors = comp.get("competitors", [])
                status = comp.get("status", {})

                res = ScoreResult(success=True, source="ESPN")
                res.match_status = status.get("type", {}).get("description", "")

                for competitor in competitors:
                    score_str = competitor.get("score", "0")
                    team_name = competitor.get("team", {}).get("displayName", "")
                    if score_str and score_str != "0":
                        # Parse "143/10 (99.0 ov)"
                        parsed = parse_score_from_text(score_str, team_a, team_b)
                        if parsed.success:
                            res.score      = parsed.score
                            res.wickets    = parsed.wickets
                            res.balls_done = parsed.balls_done
                            res.batting_team = team_name
                            break

                if res.score > 0:
                    return res

        return ScoreResult(error="ESPN: match not found in scoreboard")

    except Exception as e:
        return ScoreResult(error=f"ESPN exception: {e}")

# ── Strategy 3: Cricbuzz / cricketdata.org ───────────────────
def _try_cricbuzz(team_a: str, team_b: str) -> ScoreResult:
    """
    Try multiple free working cricket score sources.
    1. cricbuzz-live.vercel.app — unofficial Cricbuzz wrapper, free, no key
    2. mapps.cricbuzz.com — Cricbuzz mobile API
    3. cricketdata.org (api.cricapi.com) — second attempt with registered key
    """
    if not HAS_REQUESTS:
        return ScoreResult(error="requests not installed")

    ta_key = team_a.lower().split()[-1]
    tb_key = team_b.lower().split()[-1]

    headers = {**HEADERS, "Accept": "application/json, */*"}

    # ── Source 1: cricbuzz-live.vercel.app (no key, free) ─────
    try:
        # Get list of live matches
        r = requests.get(
            "https://cricbuzz-live.vercel.app/v1/matches",
            headers=headers, timeout=6
        )
        if r.status_code == 200:
            data = r.json()
            matches = data.get("data", {}).get("matches", []) or data.get("matches", [])
            ta_p, tb_p, ta_f, tb_f = _team_keys(team_a, team_b)
            for m in matches:
                title = (m.get("title","") or "").lower()
                if ta_p in title and tb_p in title:
                    match_id = m.get("id","")
                    if match_id:
                        # Fetch detailed score for this match
                        r2 = requests.get(
                            f"https://cricbuzz-live.vercel.app/v1/score/{match_id}",
                            headers=headers, timeout=6
                        )
                        if r2.status_code == 200:
                            d2 = r2.json().get("data",{})
                            live_score = d2.get("liveScore","")
                            update     = d2.get("update","")
                            state      = (d2.get("state","") or update or "").lower()

                            # Check if not started
                            if "yet to begin" in state or "upcoming" in state:
                                return ScoreResult(
                                    success=False,
                                    match_status="NotStarted",
                                    error="Match has not started yet"
                                )

                            # Parse the live score string e.g. "GG 155/5 (18.2)"
                            if live_score:
                                res = parse_score_from_text(
                                    f"{live_score} {update}", team_a, team_b
                                )
                                if res.success:
                                    res.source = "Cricbuzz"
                                    if "won" in update.lower():
                                        res.result_str   = update
                                        res.match_status = "Complete"
                                    return res
    except Exception as e:
        pass

    # ── Source 2: mapps.cricbuzz.com mobile API ────────────────
    try:
        r = requests.get(
            "https://mapps.cricbuzz.com/cbzios/match/livematches",
            headers={**headers, "App-Id": "com.cricbuzz.cricket"},
            timeout=6
        )
        if r.status_code == 200:
            data = r.json()
            for match in data.get("matchMap", {}).values():
                header = match.get("matchHeader", {})
                ta_name = header.get("team1", {}).get("shortName","").lower()
                tb_name = header.get("team2", {}).get("shortName","").lower()
                ta_p, tb_p, ta_f, tb_f = _team_keys(team_a, team_b)
                if ta_p in ta_name+tb_name and tb_p in ta_name+tb_name:
                    state = header.get("state","").lower()
                    if "upcoming" in state or "preview" in state:
                        return ScoreResult(
                            success=False, match_status="NotStarted",
                            error="Match has not started yet"
                        )
                    # Get score from miniscore
                    ms = match.get("miniscore", {})
                    bat_score = ms.get("batTeam", {})
                    runs = bat_score.get("teamScore", 0)
                    wkts = bat_score.get("teamWkts", 0)
                    overs= ms.get("overs", 0)
                    if runs:
                        res = ScoreResult(success=True, source="Cricbuzz")
                        res.score      = int(runs)
                        res.wickets    = int(wkts)
                        res.balls_done = int(float(overs)*6)
                        res.overs_str  = str(overs)
                        return res
    except Exception:
        pass

    # ── Source 3: cricketdata.org second attempt (different endpoint) ────
    try:
        key3 = _get_cricketdata_key()
        for apikey in [key3]:
            r = requests.get(
                f"https://api.cricapi.com/v1/currentMatches?apikey={apikey}&offset=0",
                headers=headers, timeout=6
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    for m in data.get("data", []):
                        teams = " ".join(m.get("teams", [])).lower()
                        ta_p, tb_p, ta_f, tb_f = _team_keys(team_a, team_b)
                        if ta_p in teams and tb_p in teams:
                            scores = m.get("score", [])
                            status = (m.get("status", "") or "").lower()
                            matchStarted = m.get("matchStarted", False)

                            if not matchStarted or "yet to begin" in status or not scores:
                                return ScoreResult(
                                    success=False, match_status="NotStarted",
                                    error="Match has not started yet"
                                )
                            latest = scores[-1]
                            res = ScoreResult(success=True, source="CricAPI")
                            res.score      = int(latest.get("r", 0))
                            res.wickets    = int(latest.get("w", 0))
                            ov = str(latest.get("o", 0))
                            res.overs_str  = ov
                            res.balls_done = overs_to_balls(ov)
                            res.innings    = len(scores)
                            res.match_status = m.get("status", "")
                            if "won" in status:
                                res.result_str   = m.get("status", "")
                                res.match_status = "Complete"
                            return res
                    break  # tried this key, no match found
    except Exception:
        pass

    return ScoreResult(
        error="Cricbuzz/CricAPI: match not found in live feeds",
        raw_text=f"Searched for '{ta_key}' and '{tb_key}'"
    )
    if not HAS_REQUESTS:
        return ScoreResult(error="requests not installed")

    ta_key = team_a.lower().split()[-1]
    tb_key = team_b.lower().split()[-1]

    endpoints = [
        "https://www.cricbuzz.com/api/cricket-match/live/matches",
        "https://www.cricbuzz.com/cricket-match/live-scores",
        "https://www.cricbuzz.com/api/matches",
    ]

    cb_headers = {
        **HEADERS,
        "Referer": "https://www.cricbuzz.com/",
        "Accept":  "application/json, text/html, */*",
        "Origin":  "https://www.cricbuzz.com",
    }

    for url in endpoints:
        try:
            r = requests.get(url, headers=cb_headers, timeout=6)
            if r.status_code != 200:
                continue

            content = r.text

            # Check if our match is mentioned at all
            ta_p, tb_p, ta_f, tb_f = _team_keys(team_a, team_b)
            match_mentioned = (ta_p in content.lower() and
                               tb_p in content.lower())

            if not match_mentioned:
                continue

            # Try JSON parse
            try:
                import json as _json
                data = _json.loads(content)

                def find_match(obj, depth=0):
                    if depth > 8:
                        return None
                    if isinstance(obj, dict):
                        teams_str = str(obj).lower()
                        if ta_p in teams_str and tb_p in teams_str:
                            # Check match state
                            state = (obj.get("state","") or
                                     obj.get("status","") or
                                     obj.get("matchState","") or "").lower()

                            # Upcoming / not started
                            if any(w in state for w in
                                   ["upcoming","preview","not started","scheduled","yet to"]):
                                res = ScoreResult(success=False)
                                res.match_status = "NotStarted"
                                res.error = "Match has not started yet"
                                # Try to get start time
                                start = (obj.get("startTime","") or
                                         obj.get("matchTime","") or
                                         obj.get("time",""))
                                if start:
                                    res.error = f"Match has not started yet — starts {start}"
                                return res

                            # Live — extract score
                            score_raw = (obj.get("score","") or
                                        obj.get("bat1Score","") or
                                        obj.get("batScore","") or
                                        obj.get("currentScore","") or
                                        obj.get("liveScore",""))
                            if score_raw:
                                res = parse_score_from_text(
                                    str(score_raw), team_a, team_b
                                )
                                if res.success:
                                    return res

                        for v in obj.values():
                            found = find_match(v, depth+1)
                            if found:
                                return found

                    elif isinstance(obj, list):
                        for item in obj:
                            found = find_match(item, depth+1)
                            if found:
                                return found
                    return None

                result = find_match(data)
                if result:
                    if result.success:
                        result.source = "Cricbuzz"
                    return result

            except Exception:
                pass

            # Text parse fallback — check for "upcoming" keywords
            content_low = content.lower()
            if any(w in content_low for w in
                   ["upcoming","not started","yet to begin","starts at","starts in"]):
                res = ScoreResult(success=False)
                res.match_status = "NotStarted"
                res.error = "Match has not started yet"
                return res

            # Try text score parse
            parsed = parse_score_from_text(content, team_a, team_b)
            if parsed.success:
                parsed.source = "Cricbuzz"
                return parsed

        except Exception as ex:
            continue

    return ScoreResult(
        error="Cricbuzz: match not found in live feeds",
        raw_text=f"Searched for '{ta_key}' and '{tb_key}' in {len(endpoints)} endpoints"
    )

# ── Strategy 4: Claude-powered search (via Anthropic API) ─────
def _try_claude_search(team_a: str, team_b: str, match_date: str,
                       api_key: str = "") -> ScoreResult:
    """
    Use Claude's web search to find the live score.
    Requires ANTHROPIC_API_KEY in Streamlit secrets or environment.
    Most reliable source as Claude can search and parse any format.
    """
    if not HAS_REQUESTS:
        return ScoreResult(error="requests not installed")

    # Get API key from environment or passed parameter
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            # Streamlit secrets — try dict-style access first
            try:
                key = st.secrets["ANTHROPIC_API_KEY"]
            except (KeyError, AttributeError):
                key = st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st.secrets, "get") else ""
        except Exception:
            pass

    if not key:
        return ScoreResult(error="No ANTHROPIC_API_KEY found in environment or Streamlit secrets. Add it via Manage App → Settings → Secrets")

    try:
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 400,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{
                "role": "user",
                "content": (
                    f"Search for the cricket match result or live score: "
                    f"{team_a} vs {team_b} on {match_date}. "
                    f"This could be a completed match or live match. "
                    f"Reply ONLY in this exact structured format (no other text):\n"
                    f"SCORE1: runs/wickets  (team batting first final score)\n"
                    f"TEAM1: team_name_that_batted_first\n"
                    f"SCORE2: runs/wickets  (team batting second score, or 'innings not started')\n"
                    f"TEAM2: team_name_that_batted_second\n"
                    f"BALLS: balls_completed_in_current_or_last_innings\n"
                    f"INNINGS: 1 or 2  (which innings is current or was last)\n"
                    f"TARGET: runs (only if 2nd innings)\n"
                    f"STATUS: Live or Complete or NotStarted\n"
                    f"RESULT: result_string (e.g. 'Welsh Fire won by 6 wickets') if complete\n"
                    f"BATTING: team currently batting (if live)\n\n"
                    f"If match has not started:\n"
                    f"STATUS: NotStarted\n"
                    f"TOSS: winner elected to bat/field (if known)"
                )
            }]
        }
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         key,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
            timeout=20
        )
        if r.status_code != 200:
            return ScoreResult(error=f"Claude API HTTP {r.status_code}: {r.text[:100]}")

        data = r.json()
        text_blocks = [b["text"] for b in data.get("content", [])
                       if b.get("type") == "text"]
        response_text = "\n".join(text_blocks)

        res = ScoreResult(source="Claude web search")

        # Parse structured response
        score1_m = re.search(r"SCORE1:\s*(\d+)/(\d+)", response_text)
        score2_m = re.search(r"SCORE2:\s*(\d+)/(\d+)", response_text)
        team1_m  = re.search(r"TEAM1:\s*(.+)", response_text)
        team2_m  = re.search(r"TEAM2:\s*(.+)", response_text)
        score_m  = re.search(r"^SCORE:\s*(\d+)/(\d+)", response_text, re.MULTILINE)
        balls_m  = re.search(r"BALLS:\s*(\d+)", response_text)
        inn_m    = re.search(r"INNINGS:\s*(\d)", response_text)
        tgt_m    = re.search(r"TARGET:\s*(\d+)", response_text)
        bat_m    = re.search(r"BATTING:\s*(.+)", response_text)
        status_m = re.search(r"STATUS:\s*(\w+)", response_text)
        result_m = re.search(r"RESULT:\s*(.+)", response_text)
        toss_m   = re.search(r"TOSS:\s*(.+)", response_text)

        if status_m:
            res.match_status = status_m.group(1).strip()

        # Completed match — show both innings
        if score1_m and score2_m:
            res.score   = int(score2_m.group(1))  # show 2nd innings as "current"
            res.wickets = int(score2_m.group(2))
            res.innings = 2
            res.success = True
            if team2_m:
                res.batting_team = team2_m.group(1).strip()
                res.bowling_team = team1_m.group(1).strip() if team1_m else team_a
            # Build result string showing both scores
            t1 = team1_m.group(1).strip() if team1_m else team_a
            t2 = team2_m.group(1).strip() if team2_m else team_b
            s1 = f"{score1_m.group(1)}/{score1_m.group(2)}"
            s2 = f"{score2_m.group(1)}/{score2_m.group(2)}"
            if result_m:
                res.result_str = result_m.group(1).strip()
            # Put full scorecard in match_status for display
            res.match_status = f"Complete — {t1} {s1} | {t2} {s2}"
        elif score_m:
            res.score   = int(score_m.group(1))
            res.wickets = int(score_m.group(2))
            res.success = True

        if balls_m:
            res.balls_done = int(balls_m.group(1))
            res.overs_str  = f"{res.balls_done//6}.{res.balls_done%6}"
        if inn_m:
            res.innings = int(inn_m.group(1))
        if tgt_m:
            res.target     = int(tgt_m.group(1))
            res.runs_needed= res.target - res.score if res.score else None
        if bat_m and not res.batting_team:
            res.batting_team = bat_m.group(1).strip()
            res.bowling_team = (team_b if res.batting_team.lower() in team_a.lower()
                               else team_a)
        if result_m and not res.result_str:
            res.result_str = result_m.group(1).strip()
        if toss_m:
            res.toss_winner = toss_m.group(1).strip()

        if res.match_status == "NotStarted":
            res.success = False
            res.error = "Match has not started yet"

        if not res.success and not res.error:
            res.error = f"Could not parse response: {response_text[:200]}"

        return res

    except Exception as e:
        return ScoreResult(error=f"Claude search error: {e}")

# ── Main entry point ──────────────────────────────────────────
def fetch_live_score(
    team_a:     str,
    team_b:     str,
    match_date: str,
    fmt:        str = "ODI",
    text_input: str = "",
    api_key:    str = "",
) -> ScoreResult:
    """
    Try 4 strategies in order, return first success.
    """
    import datetime as _dt

    # Determine if match is in the past — if so, skip "NotStarted" returns
    try:
        match_dt  = _dt.date.fromisoformat(match_date)
        is_past   = match_dt < _dt.date.today()
        is_today  = match_dt == _dt.date.today()
    except Exception:
        is_past  = False
        is_today = True

    # Strategy 0: user pasted text
    if text_input and len(text_input) > 10:
        res = parse_score_from_text(text_input, team_a, team_b)
        if res.success:
            res.source = "pasted text"
            return res

    errors = []

    errors = []

    # Each strategy: if match not started, return immediately — no point trying others
    for name, fn_result in [
        ("cricketdata", _try_cricketdata(team_a, team_b, fmt)),
        ("ESPN",        _try_espn(team_a, team_b, match_date)),
        ("Cricbuzz",    _try_cricbuzz(team_a, team_b)),
    ]:
        if fn_result.success:
            return fn_result
        if fn_result.match_status == "NotStarted" and not is_past:
            fn_result.error = fn_result.error or "Match has not started yet"
            return fn_result
        errors.append(f"{name}: {fn_result.error}")

    # Strategy 4: Claude web search — works for both live AND completed matches
    res = _try_claude_search(team_a, team_b, match_date, api_key)
    if res.success:
        return res
    if res.match_status == "NotStarted" and not is_past:
        res.error = res.error or "Match has not started yet"
        return res
    errors.append(f"Claude: {res.error}")

    # If past match and nothing found — give a specific message
    if is_past:
        return ScoreResult(
            success=False,
            error=f"Match was yesterday/earlier. Sources returned stale pre-match data. Enter result manually or log it via ✏️ Log result.",
            raw_text="\n".join(errors),
            source="none",
            match_status="Complete"
        )

    return ScoreResult(
        success=False,
        error="All sources failed. Enter score manually.",
        raw_text="\n".join(errors),
        source="none"
    )
