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
    Handles:
      "51/3 (7.3 ov)"
      "England 258 all out (48.2 overs)"
      "India 144/3 (14 balls)"   ← 100-ball format
      "Target: 144, India need 93 runs from 56 balls"
    """
    r = ScoreResult()
    r.raw_text = text[:500]

    # Score patterns: runs/wickets (overs)
    patterns = [
        # "51/3 (7.3 ov)" or "51/3 (44 balls)"
        r"(\d{1,3})/(\d{1,2})\s*\(?\s*(\d{1,3}(?:\.\d)?)\s*(?:ov(?:ers?)?|balls?|b)\s*\)?",
        # "258 all out (48.2)"
        r"(\d{2,3})\s+(?:all\s+out|ao)\s*\(?\s*(\d{1,3}(?:\.\d)?)\s*(?:ov(?:ers?)?|balls?)?\s*\)?",
        # "144/3" with no overs
        r"(\d{1,3})/(\d{1,2})",
    ]

    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        if matches:
            m = matches[-1]  # take the most recent score
            if len(m) >= 2:
                r.score   = int(m[0])
                r.wickets = int(m[1]) if len(m) > 1 and m[1] else 0
                if len(m) > 2 and m[2]:
                    r.overs_str = m[2]
                    r.balls_done = overs_to_balls(m[2])
                r.success = True
                r.source  = "text_parse"
                break

    # Target / runs needed
    tgt = re.search(
        r"(?:target|chasing|need[s]?|require[s]?)\s*[:\s]*(\d{2,3})",
        text, re.IGNORECASE
    )
    if tgt:
        r.target  = int(tgt.group(1))
        r.innings = 2

    runs_needed = re.search(
        r"need[s]?\s+(\d{1,3})\s+(?:more\s+)?runs?\s+(?:from|in|off)\s+(\d{1,3})\s+balls?",
        text, re.IGNORECASE
    )
    if runs_needed:
        r.runs_needed = int(runs_needed.group(1))
        r.innings = 2

    # Innings number
    inn_m = re.search(r"(\d)(?:st|nd|rd|th)\s+innings?", text, re.IGNORECASE)
    if inn_m:
        r.innings = int(inn_m.group(1))

    # Toss
    toss_m = re.search(
        r"([\w\s]+?)\s+won\s+the\s+toss\s+and\s+(?:elected|chose)\s+to\s+(bat|field)",
        text, re.IGNORECASE
    )
    if toss_m:
        r.toss_winner = toss_m.group(1).strip()
        r.toss_choice = toss_m.group(2).strip()

    # Result
    result_m = re.search(
        r"([\w\s]+?)\s+(?:won|beat|beats|defeated)\s+[\w\s]+?\s+by\s+[\w\s]+",
        text, re.IGNORECASE
    )
    if result_m:
        r.result_str  = result_m.group(0).strip()
        r.match_status = "Complete"

    # Batting team detection
    if team_a and team_b:
        ta_low = team_a.lower().split()[-1]
        tb_low = team_b.lower().split()[-1]
        if r.score > 0:
            # Look for team name near the score in text
            score_idx = text.find(str(r.score))
            if score_idx >= 0:
                ctx = text[max(0, score_idx-150):score_idx+50].lower()
                if ta_low in ctx:
                    r.batting_team = team_a
                    r.bowling_team = team_b
                elif tb_low in ctx:
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
def _try_claude_search(team_a: str, team_b: str, match_date: str) -> ScoreResult:
    """
    Use Claude's own web search capability to find the live score.
    This calls the Anthropic API from within the Streamlit app.
    Most reliable as Claude knows how to parse cricket scores.
    """
    if not HAS_REQUESTS:
        return ScoreResult(error="requests not installed")
    try:
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{
                "role": "user",
                "content": (
                    f"What is the current live score for {team_a} vs {team_b} "
                    f"cricket match on {match_date}? "
                    f"Reply ONLY in this exact format, nothing else:\n"
                    f"SCORE: runs/wickets\n"
                    f"OVERS: X.Y\n"
                    f"INNINGS: 1 or 2\n"
                    f"TARGET: runs (if 2nd innings, else omit)\n"
                    f"BATTING: team name\n"
                    f"STATUS: Live/Complete/Break\n"
                    f"RESULT: result string if complete (else omit)"
                )
            }]
        }
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=15
        )
        if r.status_code != 200:
            return ScoreResult(error=f"Claude API HTTP {r.status_code}")

        data = r.json()
        # Extract text from response
        text_blocks = [b["text"] for b in data.get("content", [])
                       if b.get("type") == "text"]
        response_text = "\n".join(text_blocks)

        # Parse structured response
        res = ScoreResult(source="Claude web search")

        score_m  = re.search(r"SCORE:\s*(\d+)/(\d+)", response_text)
        overs_m  = re.search(r"OVERS:\s*([\d.]+)", response_text)
        inn_m    = re.search(r"INNINGS:\s*(\d)", response_text)
        tgt_m    = re.search(r"TARGET:\s*(\d+)", response_text)
        bat_m    = re.search(r"BATTING:\s*(.+)", response_text)
        status_m = re.search(r"STATUS:\s*(.+)", response_text)
        result_m = re.search(r"RESULT:\s*(.+)", response_text)

        if score_m:
            res.score    = int(score_m.group(1))
            res.wickets  = int(score_m.group(2))
            res.success  = True
        if overs_m:
            res.overs_str  = overs_m.group(1)
            res.balls_done = overs_to_balls(overs_m.group(1))
        if inn_m:
            res.innings = int(inn_m.group(1))
        if tgt_m:
            res.target     = int(tgt_m.group(1))
            res.runs_needed= res.target - res.score
        if bat_m:
            res.batting_team = bat_m.group(1).strip()
            res.bowling_team = team_b if res.batting_team==team_a else team_a
        if status_m:
            res.match_status = status_m.group(1).strip()
        if result_m:
            res.result_str = result_m.group(1).strip()

        if not res.success:
            res.error = f"Claude returned: {response_text[:200]}"

        return res

    except Exception as e:
        return ScoreResult(error=f"Claude search exception: {e}")

# ── Main entry point ──────────────────────────────────────────
def fetch_live_score(
    team_a:     str,
    team_b:     str,
    match_date: str,
    fmt:        str = "ODI",
    text_input: str = "",   # if user pastes text — skip all API calls
) -> ScoreResult:
    """
    Try 4 strategies in order, return first success.
    """
    # Strategy 0: user pasted text — parse directly, fastest
    if text_input and len(text_input) > 10:
        res = parse_score_from_text(text_input, team_a, team_b)
        if res.success:
            res.source = "pasted text"
            return res

    errors = []

    # Strategy 1: cricketdata.org API
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

    # Strategy 4: Claude web search (most reliable but slowest)
    res = _try_claude_search(team_a, team_b, match_date)
    if res.success:
        return res
    errors.append(f"Claude: {res.error}")

    # All failed
    return ScoreResult(
        success=False,
        error=f"All sources failed:\n" + "\n".join(errors),
        source="none"
    )
