"""
elo_config.py
All ELO engine constants and lookup tables.
Edit here to tune the model — no other files need changing.
"""

# ── Core ELO parameters ───────────────────────────────────────
ELO_START           = 1500.0   # starting rating for all teams
ELO_SCALE           = 400      # chess default — controls how steep the curve is
HOME_ADVANTAGE      = 100      # rating points added to home team before expected score calc
NEUTRAL_ADVANTAGE   = 0        # UAE, Ireland, Sri Lanka as neutral hosts
DATA_START_YEAR     = 2020     # only process matches from Jan 1 2020 onwards

# ── K-factors by match type ───────────────────────────────────
# Higher K = rating changes faster after each match
K_FACTORS = {
    "icc_event":    48,    # World Cups, Champions Trophy, Asia Cup finals
    "bilateral":    32,    # standard bilateral series
    "domestic":     24,    # CPL, BBL, WBBL, The Hundred, LPL
    "associate":    16,    # matches involving associate nations
}

# ── Formats we track ─────────────────────────────────────────
FORMATS = ["Test", "ODI", "T20I", "T20"]

# Cricsheet uses different format labels — map them
CRICSHEET_FORMAT_MAP = {
    "T20":   "T20I",   # international T20
    "ODI":   "ODI",
    "Test":  "Test",
    "IT20":  "T20",    # domestic/franchise T20 (BBL, CPL etc)
}

# ── Team name normalisation ───────────────────────────────────
# Cricsheet uses varying names — map all to our canonical names
TEAM_NAME_MAP = {
    # International Men
    "India":                    "India",
    "England":                  "England",
    "Australia":                "Australia",
    "Pakistan":                 "Pakistan",
    "West Indies":              "West Indies",
    "New Zealand":              "New Zealand",
    "South Africa":             "South Africa",
    "Sri Lanka":                "Sri Lanka",
    "Bangladesh":               "Bangladesh",
    "Afghanistan":              "Afghanistan",
    "Zimbabwe":                 "Zimbabwe",
    "Ireland":                  "Ireland",
    "Scotland":                 "Scotland",
    "Netherlands":              "Netherlands",
    "Namibia":                  "Namibia",
    "Uganda":                   "Uganda",
    "Oman":                     "Oman",
    "Papua New Guinea":         "Papua New Guinea",
    "UAE":                      "UAE",

    # International Women
    "India Women":              "India Women",
    "England Women":            "England Women",
    "Australia Women":          "Australia Women",
    "South Africa Women":       "South Africa Women",
    "New Zealand Women":        "New Zealand Women",
    "West Indies Women":        "West Indies Women",
    "Pakistan Women":           "Pakistan Women",
    "Sri Lanka Women":          "Sri Lanka Women",
    "Bangladesh Women":         "Bangladesh Women",
    "India Women's":            "India Women",
    "England Women's":          "England Women",
    "Australia Women's":        "Australia Women",

    # CPL teams (name changes over years)
    "Jamaica Tallawahs":        "Jamaica Kingsmen",    # rebranded 2026
    "Jamaica Kingsmen":         "Jamaica Kingsmen",
    "Trinbago Knight Riders":   "Trinbago KR",
    "Trinbago KR":              "Trinbago KR",
    "Saint Lucia Kings":        "SL Kings",
    "Saint Lucia Zouks":        "SL Kings",            # old name
    "SL Kings":                 "SL Kings",
    "Barbados Royals":          "Barbados Royals",
    "Barbados Tridents":        "Barbados Royals",     # rebranded
    "Guyana Amazon Warriors":   "Guyana AW",
    "Guyana AW":                "Guyana AW",
    "St Kitts and Nevis Patriots": "SKN Patriots",
    "SKN Patriots":             "SKN Patriots",
    "Antigua & Barbuda Falcons":"Antigua Falcons",
    "Antigua Falcons":          "Antigua Falcons",
    "Jamaica Kingsmen":         "Jamaica Kingsmen",

    # WCPL
    "Barbados Royals Women":    "Barbados Tridents W",
    "Barbados Tridents Women":  "Barbados Tridents W",
    "Trinbago Knight Riders Women": "Trinbago KR W",
    "Guyana Amazon Warriors Women": "Guyana AW W",
    "Jamaica Tallawahs Women":  "Jamaica Empress W",

    # BBL
    "Melbourne Renegades":      "Melbourne Renegades",
    "Perth Scorchers":          "Perth Scorchers",
    "Brisbane Heat":            "Brisbane Heat",
    "Sydney Sixers":            "Sydney Sixers",
    "Sydney Thunder":           "Sydney Thunder",
    "Adelaide Strikers":        "Adelaide Strikers",
    "Melbourne Stars":          "Melbourne Stars",
    "Hobart Hurricanes":        "Hobart Hurricanes",

    # WBBL
    "Melbourne Renegades Women": "Melbourne Renegades W",
    "Perth Scorchers Women":    "Perth Scorchers W",
    "Brisbane Heat Women":      "Brisbane Heat W",
    "Sydney Sixers Women":      "Sydney Sixers W",
    "Sydney Thunder Women":     "Sydney Thunder W",
    "Adelaide Strikers Women":  "Adelaide Strikers W",
    "Melbourne Stars Women":    "Melbourne Stars W",
    "Hobart Hurricanes Women":  "Hobart Hurricanes W",

    # The Hundred
    "Oval Invincibles":         "Oval Invincibles",
    "London Spirit":            "London Spirit",
    "Welsh Fire":               "Welsh Fire",
    "Southern Brave":           "Southern Brave",
    "Trent Rockets":            "Trent Rockets",
    "Birmingham Phoenix":       "Birmingham Phoenix",
    "Manchester Originals":     "Manchester Originals",
    "Northern Superchargers":   "Sunrisers",           # rebranded 2024
    "Sunrisers":                "Sunrisers",
    "Oval Invincibles Women":   "Oval Invincibles W",
    "London Spirit Women":      "London Spirit W",
    "Welsh Fire Women":         "Welsh Fire W",
    "Southern Brave Women":     "Southern Brave W",
    "Trent Rockets Women":      "Trent Rockets W",
    "Birmingham Phoenix Women": "Birmingham Phoenix W",
    "Manchester Originals Women":"Manchester Originals W",
    "Northern Superchargers Women":"Sunrisers W",
    "Sunrisers Women":          "Sunrisers W",

    # LPL
    "Dambulla Giants":          "Dambulla Sixers",
    "Dambulla Sixers":          "Dambulla Sixers",
    "Colombo Stars":            "Colombo Stars",
    "Kandy Falcons":            "Kandy Falcons",
    "Galle Gladiators":         "Galle Gladiators",
    "Jaffna Kings":             "Jaffna Kings",

    # PSL
    "Karachi Kings":            "Karachi Kings",
    "Lahore Qalandars":         "Lahore Qalandars",
    "Peshawar Zalmi":           "Peshawar Zalmi",
    "Quetta Gladiators":        "Quetta Gladiators",
    "Islamabad United":         "Islamabad United",
    "Multan Sultans":           "Multan Sultans",
}

