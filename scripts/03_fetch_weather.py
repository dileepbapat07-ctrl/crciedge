"""
03_fetch_weather.py
Fetch weather for today's match venues from Open-Meteo.
Run every morning. Free, no API key needed.
"""
import sqlite3, os, json, urllib.request, urllib.parse
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")

# Venue lat/lon lookup
VENUE_COORDS = {
    "sophia-gardens-cardiff":          (51.478, -3.188),
    "lord's-london":                   (51.529, -0.172),
    "edgbaston-birmingham":            (52.455, -1.902),
    "the-oval-london":                 (51.483, -0.115),
    "headingley-leeds":                (53.818, -1.582),
    "trent-bridge-nottingham":         (52.936,  1.132),
    "mcg-melbourne":                   (-37.820, 144.983),
    "optus-stadium-perth":             (-31.951, 115.888),
    "the-gabba-brisbane":              (-27.485, 153.038),
    "adelaide-oval-adelaide":          (-34.916, 138.596),
    "junction-oval-melbourne":         (-37.843, 144.963),
    "waca-ground-perth":               (-31.960, 115.878),
    "bellerive-oval-hobart":           (-42.883, 147.341),
    "north-sydney-oval-sydney":        (-33.839, 151.209),
    "ma-chidambaram-stadiuchennai":    (13.063,  80.279),
    "wankhede-stadium-mumbai":         (18.938,  72.825),
    "eden-gardens-kolkata":            (22.565,  88.343),
    "narendra-modi-stadiumahmedabad":  (23.090,  72.601),
    "m-chinnaswamy-stadium-bangalore": (12.979,  77.600),
    "sher-e-bangla-stadium-dhaka":     (23.759,  90.361),
    "matiur-rahman-stadiumchattogram": (22.339,  91.831),
    "kensington-oval-bridgetown":      (13.103, -59.648),
    "providence-stadium-provi":        (6.827,  -58.107),
    "brian-lara-stadium-tarouba":      (10.348, -61.393),
    "sabina-park-kingston":            (17.997, -76.778),
    "daren-sammy-stadium-gros-i":      (14.009, -60.995),
    "warner-park-basseterre":          (17.304, -62.731),
    "arnos-vale-st-vincent":           (13.142, -61.213),
    "sir-vivian-richards-staantigua":  (17.139, -61.845),
    "harare-sports-club-harare":       (-17.806,  31.038),
    "stormont-belfast":                (54.634,  -5.836),
    "rangiri-dambulla-stadiumdambulla":(7.874,  80.651),
    "r.premadasa-stadium-colombo":     (6.926,  79.873),
    "pallekele-international-kandy":   (7.341,  80.621),
    "supersport-park-centurion":       (-25.744,  28.185),
    "newlands-cape-town":              (-33.919,  18.424),
    "the-wanderers-johannesburg":      (-26.148,  28.077),
    "eden-park-auckland":              (-36.874, 174.742),
    "basin-reserve-wellington":        (-41.307, 174.778),
    "hagley-oval-christchurch":        (-43.527, 172.627),
    "marrara-oval-darwin":             (-12.388, 130.880),
}

def dl_risk(rain_pct, cloud_pct):
    if rain_pct >= 60: return "high"
    if rain_pct >= 30: return "medium"
    return "low"

def condition(rain_pct, cloud_pct):
    if rain_pct >= 60: return "rain"
    if cloud_pct >= 70: return "cloudy"
    return "clear"

def fetch_weather(lat, lon, match_date):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&daily=precipitation_probability_max,precipitation_sum,"
        f"windspeed_10m_max,cloudcover_mean,temperature_2m_max,relativehumidity_2m_max"
        f"&timezone=auto&start_date={match_date}&end_date={match_date}"
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
        d = data.get("daily", {})
        def g(k): return d.get(k, [None])[0]
        rain  = g("precipitation_probability_max") or 0
        cloud = g("cloudcover_mean") or 0
        wind  = g("windspeed_10m_max") or 0
        temp  = g("temperature_2m_max") or 0
        humid = g("relativehumidity_2m_max") or 0
        return {
            "rain_prob_pct":   round(rain),
            "humidity_pct":    round(humid),
            "wind_kmh":        round(wind, 1),
            "cloud_cover_pct": round(cloud),
            "temp_celsius":    round(temp, 1),
            "condition":       condition(rain, cloud),
            "dl_risk":         dl_risk(rain, cloud),
        }
    except Exception as e:
        return {"error": str(e)}

def run(target_date=None):
    if target_date is None:
        target_date = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    matches = conn.execute("""
        SELECT m.match_id, m.venue_id, m.date, m.label, m.team_a, m.team_b
        FROM matches m
        WHERE m.date = ?
        ORDER BY m.step
    """, (target_date,)).fetchall()

    if not matches:
        print(f"No matches on {target_date}")
        conn.close()
        return

    print(f"\nFetching weather for {len(matches)} matches on {target_date}\n")
    results = []

    for m in matches:
        vid = m["venue_id"]
        coords = VENUE_COORDS.get(vid)

        if not coords:
            print(f"  No coords for {vid} — skipping weather")
            results.append({**dict(m), "weather": None})
            continue

        lat, lon = coords
        w = fetch_weather(lat, lon, target_date)

        if "error" in w:
            print(f"  {m['label']:20s} — fetch error: {w['error']}")
            results.append({**dict(m), "weather": None})
            continue

        conn.execute("""
            INSERT OR REPLACE INTO weather
            (venue_id, match_date, fetched_at,
             rain_prob_pct, humidity_pct, wind_kmh, cloud_cover_pct,
             temp_celsius, condition, dl_risk)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (vid, target_date, datetime.now().isoformat(),
              w["rain_prob_pct"], w["humidity_pct"], w["wind_kmh"],
              w["cloud_cover_pct"], w["temp_celsius"],
              w["condition"], w["dl_risk"]))

        flag = "RAIN RISK" if w["dl_risk"] == "high" else ("CLOUDY" if w["condition"] == "cloudy" else "OK")
        print(f"  {m['team_a']:20s} vs {m['team_b']:20s}  "
              f"Rain:{w['rain_prob_pct']:3.0f}%  "
              f"Cloud:{w['cloud_cover_pct']:3.0f}%  "
              f"Wind:{w['wind_kmh']:4.1f}kmh  "
              f"Temp:{w['temp_celsius']:4.1f}°C  [{flag}]")
        results.append({**dict(m), "weather": w})

    conn.commit()
    conn.close()
    return results

if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else None
    run(d)
