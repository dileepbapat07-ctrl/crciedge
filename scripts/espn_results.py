"""
scripts/espn_results.py
========================
Scrapes ESPNcricinfo for completed match results.
No API key needed. Works from Streamlit Cloud.

Strategy — tries 4 ESPN endpoints in order:
1. hs-consumer-api results JSON (structured, best)
2. hs-consumer-api recent JSON
3. espncricinfo.com HTML live scores page (has recent results section)
4. cricbuzz-live.vercel.app (fallback)
"""

import re, requests
from typing import Optional
from dataclasses import dataclass, field

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "x-version":       "experimental",
    "Referer":         "https://www.espncricinfo.com/",
}

@dataclass
class ResultData:
    success:    bool = False
    team1:      str  = ""
    score1:     str  = ""
    team2:      str  = ""
    score2:     str  = ""
    winner:     str  = ""
    result_str: str  = ""
    potm:       str  = ""
    source:     str  = ""
    raw:        str  = ""

def _team_key(name: str) -> str:
    clean = name.lower().replace(" women","").replace(" men","").strip()
    words = [w for w in clean.split() if len(w) > 2 and w not in ("the","and","for")]
    return words[0] if words else clean[:4]

def _match_teams(ta_k, tb_k, text: str) -> bool:
    t = text.lower()
    return ta_k in t and tb_k in t