# ── Team type classification ──────────────────────────────────
INTERNATIONAL_TEAMS = {
    "India","England","Australia","Pakistan","West Indies","New Zealand",
    "South Africa","Sri Lanka","Bangladesh","Afghanistan","Zimbabwe","Ireland",
    "Scotland","Netherlands","Namibia","Uganda","Oman","Papua New Guinea","UAE",
    "India Women","England Women","Australia Women","South Africa Women",
    "New Zealand Women","West Indies Women","Pakistan Women","Sri Lanka Women",
    "Bangladesh Women",
}

# ── ICC events (get higher K factor) ─────────────────────────
ICC_EVENT_KEYWORDS = [
    "world cup","world twenty20","wt20","champions trophy",
    "asia cup","icc","womens t20 world cup","u19 world cup",
]

# ── Countries to detect home advantage ───────────────────────
HOME_COUNTRY_MAP = {
    "India":         ["India"],
    "England":       ["England","United Kingdom","UK","Wales","Scotland"],
    "Australia":     ["Australia"],
    "Pakistan":      ["Pakistan"],
    "West Indies":   ["West Indies","Barbados","Jamaica","Trinidad","Guyana",
                      "Antigua","St Kitts","St Lucia","Grenada"],
    "New Zealand":   ["New Zealand"],
    "South Africa":  ["South Africa"],
    "Sri Lanka":     ["Sri Lanka"],
    "Bangladesh":    ["Bangladesh"],
    "Afghanistan":   ["Afghanistan"],
    "Zimbabwe":      ["Zimbabwe"],
    "Ireland":       ["Ireland"],
    # Franchise — always neutral
}

# ── ELO delta → factor score (0–10) ──────────────────────────
def elo_delta_to_score(delta: float) -> float:
    """
    Convert ELO rating difference to a 0–10 factor score.
    delta = team_a_elo - team_b_elo (positive = team_a stronger)
    Score of 5.0 = equal teams
    Score of 9.0 = +200 ELO gap (very dominant)
    Score of 1.0 = -200 ELO gap (heavy underdog)
    """
    # Sigmoid-like mapping
    # +300 → ~9.5  +200 → ~8.5  +100 → ~6.8
    #    0 → 5.0  -100 → ~3.2  -200 → ~1.5  -300 → ~0.5
    import math
    score = 10 / (1 + math.exp(-delta / 150))
    return round(max(0.5, min(9.5, score)), 2)

def expected_score(rating_a: float, rating_b: float,
                   home_team: str = None, team_a: str = None) -> float:
    """
    Expected score for team_a vs team_b.
    Returns probability 0–1 that team_a wins.
    """
    adj_b = rating_b
    adj_a = rating_a
    if home_team == team_a:
        adj_a += HOME_ADVANTAGE
    elif home_team is not None and home_team != team_a:
        adj_b += HOME_ADVANTAGE
    return 1 / (1 + 10 ** ((adj_b - adj_a) / ELO_SCALE))

def k_factor(match_type: str, team_a: str, team_b: str) -> float:
    """Determine K factor from match context."""
    if match_type == "icc_event":
        return K_FACTORS["icc_event"]
    ta_intl = team_a in INTERNATIONAL_TEAMS
    tb_intl = team_b in INTERNATIONAL_TEAMS
    if ta_intl and tb_intl:
        return K_FACTORS["bilateral"]
    if not ta_intl and not tb_intl:
        return K_FACTORS["domestic"]
    return K_FACTORS["associate"]
