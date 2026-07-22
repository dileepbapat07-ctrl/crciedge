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
def _try_cricketdata(team_a: str, team_b: str, fmt: str) -> ScoreResult:
    """
    cricketdata.org gives 500 free req/day.
    No API key needed for the basic current matches endpoint.
    """
    if not HAS_REQUESTS:
        return ScoreResult(error="requests not installed")
    try:
        # List current matches
        r = requests.get(
            "https://api.cricapi.com/v1/currentMatches?apikey=free&offset=0",
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
            teams = [t.lower() for t in match.get("teams", [])]
            if any(ta_low.split()[-1] in t for t in teams) and \
               any(tb_low.split()[-1] in t for t in teams):
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

# ── Strategy 3: Cricbuzz unofficial ──────────────────────────
def _try_cricbuzz(team_a: str, team_b: str) -> ScoreResult:
    """
    Cricbuzz has an unofficial JSON endpoint used by many apps.
    """
    if not HAS_REQUESTS:
        return ScoreResult(error="requests not installed")
    try:
        # Unofficial Cricbuzz live scores endpoint
        r = requests.get(
            "https://www.cricbuzz.com/api/cricket-match/commentary/",
            headers={**HEADERS, "Referer": "https://www.cricbuzz.com/"},
            timeout=6
        )
        if r.status_code == 200:
            text = r.text
            parsed = parse_score_from_text(text, team_a, team_b)
            if parsed.success:
                parsed.source = "Cricbuzz"
                return parsed

        return ScoreResult(error=f"Cricbuzz HTTP {r.status_code}")
    except Exception as e:
        return ScoreResult(error=f"Cricbuzz exception: {e}")

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
        # Try to get from streamlit secrets
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass

    if not key:
        return ScoreResult(error="No ANTHROPIC_API_KEY found in environment or secrets")

    try:
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 400,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{
                "role": "user",
                "content": (
                    f"Search for the live cricket score: {team_a} vs {team_b} "
                    f"on {match_date}. "
                    f"Reply ONLY in this exact structured format (no other text):\n"
                    f"SCORE: runs/wickets\n"
                    f"BALLS: balls_completed\n"
                    f"INNINGS: 1 or 2\n"
                    f"TARGET: runs_needed_to_win (only if 2nd innings, else omit)\n"
                    f"BATTING: team_name_batting_now\n"
                    f"STATUS: Live or Complete or NotStarted\n"
                    f"RESULT: result_string (only if complete, else omit)\n\n"
                    f"If match has not started yet, reply:\n"
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

        # Parse structured response
        res = ScoreResult(source="Claude web search")

        score_m  = re.search(r"SCORE:\s*(\d+)/(\d+)", response_text)
        balls_m  = re.search(r"BALLS:\s*(\d+)", response_text)
        inn_m    = re.search(r"INNINGS:\s*(\d)", response_text)
        tgt_m    = re.search(r"TARGET:\s*(\d+)", response_text)
        bat_m    = re.search(r"BATTING:\s*(.+)", response_text)
        status_m = re.search(r"STATUS:\s*(\w+)", response_text)
        result_m = re.search(r"RESULT:\s*(.+)", response_text)
        toss_m   = re.search(r"TOSS:\s*(.+)", response_text)

        if score_m:
            res.score    = int(score_m.group(1))
            res.wickets  = int(score_m.group(2))
            res.success  = True
        if balls_m:
            res.balls_done = int(balls_m.group(1))
            res.overs_str  = f"{res.balls_done//6}.{res.balls_done%6}"
        if inn_m:
            res.innings = int(inn_m.group(1))
        if tgt_m:
            res.target     = int(tgt_m.group(1))
            res.runs_needed= res.target - res.score if res.score else None
        if bat_m:
            res.batting_team = bat_m.group(1).strip()
            res.bowling_team = (team_b if res.batting_team.lower() in team_a.lower()
                               else team_a)
        if status_m:
            res.match_status = status_m.group(1).strip()
            if res.match_status == "NotStarted":
                res.success = False
                res.error   = "Match has not started yet"
                if toss_m:
                    res.toss_winner = toss_m.group(1).strip()
        if result_m:
            res.result_str = result_m.group(1).strip()
            res.match_status = "Complete"

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
    # Strategy 0: user pasted text
    if text_input and len(text_input) > 10:
        res = parse_score_from_text(text_input, team_a, team_b)
        if res.success:
            res.source = "pasted text"
            return res

    errors = []

    # Strategy 1: cricketdata.org
    res = _try_cricketdata(team_a, team_b, fmt)
    if res.success:
        return res
    errors.append(f"cricketdata: {res.error}")

    # Strategy 2: ESPN
    res = _try_espn(team_a, team_b, match_date)
    if res.success:
        return res
    errors.append(f"ESPN: {res.error}")

    # Strategy 3: Cricbuzz
    res = _try_cricbuzz(team_a, team_b)
    if res.success:
        return res
    errors.append(f"Cricbuzz: {res.error}")

    # Strategy 4: Claude web search
    res = _try_claude_search(team_a, team_b, match_date, api_key)
    if res.success:
        return res
    if res.match_status == "NotStarted":
        # Not an error — match just hasn't started
        res.error = f"Match has not started yet. Toss: {res.toss_winner or 'not announced'}"
        return res
    errors.append(f"Claude: {res.error}")

    return ScoreResult(
        success=False,
        error="All sources failed. Enter score manually.",
        raw_text="\n".join(errors),
        source="none"
    )
