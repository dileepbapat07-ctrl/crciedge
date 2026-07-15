"""
01_seed_matches.py
Seed the matches table with our verified 193-match schedule (Jul 14 – Dec 31 2026)
"""
import sqlite3, os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "../db/cricket_engine.db")
SQL_PATH = os.path.join(os.path.dirname(__file__), "../db/schema.sql")

# ── Create / connect DB ───────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
with open(SQL_PATH) as f:
    conn.executescript(f.read())
conn.commit()

# ── Match schedule ────────────────────────────────────────────
# (date, label, team_a, team_b, format, series, category, gender, venue_name, city, country)
SCHEDULE = [
    # JULY
    (date(2026,7,14),"2nd ODI","England","India","ODI","India tour of England 2026","International","Men's","Sophia Gardens","Cardiff","England"),
    (date(2026,7,15),"3rd ODI (WI vs NZ)","West Indies","New Zealand","ODI","NZ tour of West Indies 2026","International","Men's","Arnos Vale","St Vincent","West Indies"),
    (date(2026,7,16),"3rd ODI","England","India","ODI","India tour of England 2026","International","Men's","Lord's","London","England"),
    (date(2026,7,17),"4th ODI (WI vs NZ)","West Indies","New Zealand","ODI","NZ tour of West Indies 2026","International","Men's","Arnos Vale","St Vincent","West Indies"),
    (date(2026,7,19),"5th ODI (WI vs NZ)","West Indies","New Zealand","ODI","NZ tour of West Indies 2026","International","Men's","Arnos Vale","St Vincent","West Indies"),
    (date(2026,7,21),"M1 W+M","Oval Invincibles","London Spirit","100-ball","The Hundred 2026","Franchise","Both","The Oval","London","England"),
    (date(2026,7,22),"M2 W+M","Welsh Fire","Southern Brave","100-ball","The Hundred 2026","Franchise","Both","Sophia Gardens","Cardiff","England"),
    (date(2026,7,23),"M3 W+M","Trent Rockets","Birmingham Phoenix","100-ball","The Hundred 2026","Franchise","Both","Trent Bridge","Nottingham","England"),
    (date(2026,7,23),"1st T20I","Zimbabwe","India","T20I","India tour of Zimbabwe 2026","International","Men's","Harare Sports Club","Harare","Zimbabwe"),
    (date(2026,7,23),"Asia Cup M1+M2","India Women","Pakistan Women","T20I","Women's T20 Asia Cup 2026","ACC","Women's","Rangiri Dambulla Stadium","Dambulla","Sri Lanka"),
    (date(2026,7,24),"M4 W+M","London Spirit","Manchester Originals","100-ball","The Hundred 2026","Franchise","Both","Lord's","London","England"),
    (date(2026,7,24),"2nd T20I","Zimbabwe","India","T20I","India tour of Zimbabwe 2026","International","Men's","Harare Sports Club","Harare","Zimbabwe"),
    (date(2026,7,24),"Asia Cup M3+M4","Sri Lanka Women","Bangladesh Women","T20I","Women's T20 Asia Cup 2026","ACC","Women's","Rangiri Dambulla Stadium","Dambulla","Sri Lanka"),
    (date(2026,7,25),"M5 W+M","Sunrisers","Welsh Fire","100-ball","The Hundred 2026","Franchise","Both","Headingley","Leeds","England"),
    (date(2026,7,25),"1st Test D1","West Indies","Pakistan","Test","Pakistan tour of West Indies 2026","International","Men's","Brian Lara Stadium","Tarouba","Trinidad"),
    (date(2026,7,25),"GSL M3","GSL Team A","GSL Team B","T20","Global Super League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,7,26),"M6 W+M","Southern Brave","Oval Invincibles","100-ball","The Hundred 2026","Franchise","Both","The Rose Bowl","Southampton","England"),
    (date(2026,7,26),"3rd T20I","Zimbabwe","India","T20I","India tour of Zimbabwe 2026","International","Men's","Harare Sports Club","Harare","Zimbabwe"),
    (date(2026,7,26),"Asia Cup M5+M6","Nepal Women","UAE Women","T20I","Women's T20 Asia Cup 2026","ACC","Women's","Rangiri Dambulla Stadium","Dambulla","Sri Lanka"),
    (date(2026,7,26),"GSL M4","GSL Team C","GSL Team D","T20","Global Super League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,7,27),"M7 W+M","Birmingham Phoenix","London Spirit","100-ball","The Hundred 2026","Franchise","Both","Edgbaston","Birmingham","England"),
    (date(2026,7,27),"Asia Cup M7+M8","Sri Lanka Women","Malaysia Women","T20I","Women's T20 Asia Cup 2026","ACC","Women's","Rangiri Dambulla Stadium","Dambulla","Sri Lanka"),
    (date(2026,7,27),"GSL M5","GSL Team A","GSL Team C","T20","Global Super League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,7,28),"M8 W+M","Sunrisers","Manchester Originals","100-ball","The Hundred 2026","Franchise","Both","Headingley","Leeds","England"),
    (date(2026,7,28),"Asia Cup M9+M10","Pakistan Women","UAE Women","T20I","Women's T20 Asia Cup 2026","ACC","Women's","Rangiri Dambulla Stadium","Dambulla","Sri Lanka"),
    (date(2026,7,28),"GSL M6","GSL Team B","GSL Team D","T20","Global Super League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,7,28),"LPL M21","Dambulla Sixers","Kandy Falcons","T20","Lanka Premier League 2026","Franchise","Men's","Pallekele International","Kandy","Sri Lanka"),
    (date(2026,7,28),"Asia Cup SF+Final","TBC Women","TBC Women","T20I","Women's T20 Asia Cup 2026","ACC","Women's","Rangiri Dambulla Stadium","Dambulla","Sri Lanka"),
    (date(2026,7,29),"M9 W+M","Trent Rockets","Welsh Fire","100-ball","The Hundred 2026","Franchise","Both","Trent Bridge","Nottingham","England"),
    (date(2026,7,29),"GSL M7","GSL Team A","GSL Team D","T20","Global Super League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,7,30),"M10 W+M","Oval Invincibles","London Spirit","100-ball","The Hundred 2026","Franchise","Both","The Oval","London","England"),
    (date(2026,7,30),"GSL M8","GSL Team B","GSL Team C","T20","Global Super League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,7,31),"M11 W+M","Birmingham Phoenix","Southern Brave","100-ball","The Hundred 2026","Franchise","Both","Edgbaston","Birmingham","England"),
    (date(2026,7,31),"GSL M9","GSL Team C","GSL Team D","T20","Global Super League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    # AUGUST
    (date(2026,8,1),"M12 W+M","Manchester Originals","Trent Rockets","100-ball","The Hundred 2026","Franchise","Both","Old Trafford","Manchester","England"),
    (date(2026,8,1),"GSL SF+Final","GSL Team A","GSL Team B","T20","Global Super League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,8,1),"LPL Eliminator","TBC","TBC","T20","Lanka Premier League 2026","Franchise","Men's","R.Premadasa Stadium","Colombo","Sri Lanka"),
    (date(2026,8,2),"M13 W+M","Welsh Fire","London Spirit","100-ball","The Hundred 2026","Franchise","Both","Sophia Gardens","Cardiff","England"),
    (date(2026,8,2),"2nd Test D1","West Indies","Pakistan","Test","Pakistan tour of West Indies 2026","International","Men's","Brian Lara Stadium","Tarouba","Trinidad"),
    (date(2026,8,3),"M14 W+M","Sunrisers","Oval Invincibles","100-ball","The Hundred 2026","Franchise","Both","Headingley","Leeds","England"),
    (date(2026,8,4),"M15 W+M","Southern Brave","Trent Rockets","100-ball","The Hundred 2026","Franchise","Both","The Rose Bowl","Southampton","England"),
    (date(2026,8,4),"LPL Qualifier Final","TBC","TBC","T20","Lanka Premier League 2026","Franchise","Men's","R.Premadasa Stadium","Colombo","Sri Lanka"),
    (date(2026,8,5),"M16 W+M","Birmingham Phoenix","Manchester Originals","100-ball","The Hundred 2026","Franchise","Both","Edgbaston","Birmingham","England"),
    (date(2026,8,5),"1st ODI","Ireland","Afghanistan","ODI","Afghanistan tour of Ireland 2026","International","Men's","Stormont","Belfast","Ireland"),
    (date(2026,8,6),"M17 W+M","Welsh Fire","Oval Invincibles","100-ball","The Hundred 2026","Franchise","Both","Sophia Gardens","Cardiff","England"),
    (date(2026,8,7),"M18 W+M","London Spirit","Sunrisers","100-ball","The Hundred 2026","Franchise","Both","Lord's","London","England"),
    (date(2026,8,7),"2nd ODI","Ireland","Afghanistan","ODI","Afghanistan tour of Ireland 2026","International","Men's","Stormont","Belfast","Ireland"),
    (date(2026,8,7),"CPL M1","Jamaica Kingsmen","Antigua Falcons","T20","Caribbean Premier League 2026","Franchise","Men's","Arnos Vale","St Vincent","West Indies"),
    (date(2026,8,8),"M19 W+M","Manchester Originals","Southern Brave","100-ball","The Hundred 2026","Franchise","Both","Old Trafford","Manchester","England"),
    (date(2026,8,8),"CPL M2","SKN Patriots","Trinbago KR","T20","Caribbean Premier League 2026","Franchise","Men's","Arnos Vale","St Vincent","West Indies"),
    (date(2026,8,8),"LPL Final","TBC","TBC","T20","Lanka Premier League 2026","Franchise","Men's","R.Premadasa Stadium","Colombo","Sri Lanka"),
    (date(2026,8,9),"M20 W+M","Trent Rockets","Oval Invincibles","100-ball","The Hundred 2026","Franchise","Both","Trent Bridge","Nottingham","England"),
    (date(2026,8,9),"CPL M3","Antigua Falcons","SL Kings","T20","Caribbean Premier League 2026","Franchise","Men's","Arnos Vale","St Vincent","West Indies"),
    (date(2026,8,10),"M21 W+M","Welsh Fire","Birmingham Phoenix","100-ball","The Hundred 2026","Franchise","Both","Sophia Gardens","Cardiff","England"),
    (date(2026,8,10),"3rd ODI","Ireland","Afghanistan","ODI","Afghanistan tour of Ireland 2026","International","Men's","Stormont","Belfast","Ireland"),
    (date(2026,8,11),"M22 W+M","London Spirit","Southern Brave","100-ball","The Hundred 2026","Franchise","Both","Lord's","London","England"),
    (date(2026,8,11),"CPL M4","Jamaica Kingsmen","Barbados Royals","T20","Caribbean Premier League 2026","Franchise","Men's","Sabina Park","Kingston","Jamaica"),
    (date(2026,8,12),"M23 W+M","Sunrisers","Trent Rockets","100-ball","The Hundred 2026","Franchise","Both","Headingley","Leeds","England"),
    (date(2026,8,12),"4th ODI","Ireland","Afghanistan","ODI","Afghanistan tour of Ireland 2026","International","Men's","Stormont","Belfast","Ireland"),
    (date(2026,8,12),"CPL M5","SL Kings","SKN Patriots","T20","Caribbean Premier League 2026","Franchise","Men's","Daren Sammy Stadium","Gros Islet","Saint Lucia"),
    (date(2026,8,13),"M24 W+M","Manchester Originals","Welsh Fire","100-ball","The Hundred 2026","Franchise","Both","Old Trafford","Manchester","England"),
    (date(2026,8,13),"1st Test D1","Australia","Bangladesh","Test","Bangladesh tour of Australia 2026","International","Men's","Marrara Oval","Darwin","Australia"),
    (date(2026,8,13),"CPL M6","Jamaica Kingsmen","Guyana AW","T20","Caribbean Premier League 2026","Franchise","Men's","Sabina Park","Kingston","Jamaica"),
    (date(2026,8,14),"Eliminator W+M","TBC","TBC","100-ball","The Hundred 2026","Franchise","Both","The Oval","London","England"),
    (date(2026,8,14),"5th ODI","Ireland","Afghanistan","ODI","Afghanistan tour of Ireland 2026","International","Men's","Stormont","Belfast","Ireland"),
    (date(2026,8,14),"CPL M7","SL Kings","Antigua Falcons","T20","Caribbean Premier League 2026","Franchise","Men's","Daren Sammy Stadium","Gros Islet","Saint Lucia"),
    (date(2026,8,15),"CPL M8","Jamaica Kingsmen","Trinbago KR","T20","Caribbean Premier League 2026","Franchise","Men's","Sabina Park","Kingston","Jamaica"),
    (date(2026,8,16),"Finals Day W+M","TBC","TBC","100-ball","The Hundred 2026","Franchise","Both","Lord's","London","England"),
    (date(2026,8,16),"CPL M9","SL Kings","Barbados Royals","T20","Caribbean Premier League 2026","Franchise","Men's","Daren Sammy Stadium","Gros Islet","Saint Lucia"),
    (date(2026,8,18),"CPL M10","Jamaica Kingsmen","SKN Patriots","T20","Caribbean Premier League 2026","Franchise","Men's","Sabina Park","Kingston","Jamaica"),
    (date(2026,8,19),"1st Test D1","England","Pakistan","Test","Pakistan tour of England 2026","International","Men's","Headingley","Leeds","England"),
    (date(2026,8,19),"CPL M11","SL Kings","Guyana AW","T20","Caribbean Premier League 2026","Franchise","Men's","Daren Sammy Stadium","Gros Islet","Saint Lucia"),
    (date(2026,8,20),"CPL M12","Antigua Falcons","SKN Patriots","T20","Caribbean Premier League 2026","Franchise","Men's","Sir Vivian Richards Stadium","Antigua","Antigua"),
    (date(2026,8,21),"CPL M13","SL Kings","Jamaica Kingsmen","T20","Caribbean Premier League 2026","Franchise","Men's","Daren Sammy Stadium","Gros Islet","Saint Lucia"),
    (date(2026,8,22),"2nd Test D1","Australia","Bangladesh","Test","Bangladesh tour of Australia 2026","International","Men's","Great Barrier Reef Arena","Mackay","Australia"),
    (date(2026,8,22),"CPL M14","Antigua Falcons","Trinbago KR","T20","Caribbean Premier League 2026","Franchise","Men's","Sir Vivian Richards Stadium","Antigua","Antigua"),
    (date(2026,8,23),"CPL M15","Antigua Falcons","Guyana AW","T20","Caribbean Premier League 2026","Franchise","Men's","Sir Vivian Richards Stadium","Antigua","Antigua"),
    (date(2026,8,25),"CPL M16","Antigua Falcons","Barbados Royals","T20","Caribbean Premier League 2026","Franchise","Men's","Sir Vivian Richards Stadium","Antigua","Antigua"),
    (date(2026,8,26),"CPL M17","Trinbago KR","SL Kings","T20","Caribbean Premier League 2026","Franchise","Men's","Brian Lara Stadium","Tarouba","Trinidad"),
    (date(2026,8,27),"2nd Test D1","England","Pakistan","Test","Pakistan tour of England 2026","International","Men's","Lord's","London","England"),
    (date(2026,8,27),"CPL M18","SKN Patriots","Jamaica Kingsmen","T20","Caribbean Premier League 2026","Franchise","Men's","Warner Park","Basseterre","St Kitts"),
    (date(2026,8,28),"CPL M19","Trinbago KR","Barbados Royals","T20","Caribbean Premier League 2026","Franchise","Men's","Brian Lara Stadium","Tarouba","Trinidad"),
    (date(2026,8,29),"CPL M20","Trinbago KR","Guyana AW","T20","Caribbean Premier League 2026","Franchise","Men's","Brian Lara Stadium","Tarouba","Trinidad"),
    (date(2026,8,30),"CPL M21","SKN Patriots","Antigua Falcons","T20","Caribbean Premier League 2026","Franchise","Men's","Warner Park","Basseterre","St Kitts"),
    (date(2026,8,31),"CPL M22","Trinbago KR","Jamaica Kingsmen","T20","Caribbean Premier League 2026","Franchise","Men's","Brian Lara Stadium","Tarouba","Trinidad"),
    # SEPTEMBER
    (date(2026,9,1),"1st ODI","Bangladesh","India","ODI","India tour of Bangladesh 2026","International","Men's","Sher-e-Bangla Stadium","Dhaka","Bangladesh"),
    (date(2026,9,1),"CPL M23","SKN Patriots","Barbados Royals","T20","Caribbean Premier League 2026","Franchise","Men's","Warner Park","Basseterre","St Kitts"),
    (date(2026,9,2),"CPL M24","Trinbago KR","Antigua Falcons","T20","Caribbean Premier League 2026","Franchise","Men's","Brian Lara Stadium","Tarouba","Trinidad"),
    (date(2026,9,3),"2nd ODI","Bangladesh","India","ODI","India tour of Bangladesh 2026","International","Men's","Sher-e-Bangla Stadium","Dhaka","Bangladesh"),
    (date(2026,9,3),"CPL M25","SKN Patriots","SL Kings","T20","Caribbean Premier League 2026","Franchise","Men's","Warner Park","Basseterre","St Kitts"),
    (date(2026,9,4),"3rd Test D1","England","Pakistan","Test","Pakistan tour of England 2026","International","Men's","Edgbaston","Birmingham","England"),
    (date(2026,9,4),"CPL M26","Guyana AW","Jamaica Kingsmen","T20","Caribbean Premier League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,9,5),"WCPL M1","Barbados Tridents W","Trinbago KR W","T20","WCPL 2026","Franchise","Women's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,5),"CPL M27","Barbados Royals","Trinbago KR","T20","Caribbean Premier League 2026","Franchise","Men's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,6),"3rd ODI","Bangladesh","India","ODI","India tour of Bangladesh 2026","International","Men's","Sher-e-Bangla Stadium","Dhaka","Bangladesh"),
    (date(2026,9,6),"WCPL M2","Guyana AW W","Jamaica Empress W","T20","WCPL 2026","Franchise","Women's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,6),"CPL M28","Guyana AW","SKN Patriots","T20","Caribbean Premier League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,9,6),"CPL M29","Barbados Royals","SL Kings","T20","Caribbean Premier League 2026","Franchise","Men's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,8),"CPL M30","Guyana AW","Antigua Falcons","T20","Caribbean Premier League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,9,9),"1st T20I","Bangladesh","India","T20I","India tour of Bangladesh 2026","International","Men's","Matiur Rahman Stadium","Chattogram","Bangladesh"),
    (date(2026,9,9),"CPL M31","Guyana AW","SL Kings","T20","Caribbean Premier League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,9,10),"WCPL M3","Jamaica Empress W","Trinbago KR W","T20","WCPL 2026","Franchise","Women's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,10),"CPL M32","Barbados Royals","SKN Patriots","T20","Caribbean Premier League 2026","Franchise","Men's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,11),"2nd T20I","Bangladesh","India","T20I","India tour of Bangladesh 2026","International","Men's","Matiur Rahman Stadium","Chattogram","Bangladesh"),
    (date(2026,9,11),"CPL M33","Guyana AW","Trinbago KR","T20","Caribbean Premier League 2026","Franchise","Men's","Providence Stadium","Providence","Guyana"),
    (date(2026,9,12),"WCPL M4","Guyana AW W","Trinbago KR W","T20","WCPL 2026","Franchise","Women's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,12),"CPL M34","Barbados Royals","Jamaica Kingsmen","T20","Caribbean Premier League 2026","Franchise","Men's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,13),"3rd T20I","Bangladesh","India","T20I","India tour of Bangladesh 2026","International","Men's","Matiur Rahman Stadium","Chattogram","Bangladesh"),
    (date(2026,9,13),"CPL M35","Barbados Royals","Guyana AW","T20","Caribbean Premier League 2026","Franchise","Men's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,15),"1st ODI","England","Sri Lanka","ODI","Sri Lanka tour of England 2026","International","Men's","The Oval","London","England"),
    (date(2026,9,16),"CPL Eliminator","TBC","TBC","T20","Caribbean Premier League 2026","Franchise","Men's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,17),"2nd ODI","England","Sri Lanka","ODI","Sri Lanka tour of England 2026","International","Men's","Edgbaston","Birmingham","England"),
    (date(2026,9,17),"CPL Qualifier 1","TBC","TBC","T20","Caribbean Premier League 2026","Franchise","Men's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,17),"WCPL Playoff","TBC W","TBC W","T20","WCPL 2026","Franchise","Women's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,18),"CPL Qualifier 2","TBC","TBC","T20","Caribbean Premier League 2026","Franchise","Men's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,19),"3rd ODI","England","Sri Lanka","ODI","Sri Lanka tour of England 2026","International","Men's","Lord's","London","England"),
    (date(2026,9,20),"CPL Final","TBC","TBC","T20","Caribbean Premier League 2026","Franchise","Men's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,20),"WCPL Final","TBC W","TBC W","T20","WCPL 2026","Franchise","Women's","Kensington Oval","Bridgetown","Barbados"),
    (date(2026,9,22),"1st T20I","England","Sri Lanka","T20I","Sri Lanka tour of England 2026","International","Men's","The Rose Bowl","Southampton","England"),
    (date(2026,9,24),"1st ODI","South Africa","Australia","ODI","Australia tour of South Africa 2026","International","Men's","Newlands","Cape Town","South Africa"),
    (date(2026,9,25),"2nd T20I","England","Sri Lanka","T20I","Sri Lanka tour of England 2026","International","Men's","Trent Bridge","Nottingham","England"),
    (date(2026,9,27),"3rd T20I","England","Sri Lanka","T20I","Sri Lanka tour of England 2026","International","Men's","Headingley","Leeds","England"),
    (date(2026,9,27),"1st ODI","India","West Indies","ODI","West Indies tour of India 2026","International","Men's","Wankhede Stadium","Mumbai","India"),
    # OCTOBER
    (date(2026,10,1),"2nd ODI","India","West Indies","ODI","West Indies tour of India 2026","International","Men's","Eden Gardens","Kolkata","India"),
    (date(2026,10,3),"1st Test D1","South Africa","Australia","Test","Australia tour of South Africa 2026","International","Men's","SuperSport Park","Centurion","South Africa"),
    (date(2026,10,4),"3rd ODI","India","West Indies","ODI","West Indies tour of India 2026","International","Men's","Rajiv Gandhi Stadium","Hyderabad","India"),
    (date(2026,10,7),"1st T20I","India","West Indies","T20I","West Indies tour of India 2026","International","Men's","M Chinnaswamy Stadium","Bangalore","India"),
    (date(2026,10,9),"2nd T20I","India","West Indies","T20I","West Indies tour of India 2026","International","Men's","Sawai Mansingh Stadium","Jaipur","India"),
    (date(2026,10,11),"2nd Test D1","South Africa","Australia","Test","Australia tour of South Africa 2026","International","Men's","Newlands","Cape Town","South Africa"),
    (date(2026,10,12),"3rd T20I","India","West Indies","T20I","West Indies tour of India 2026","International","Men's","MA Chidambaram Stadium","Chennai","India"),
    (date(2026,10,14),"4th T20I","India","West Indies","T20I","West Indies tour of India 2026","International","Men's","HPCA Stadium","Dharamshala","India"),
    (date(2026,10,17),"5th T20I","India","West Indies","T20I","West Indies tour of India 2026","International","Men's","Narendra Modi Stadium","Ahmedabad","India"),
    (date(2026,10,20),"3rd Test D1","South Africa","Australia","Test","Australia tour of South Africa 2026","International","Men's","The Wanderers","Johannesburg","South Africa"),
    (date(2026,10,22),"1st T20I","New Zealand","India","T20I","India tour of New Zealand 2026","International","Men's","Eden Park","Auckland","New Zealand"),
    (date(2026,10,25),"2nd T20I","New Zealand","India","T20I","India tour of New Zealand 2026","International","Men's","Bay Oval","Mount Maunganui","New Zealand"),
    (date(2026,10,28),"3rd T20I","New Zealand","India","T20I","India tour of New Zealand 2026","International","Men's","Seddon Park","Hamilton","New Zealand"),
    (date(2026,10,29),"WBBL M1+M2","Melbourne Renegades W","Sydney Thunder W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Junction Oval","Melbourne","Australia"),
    (date(2026,10,30),"WBBL M3","Brisbane Heat W","Sydney Sixers W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Allan Border Field","Brisbane","Australia"),
    (date(2026,10,31),"4th T20I","New Zealand","India","T20I","India tour of New Zealand 2026","International","Men's","University Oval","Dunedin","New Zealand"),
    (date(2026,10,31),"WBBL M4+M5","Adelaide Strikers W","Melbourne Stars W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Karen Rolton Oval","Adelaide","Australia"),
    # NOVEMBER
    (date(2026,11,1),"5th T20I","New Zealand","India","T20I","India tour of New Zealand 2026","International","Men's","Westpac Stadium","Wellington","New Zealand"),
    (date(2026,11,1),"WBBL M6+M7","Sydney Thunder W","Brisbane Heat W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Drummoyne Oval","Sydney","Australia"),
    (date(2026,11,2),"WBBL M8","Melbourne Stars W","Perth Scorchers W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Junction Oval","Melbourne","Australia"),
    (date(2026,11,4),"1st ODI","New Zealand","India","ODI","India tour of New Zealand 2026","International","Men's","Eden Park","Auckland","New Zealand"),
    (date(2026,11,4),"WBBL M9","Hobart Hurricanes W","Melbourne Renegades W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Bellerive Oval","Hobart","Australia"),
    (date(2026,11,5),"WBBL M10+M11","Adelaide Strikers W","Brisbane Heat W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Drummoyne Oval","Sydney","Australia"),
    (date(2026,11,6),"2nd ODI","New Zealand","India","ODI","India tour of New Zealand 2026","International","Men's","Hagley Oval","Christchurch","New Zealand"),
    (date(2026,11,6),"WBBL M12","Melbourne Stars W","Sydney Sixers W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Junction Oval","Melbourne","Australia"),
    (date(2026,11,7),"WBBL M13+M14","Melbourne Renegades W","Adelaide Strikers W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Junction Oval","Melbourne","Australia"),
    (date(2026,11,8),"3rd ODI","New Zealand","India","ODI","India tour of New Zealand 2026","International","Men's","Basin Reserve","Wellington","New Zealand"),
    (date(2026,11,8),"WBBL M15+M16 (Sydney Smash 1)","Sydney Sixers W","Sydney Thunder W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","North Sydney Oval","Sydney","Australia"),
    (date(2026,11,9),"4th ODI","New Zealand","India","ODI","India tour of New Zealand 2026","International","Men's","McLean Park","Napier","New Zealand"),
    (date(2026,11,10),"WBBL M17","Hobart Hurricanes W","Adelaide Strikers W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Bellerive Oval","Hobart","Australia"),
    (date(2026,11,11),"5th ODI","New Zealand","India","ODI","India tour of New Zealand 2026","International","Men's","Saxton Oval","Nelson","New Zealand"),
    (date(2026,11,11),"WBBL M18","Perth Scorchers W","Sydney Thunder W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","WACA Ground","Perth","Australia"),
    (date(2026,11,12),"WBBL M19+M20","Melbourne Stars W","Brisbane Heat W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Junction Oval","Melbourne","Australia"),
    (date(2026,11,14),"WBBL M21+M22","Hobart Hurricanes W","Brisbane Heat W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Bellerive Oval","Hobart","Australia"),
    (date(2026,11,15),"1st Test D1","South Africa","Bangladesh","Test","Bangladesh tour of South Africa 2026","International","Men's","SuperSport Park","Centurion","South Africa"),
    (date(2026,11,15),"WBBL M23","Sydney Sixers W","Melbourne Renegades W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","North Sydney Oval","Sydney","Australia"),
    (date(2026,11,16),"WBBL M24","Sydney Thunder W","Melbourne Stars W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Drummoyne Oval","Sydney","Australia"),
    (date(2026,11,17),"WBBL M25","Adelaide Strikers W","Sydney Sixers W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Karen Rolton Oval","Adelaide","Australia"),
    (date(2026,11,19),"1st Test D1","New Zealand","India","Test","India tour of New Zealand 2026","International","Men's","Basin Reserve","Wellington","New Zealand"),
    (date(2026,11,19),"WBBL M26+M27","Hobart Hurricanes W","Perth Scorchers W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Allan Border Field","Brisbane","Australia"),
    (date(2026,11,20),"WBBL M28","Adelaide Strikers W","Melbourne Renegades W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Adelaide Oval","Adelaide","Australia"),
    (date(2026,11,21),"WBBL M29+M30","Hobart Hurricanes W","Sydney Thunder W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Bellerive Oval","Hobart","Australia"),
    (date(2026,11,22),"WBBL M31+M32 (Melbourne Derby)","Melbourne Stars W","Melbourne Renegades W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Junction Oval","Melbourne","Australia"),
    (date(2026,11,25),"WBBL M33","Melbourne Renegades W","Brisbane Heat W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Junction Oval","Melbourne","Australia"),
    (date(2026,11,26),"WBBL M34+M35","Sydney Thunder W","Adelaide Strikers W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","North Sydney Oval","Sydney","Australia"),
    (date(2026,11,27),"2nd Test D1","New Zealand","India","Test","India tour of New Zealand 2026","International","Men's","Hagley Oval","Christchurch","New Zealand"),
    (date(2026,11,27),"WBBL M36","Perth Scorchers W","Hobart Hurricanes W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","WACA Ground","Perth","Australia"),
    (date(2026,11,28),"WBBL M37+M38 (Derby 2 + Smash 2)","Melbourne Renegades W","Melbourne Stars W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Junction Oval","Melbourne","Australia"),
    (date(2026,11,29),"WBBL M39+M40 (Final reg season)","Brisbane Heat W","Perth Scorchers W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","Karen Rolton Oval","Adelaide","Australia"),
    # DECEMBER
    (date(2026,12,1),"WBBL Knockout","TBC W","TBC W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","TBC","TBC","Australia"),
    (date(2026,12,3),"WBBL Challenger","TBC W","TBC W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","TBC","TBC","Australia"),
    (date(2026,12,5),"WBBL Final","TBC W","TBC W","T20","WBBL 2026-27 (Season 12)","Domestic","Women's","TBC","TBC","Australia"),
    (date(2026,12,12),"BBL M1","Melbourne Renegades","Perth Scorchers","T20","BBL 2026-27 (Season 16)","Domestic","Men's","MA Chidambaram Stadium","Chennai","India"),
    (date(2026,12,15),"BBL M2","Brisbane Heat","Sydney Sixers","T20","BBL 2026-27 (Season 16)","Domestic","Men's","The Gabba","Brisbane","Australia"),
    (date(2026,12,16),"BBL M3","Sydney Thunder","Adelaide Strikers","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Corroboree Group Oval Manuka","Canberra","Australia"),
    (date(2026,12,17),"BBL M4","Hobart Hurricanes","Brisbane Heat","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Ninja Stadium","Hobart","Australia"),
    (date(2026,12,18),"BBL M5","Melbourne Stars","Adelaide Strikers","T20","BBL 2026-27 (Season 16)","Domestic","Men's","MCG","Melbourne","Australia"),
    (date(2026,12,19),"BBL M6","Sydney Thunder","Sydney Sixers","T20","BBL 2026-27 (Season 16)","Domestic","Men's","ENGIE Stadium","Sydney","Australia"),
    (date(2026,12,20),"BBL M7","Perth Scorchers","Hobart Hurricanes","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Optus Stadium","Perth","Australia"),
    (date(2026,12,21),"BBL M8","Melbourne Stars","Brisbane Heat","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Junction Oval","Melbourne","Australia"),
    (date(2026,12,22),"BBL M9","Sydney Sixers","Melbourne Renegades","T20","BBL 2026-27 (Season 16)","Domestic","Men's","SCG","Sydney","Australia"),
    (date(2026,12,23),"BBL M10","Adelaide Strikers","Sydney Thunder","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Adelaide Oval","Adelaide","Australia"),
    (date(2026,12,24),"BBL M11","Melbourne Renegades","Hobart Hurricanes","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Junction Oval","Melbourne","Australia"),
    (date(2026,12,26),"BBL M12","Sydney Sixers","Brisbane Heat","T20","BBL 2026-27 (Season 16)","Domestic","Men's","SCG","Sydney","Australia"),
    (date(2026,12,26),"BBL M13","Perth Scorchers","Melbourne Stars","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Optus Stadium","Perth","Australia"),
    (date(2026,12,27),"BBL M14","Sydney Thunder","Melbourne Renegades","T20","BBL 2026-27 (Season 16)","Domestic","Men's","ENGIE Stadium","Sydney","Australia"),
    (date(2026,12,28),"BBL M15","Brisbane Heat","Adelaide Strikers","T20","BBL 2026-27 (Season 16)","Domestic","Men's","The Gabba","Brisbane","Australia"),
    (date(2026,12,29),"BBL M16","Hobart Hurricanes","Melbourne Stars","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Ninja Stadium","Hobart","Australia"),
    (date(2026,12,30),"BBL M17","Perth Scorchers","Sydney Thunder","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Optus Stadium","Perth","Australia"),
    (date(2026,12,31),"BBL M18","Adelaide Strikers","Melbourne Stars","T20","BBL 2026-27 (Season 16)","Domestic","Men's","Adelaide Oval","Adelaide","Australia"),
]

def make_match_id(dt, team_a, team_b, fmt, label):
    a = team_a[:3].upper().replace(" ", "")
    b = team_b[:3].upper().replace(" ", "")
    l = label[:6].replace(" ", "").upper()
    return f"{dt.strftime('%Y%m%d')}-{a}-{b}-{fmt[:3].upper()}-{l}"

def make_venue_id(name, city):
    return f"{name[:15].lower().replace(' ','-')}-{city[:10].lower().replace(' ','-')}"

# Seed venues + matches
venues_seen = set()
step = 0
for row in SCHEDULE:
    dt, label, ta, tb, fmt, series, cat, gender, vname, city, country = row
    step += 1
    phase = 1 if step <= 130 else 2
    mid = make_match_id(dt, ta, tb, fmt, label)
    vid = make_venue_id(vname, city)

    if vid not in venues_seen:
        conn.execute("""
            INSERT OR IGNORE INTO venues(venue_id, name, city, country)
            VALUES (?,?,?,?)
        """, (vid, vname, city, country))
        venues_seen.add(vid)

    conn.execute("""
        INSERT OR IGNORE INTO matches
        (match_id, date, step, phase, label, team_a, team_b, format,
         series, category, gender, venue_id, city, country)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (mid, dt.isoformat(), step, phase, label, ta, tb, fmt,
          series, cat, gender, vid, city, country))

conn.commit()

# Verify
n_matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
n_venues  = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
print(f"Seeded {n_matches} matches across {n_venues} venues")
print(f"Phase 1: {conn.execute('SELECT COUNT(*) FROM matches WHERE phase=1').fetchone()[0]} matches (2% growth)")
print(f"Phase 2: {conn.execute('SELECT COUNT(*) FROM matches WHERE phase=2').fetchone()[0]} matches (1% growth)")

# Monthly breakdown
print("\nMonthly distribution:")
rows = conn.execute("""
    SELECT strftime('%b %Y', date) as mo, COUNT(*) as cnt
    FROM matches GROUP BY mo ORDER BY date
""").fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]} bets")

conn.close()
print(f"\nDB: {os.path.abspath(DB_PATH)}")