def _parse_result_str(result_str: str, team_a: str, team_b: str) -> str:
    """Extract winner name from result string."""
    result_low = result_str.lower()
    ta_k = _team_key(team_a)
    tb_k = _team_key(team_b)
    if ta_k in result_low and "won" in result_low:
        return team_a
    if tb_k in result_low and "won" in result_low:
        return team_b
    # Try to find "X won by..." pattern
    m = re.search(r"([\w\s]+)\s+won\s+by", result_str, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""

# ── Endpoint 1: hs-consumer-api results ──────────────────────
def _try_hsconsumer_results(team_a, team_b, match_date):
    ta_k = _team_key(team_a)
    tb_k = _team_key(team_b)
    try:
        for url in [
            "https://hs-consumer-api.espncricinfo.com/v1/pages/matches/results?lang=en&limit=50",
            "https://hs-consumer-api.espncricinfo.com/v1/pages/matches/recent?lang=en&limit=50",
        ]:
            r = requests.get(url, headers=HEADERS, timeout=7)
            if r.status_code != 200:
                continue
            data = r.json()
            # Walk content structure
            matches = (
                data.get("content", {}).get("matches", []) or
                data.get("matches", []) or
                data.get("data", []) or []
            )
            for m in matches:
                # Get team names from various possible keys
                t1 = (m.get("team1", {}) or {})
                t2 = (m.get("team2", {}) or {})
                t1n = (t1.get("name","") or t1.get("shortName","") or "").lower()
                t2n = (t2.get("name","") or t2.get("shortName","") or "").lower()

                if not (ta_k in t1n+t2n and tb_k in t1n+t2n):
                    continue

                # Date check
                m_date = (m.get("startDate","") or m.get("date","") or "")[:10]
                if m_date and m_date != match_date:
                    continue

                status = (m.get("status","") or m.get("result","") or "")
                t1s = str(m.get("team1Score","") or m.get("score1","") or "")
                t2s = str(m.get("team2Score","") or m.get("score2","") or "")

                if not status or "won" not in status.lower():
                    continue

                winner = _parse_result_str(status, team_a, team_b)
                return ResultData(
                    success    = True,
                    team1      = t1.get("name", team_a),
                    score1     = t1s,
                    team2      = t2.get("name", team_b),
                    score2     = t2s,
                    winner     = winner,
                    result_str = status,
                    source     = "ESPNcricinfo API",
                )
    except Exception as e:
        pass
    return None

# ── Endpoint 2: espncricinfo HTML live scores page ────────────
def _try_espn_html(team_a, team_b, match_date):
    ta_k = _team_key(team_a)
    tb_k = _team_key(team_b)
    try:
        r = requests.get(
            "https://www.espncricinfo.com/live-cricket-score",
            headers=HEADERS, timeout=7
        )
        if r.status_code != 200:
            return None

        html = r.text
        # Find result sections — ESPNcricinfo embeds JSON in script tags
        # Look for __NEXT_DATA__ or similar
        json_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if json_match:
            import json
            try:
                page_data = json.loads(json_match.group(1))
                # Walk the JSON tree looking for matches
                def find_matches(obj, depth=0):
                    if depth > 10: return []
                    found = []
                    if isinstance(obj, dict):
                        # Check if this looks like a match
                        text_repr = str(obj).lower()
                        if ta_k in text_repr and tb_k in text_repr:
                            status = obj.get("status","") or obj.get("result","") or ""
                            if "won" in status.lower():
                                winner = _parse_result_str(status, team_a, team_b)
                                if winner:
                                    found.append(ResultData(
                                        success=True, winner=winner,
                                        result_str=status,
                                        source="ESPNcricinfo HTML"
                                    ))
                        for v in obj.values():
                            found.extend(find_matches(v, depth+1))
                    elif isinstance(obj, list):
                        for item in obj:
                            found.extend(find_matches(item, depth+1))
                    return found

                results = find_matches(page_data)
                if results:
                    return results[0]
            except Exception:
                pass

        # Fallback: regex on raw HTML
        # Look for pattern like "Pakistan Women won by 5 wickets"
        result_pat = re.compile(
            r'(' + re.escape(ta_k) + r'[^"<]{0,40}won[^"<]{0,60}|'
            + re.escape(tb_k) + r'[^"<]{0,40}won[^"<]{0,60})',
            re.IGNORECASE
        )
        match = result_pat.search(html)
        if match:
            result_str = match.group(0).strip()
            winner = _parse_result_str(result_str, team_a, team_b)
            if winner:
                return ResultData(
                    success=True, winner=winner,
                    result_str=result_str,
                    source="ESPNcricinfo HTML"
                )
    except Exception:
        pass
    return None

# ── Endpoint 3: cricbuzz-live wrapper ─────────────────────────
def _try_cricbuzz_results(team_a, team_b, match_date):
    ta_k = _team_key(team_a)
    tb_k = _team_key(team_b)
    try:
        r = requests.get(
            "https://cricbuzz-live.vercel.app/v1/matches",
            headers=HEADERS, timeout=6
        )
        if r.status_code != 200:
            return None
        data = r.json()
        matches = data.get("data",{}).get("matches",[]) or data.get("matches",[])
        for m in matches:
            title = (m.get("title","") or "").lower()
            if ta_k not in title or tb_k not in title:
                continue
            status = m.get("status","") or m.get("result","") or m.get("update","") or ""
            if "won" not in status.lower():
                continue
            winner = _parse_result_str(status, team_a, team_b)
            if winner:
                return ResultData(
                    success=True, winner=winner,
                    result_str=status, source="Cricbuzz"
                )
    except Exception:
        pass
    return None

# ── Endpoint 4: cricketdata.org (registered key) ─────────────
def _try_cricketdata(team_a, team_b, match_date, api_key="TESTKEY0273"):
    ta_k = _team_key(team_a)
    tb_k = _team_key(team_b)
    try:
        # Use /v1/matches which returns recent+completed, not just current
        for endpoint in ["matches", "currentMatches"]:
            r = requests.get(
                f"https://api.cricapi.com/v1/{endpoint}"
                f"?apikey={api_key}&offset=0",
                headers=HEADERS, timeout=6
            )
            if r.status_code != 200:
                continue
            data = r.json()
            if data.get("status") != "success":
                continue
            for m in data.get("data", []):
                teams = " ".join(m.get("teams",[])).lower()
                if ta_k not in teams or tb_k not in teams:
                    continue
                m_date = m.get("date","")[:10]
                if m_date and m_date != match_date:
                    continue
                status = m.get("status","") or ""
                if "won" not in status.lower():
                    continue
                scores = m.get("score",[])
                sa = f"{scores[0].get('r',0)}/{scores[0].get('w',0)} ({scores[0].get('o',0)} ov)" if scores else ""
                sb = f"{scores[1].get('r',0)}/{scores[1].get('w',0)} ({scores[1].get('o',0)} ov)" if len(scores)>1 else ""
                winner = _parse_result_str(status, team_a, team_b)
                if winner:
                    return ResultData(
                        success=True, winner=winner,
                        score1=sa, score2=sb,
                        result_str=status, source="cricketdata.org"
                    )
    except Exception:
        pass
    return None

# ── Main entry point ──────────────────────────────────────────
def fetch_match_result(team_a: str, team_b: str,
                       match_date: str,
                       api_key: str = "TESTKEY0273") -> Optional[ResultData]:
    """
    Try all sources, return first successful result.
    All free — no Anthropic credits needed.
    """
    for fn in [
        lambda: _try_hsconsumer_results(team_a, team_b, match_date),
        lambda: _try_espn_html(team_a, team_b, match_date),
        lambda: _try_cricbuzz_results(team_a, team_b, match_date),
        lambda: _try_cricketdata(team_a, team_b, match_date, api_key),
    ]:
        try:
            res = fn()
            if res and res.success and res.winner:
                return res
        except Exception:
            pass
    return None

if __name__ == "__main__":
    # Test
    tests = [
        ("Pakistan Women", "Sri Lanka Women", "2026-07-23"),
        ("Welsh Fire", "Southern Brave", "2026-07-22"),
        ("Southern Brave Women", "Welsh Fire Women", "2026-07-22"),
    ]
    print("ESPN Results Scraper Test")
    print("="*55)
    for ta, tb, date in tests:
        print(f"\n{ta} vs {tb} ({date})")
        res = fetch_match_result(ta, tb, date)
        if res:
            print(f"  ✅ {res.result_str} [{res.source}]")
        else:
            print(f"  ❌ Not found (sandbox blocks external — works on Streamlit Cloud)")
