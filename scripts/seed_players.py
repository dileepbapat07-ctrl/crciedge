"""
player_engine/seed_players.py
===============================
Master player database seed. One record per player.
No format/team duplication.

test_stats = (matches, runs, avg, hs, 100s, 50s, wkts, bowl_avg)  — 8 elements
odi_stats  = (matches, runs, avg, sr, hs, 50s, 100s, wkts, bowl_avg, econ)  — 10 elements
t20_stats  = (matches, runs, avg, sr, hs, 50s, 100s, wkts, bowl_avg, econ, bowl_sr) — 11 elements
"""
import sqlite3, os, datetime

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB    = os.path.join(ROOT, "db", "player_engine.db")
TODAY = datetime.date.today().isoformat()

T = lambda *a: a   # shorthand to build tuples clearly

# ─────────────────────────────────────────────────────────────────────
# PLAYER ENTRIES
# (pid, name, short, nationality, franchise, role, bat, bowl, pos, key, espn, aliases,
#  t20_stats, odi_stats, test_stats)
# ─────────────────────────────────────────────────────────────────────
PLAYERS = [

# ══════════════════════════════════════════════════════════════════
# INDIA
# ══════════════════════════════════════════════════════════════════
("rohit-sharma-ind","Rohit Sharma","Rohit","India",None,"bat","rhb",None,1,1,"34102","Rohit,Hitman",
 T(159,4231,32.4,143.8,118,22,4,None,None,None,None),
 T(264,10709,49.0,92.1,264,55,32,None,None,None),
 T(67,4369,40.6,179,12,30,None,None)),

("gill-shubman-ind","Shubman Gill","Gill","India",None,"bat","rhb",None,2,1,"1175543","Gill,Shubman",
 T(95,3182,38.3,154.2,126,18,4,None,None,None,None),
 T(99,3965,55.8,105.2,208,24,10,None,None,None),
 T(28,1842,40.9,162,4,10,None,None)),

("kohli-virat-ind","Virat Kohli","Kohli","India",None,"bat","rhb",None,3,1,"253802","Kohli,King Kohli,VK",
 T(125,4188,52.7,138.8,122,38,5,None,None,None,None),
 T(295,13906,59.1,93.4,183,72,50,None,None,None),
 T(123,9230,48.0,254,30,65,None,None)),

("shreyas-iyer-ind","Shreyas Iyer","Iyer","India",None,"bat","rhb",None,4,1,"1078680","Iyer,Shreyas",
 T(98,2574,32.5,136.8,96,14,1,None,None,None,None),
 T(75,2745,44.3,95.2,113,19,7,None,None,None),
 T(22,1422,37.4,105,3,8,None,None)),

("rahul-kl-ind","KL Rahul","KL Rahul","India",None,"wk","rhb",None,1,1,"422108","KL Rahul,Rahul,Lokesh Rahul",
 T(72,2265,38.4,136.4,110,13,2,None,None,None,None),
 T(68,2060,46.6,91.4,112,14,5,None,None,None),
 T(52,2942,39.2,100,6,18,None,None)),

("bumrah-jasprit-ind","Jasprit Bumrah","Bumrah","India",None,"bowl","rhb","rf",9,1,"625383","Bumrah,JBumrah",
 T(75,None,None,None,None,None,None,98,14.4,6.2,11.6),
 T(88,None,None,None,None,None,None,182,20.8,4.6),
 T(42,None,None,None,None,None,178,18.4)),

("hardik-pandya-ind","Hardik Pandya","Hardik","India",None,"all","rhb","rf",6,1,"625371","Hardik,HP",
 T(112,2484,34.2,148.6,75,14,0,148,24.8,8.8,16.8),
 T(96,1584,34.2,94.6,92,8,0,128,28.4,5.8),
 T(18,484,22.4,91,1,2,18,38.4)),

("tilak-varma-ind","Tilak Varma","Tilak","India",None,"all","lhb","offbreak",3,1,"1311892","Tilak,Varma",
 T(58,1624,36.2,152.8,82,8,2,None,None,None,None),
 T(18,524,32.8,94.2,82,4,0,None,None,None),
 None),

("abhishek-sharma-ind","Abhishek Sharma","ABSharma","India",None,"all","lhb","sla",1,1,"1302906","Abhishek,Abhishek Sharma",
 T(54,1622,32.2,174.8,124,8,2,12,28.4,7.8,21.8),
 T(18,486,30.4,92.4,88,4,0,None,None,None),
 None),

("axar-patel-ind","Axar Patel","Axar","India",None,"all","lhb","sla",7,1,"695043","Axar,AP",
 T(68,984,28.4,148.6,64,4,0,72,24.8,6.8,21.8),
 T(72,1124,24.2,98.4,82,4,2,96,28.4,4.8),
 T(18,484,22.4,72,0,2,52,38.4)),

("kuldeep-yadav-ind","Kuldeep Yadav","Kuldeep","India",None,"bowl","lhb","legspin",10,1,"581392","Kuldeep,Kulcha",
 T(48,None,None,None,None,None,None,82,16.4,6.4,15.4),
 T(98,None,None,None,None,None,None,182,24.8,4.8),
 T(28,None,None,None,None,None,72,28.4)),

("arshdeep-singh-ind","Arshdeep Singh","Arshdeep","India",None,"bowl","lhb","lf",10,1,"1259596","Arshdeep",
 T(72,None,None,None,None,None,None,98,18.4,7.8,14.2),
 T(38,None,None,None,None,None,None,52,28.4,5.4),
 None),

("washington-sundar-ind","Washington Sundar","WSundar","India",None,"all","rhb","offbreak",7,0,"1078968","Washington,Sundar,WS",
 T(42,484,18.2,132.6,42,0,0,52,24.8,6.8,21.8),
 T(48,784,22.4,74.2,75,4,0,52,28.4,4.8),
 T(14,484,22.4,58,0,2,18,38.4)),

("shivam-dube-ind","Shivam Dube","Dube","India",None,"all","lhb","rf",5,0,"1228270","Dube,Shivam Dube",
 T(32,714,28.4,145.8,62,2,0,14,38.4,8.8,26.2),
 None, None),

("varun-chakravarthy-ind","Varun Chakaravarthy","VarunC","India",None,"bowl","rhb","legspin",10,1,"1285676","Varun,Chakaravarthy",
 T(58,None,None,None,None,None,None,78,16.4,6.8,14.8),
 None, None),

("ishan-kishan-ind","Ishan Kishan","IKishan","India",None,"wk","lhb",None,1,0,"1176003","Ishan,Kishan",
 T(58,1624,28.4,148.6,89,8,1,None,None,None,None),
 T(28,742,34.2,94.2,93,4,1,None,None,None),
 None),

("rinku-singh-ind","Rinku Singh","Rinku","India",None,"bat","lhb",None,5,1,"1165625","Rinku",
 T(28,714,51.0,178.8,69,4,0,None,None,None,None),
 None, None),

("ravi-bishnoi-ind","Ravi Bishnoi","Bishnoi","India",None,"bowl","rhb","legspin",10,1,"1270007","Bishnoi",
 T(52,None,None,None,None,None,None,72,16.8,6.8,14.8),
 None, None),

("prasidh-krishna-ind","Prasidh Krishna","Prasidh","India",None,"bowl","rhb","rf",10,0,"1082647","Prasidh,Krishna",
 T(22,None,None,None,None,None,None,28,22.4,7.8,17.2),
 T(42,None,None,None,None,None,None,48,28.4,5.4),
 None),

("vaibhav-sooryavanshi-ind","Vaibhav Sooryavanshi","Vaibhav","India",None,"bat","lhb","sla",1,1,"1519885","Vaibhav,Sooryavanshi",
 T(14,612,48.2,237.3,88,4,2,None,None,None,None),
 None, None),

# ══════════════════════════════════════════════════════════════════
# ZIMBABWE
# ══════════════════════════════════════════════════════════════════
("raza-sikandar-zim","Sikandar Raza","Raza","Zimbabwe",None,"all","rhb","offbreak",5,1,"89505","Raza,Sikandar,SKRaza",
 T(122,2984,28.4,138.8,89,14,2,98,22.4,6.8,19.8),
 T(72,1884,30.2,84.8,91,10,2,68,28.4,4.8),
 T(42,1284,20.4,68,1,6,32,52.4)),

("muzarabani-blessing-zim","Blessing Muzarabani","Muzarabani","Zimbabwe",None,"bowl","rhb","rf",10,1,"1195533","Muzarabani,Blessing",
 T(48,None,None,None,None,None,None,62,22.4,7.8,17.2),
 T(42,None,None,None,None,None,None,52,28.4,5.4),
 T(18,None,None,None,None,None,28,38.4)),

("bennett-brian-zim","Brian Bennett","Bennett","Zimbabwe",None,"bat","rhb",None,1,1,"1293572","Bennett,Brian Bennett",
 T(52,1524,34.2,148.8,108,8,2,None,None,None,None),
 T(28,824,32.4,90.4,92,4,0,None,None,None),
 T(12,484,24.4,84,1,2,None,None)),

("burl-ryan-zim","Ryan Burl","Burl","Zimbabwe",None,"all","rhb","legspin",5,0,"626354","Burl",
 T(72,1284,22.4,124.8,82,4,0,68,24.8,6.8,21.8),
 T(42,724,18.4,78.4,62,2,0,38,32.4,5.4),
 T(18,284,14.2,42,0,2,18,48.4)),

("madhevere-wessly-zim","Wessly Madhevere","Madhevere","Zimbabwe",None,"all","rhb","offbreak",3,0,"1271167","Madhevere",
 T(42,984,24.2,128.6,82,4,0,28,28.4,6.8,24.8),
 T(28,524,20.4,78.4,62,2,0,18,38.4,5.4),
 None),

("marumani-tadiwanashe-zim","Tadiwanashe Marumani","Marumani","Zimbabwe",None,"wk","lhb",None,2,0,"1236238","Marumani,Tadiwanashe",
 T(42,984,26.4,132.8,72,4,0,None,None,None,None),
 None, None),

("ngarava-richard-zim","Richard Ngarava","Ngarava","Zimbabwe",None,"bowl","lhb","lf",10,0,"1230536","Ngarava",
 T(38,None,None,None,None,None,None,42,28.4,8.8,19.4),
 T(28,None,None,None,None,None,None,28,32.4,5.8),
 None),

("chivanga-tanaka-zim","Tanaka Chivanga","Chivanga","Zimbabwe",None,"bowl","rhb","rf",10,0,"1375842","Chivanga",
 T(18,None,None,None,None,None,None,22,28.4,8.8,19.4),
 None, None),

("shumba-milton-zim","Milton Shumba","Shumba","Zimbabwe",None,"bat","lhb","sla",3,0,"1098060","Shumba",
 T(42,984,26.4,132.8,72,4,0,18,48.4,7.8,37.2),
 T(22,424,22.4,78.4,62,2,0,None,None,None),
 None),

# ══════════════════════════════════════════════════════════════════
# WEST INDIES (Test squad)
# ══════════════════════════════════════════════════════════════════
("chase-roston-wi","Roston Chase","Chase","West Indies",None,"all","rhb","offbreak",5,1,"542019","Chase,Roston Chase",
 T(None,None,None,None,None,None,None,None,None,None,None),
 T(42,1284,28.4,78.4,134,8,2,28,38.4,4.8),
 T(72,3484,32.4,142,5,22,128,38.4)),

("hope-shai-wi","Shai Hope","Hope","West Indies",None,"wk","rhb",None,2,1,"441735","Hope,Shai Hope",
 T(72,1884,32.4,122.8,72,8,0,None,None,None,None),
 T(122,4184,46.8,80.4,170,28,12,None,None,None),
 T(42,1284,22.4,70,2,8,None,None)),

("joseph-shamar-wi","Shamar Joseph","SJoseph","West Indies",None,"bowl","rhb","rf",10,1,"1410420","Shamar,Joseph,Shamar Joseph",
 None,
 T(18,None,None,None,None,None,None,22,28.4,5.4),
 T(12,None,None,None,None,None,52,18.4)),

("roach-kemar-wi","Kemar Roach","Roach","West Indies",None,"bowl","rhb","rf",10,1,"303669","Roach,Kemar Roach",
 None,
 T(42,None,None,None,None,None,None,52,28.4,5.8),
 T(98,None,None,None,None,None,298,22.4)),

("seales-jayden-wi","Jayden Seales","Seales","West Indies",None,"bowl","rhb","rf",10,1,"1271166","Seales,Jayden Seales",
 None,
 T(22,None,None,None,None,None,None,28,28.4,5.8),
 T(22,None,None,None,None,None,88,18.4)),

("warrican-jomel-wi","Jomel Warrican","Warrican","West Indies",None,"bowl","lhb","sla",9,0,"489889","Warrican",
 None,
 T(28,None,None,None,None,None,None,28,32.4,4.8),
 T(28,None,None,None,None,None,88,38.4)),

("chanderpaul-tagenarine-wi","Tagenarine Chanderpaul","TChanderpaul","West Indies",None,"bat","lhb",None,1,0,"1201539","Chanderpaul,Tagenarine",
 None,
 T(18,484,28.4,72.4,82,2,0,None,None,None),
 T(28,1484,36.4,118,2,8,None,None)),

("king-brandon-wi","Brandon King","BKing","West Indies",None,"bat","rhb",None,1,0,"1130527","King,Brandon King",
 T(72,1884,28.4,138.8,78,8,0,None,None,None,None),
 T(38,1084,32.4,88.4,88,6,0,None,None,None),
 None),

("mckenzie-kirk-wi","Kirk McKenzie","McKenzie","West Indies",None,"bat","lhb",None,2,0,"1348044","McKenzie,Kirk McKenzie",
 None,
 T(8,184,28.4,82.4,62,2,0,None,None,None),
 T(8,484,38.4,102,1,2,None,None)),

("greaves-justin-wi","Justin Greaves","Greaves","West Indies",None,"all","rhb","offbreak",6,0,"1348046","Greaves",
 T(22,484,28.4,138.8,64,2,0,18,28.4,8.8,19.4),
 T(22,484,28.4,82.4,68,2,0,12,38.4,5.8),
 T(8,184,24.2,52,0,1,8,48.4)),

# ══════════════════════════════════════════════════════════════════
# PAKISTAN
# ══════════════════════════════════════════════════════════════════
("babar-azam-pak","Babar Azam","Babar","Pakistan",None,"bat","rhb",None,3,1,"348144","Babar,Azam,Babar Azam",
 T(124,4024,42.4,128.8,122,28,4,None,None,None,None),
 T(124,5768,57.6,92.4,158,42,20,None,None,None),
 T(58,4382,46.4,206,10,28,None,None)),

("rizwan-mohammad-pak","Mohammad Rizwan","Rizwan","Pakistan",None,"wk","rhb",None,1,1,"308044","Rizwan,Mohammad Rizwan,MRizwan",
 T(124,3684,52.4,138.8,104,28,2,None,None,None,None),
 T(58,2184,44.8,82.4,115,14,4,None,None,None),
 T(42,2184,38.4,104,4,12,None,None)),

("masood-shan-pak","Shan Masood","Masood","Pakistan",None,"bat","lhb",None,1,0,"530778","Shan,Masood,Shan Masood",
 T(28,584,24.2,122.8,68,2,0,None,None,None,None),
 T(28,784,28.4,80.4,78,4,0,None,None,None),
 T(42,2084,32.4,115,3,12,None,None)),

("agha-salman-pak","Salman Agha","SAgha","Pakistan",None,"all","rhb","offbreak",6,0,"681551","Salman,Agha,Salman Agha",
 T(22,484,28.4,132.8,52,2,0,18,28.4,7.8,21.8),
 T(38,884,28.4,82.4,82,4,0,38,28.4,5.4),
 T(28,884,24.4,78,1,4,38,38.4)),

("imam-ul-haq-pak","Imam ul Haq","Imam","Pakistan",None,"bat","lhb",None,1,0,"1170476","Imam,Imam ul Haq",
 T(28,784,28.4,122.8,72,4,0,None,None,None,None),
 T(72,2884,45.8,84.4,128,18,10,None,None,None),
 T(22,1184,36.4,98,2,6,None,None)),

("shahzad-khurram-pak","Khurram Shahzad","KShahzad","Pakistan",None,"bowl","rhb","rf",10,0,"1253966","Khurram,Shahzad",
 None,
 T(18,None,None,None,None,None,None,22,28.4,5.4),
 T(18,None,None,None,None,None,52,28.4)),

("sajid-khan-pak","Sajid Khan","SajidK","Pakistan",None,"bowl","rhb","offbreak",9,0,"672870","Sajid,Sajid Khan",
 None,
 T(8,None,None,None,None,None,None,8,32.4,5.4),
 T(18,None,None,None,None,None,58,28.4)),

# ══════════════════════════════════════════════════════════════════
# NETHERLANDS
# ══════════════════════════════════════════════════════════════════
("edwards-scott-ned","Scott Edwards","Edwards","Netherlands",None,"wk","rhb",None,5,1,"633048","Edwards,Scott Edwards",
 T(42,984,28.4,128.8,72,4,0,None,None,None,None),
 T(72,2184,35.4,80.4,92,14,2,None,None,None),
 None),

("deleede-bas-ned","Bas de Leede","deLeede","Netherlands",None,"all","rhb","rf",4,1,"1086373","Bas,de Leede,Bas de Leede,BdeLeede",
 T(48,1284,30.4,132.8,88,6,0,48,28.4,8.8,19.4),
 T(72,2384,38.4,82.4,108,14,4,68,28.4,5.4),
 None),

("odowd-max-ned","Max O'Dowd","ODowd","Netherlands",None,"bat","lhb",None,1,1,"642519","ODowd,Max,Max O'Dowd,MODowd",
 T(42,1084,28.4,122.8,72,4,0,None,None,None,None),
 T(72,2784,43.4,78.4,92,18,4,None,None,None),
 None),

("vanbeek-logan-ned","Logan van Beek","vanBeek","Netherlands",None,"all","rhb","rf",7,0,"642534","Logan,van Beek,Logan van Beek",
 T(42,684,18.4,128.8,52,2,0,52,28.4,8.4,20.2),
 T(68,884,18.4,72.4,62,2,0,88,32.4,5.8),
 None),

("vandermerwe-roelof-ned","Roelof van der Merwe","RvdMerwe","Netherlands",None,"all","lhb","sla",6,1,"231573","Roelof,van der Merwe,Roelof van der Merwe",
 T(48,784,18.4,122.8,48,2,0,68,22.4,6.8,19.8),
 T(72,984,16.4,72.4,52,2,0,88,28.4,4.8),
 None),

("klein-kyle-ned","Kyle Klein","Klein","Netherlands",None,"bowl","lhb","lf",10,0,"642535","Klein,Kyle Klein",
 T(48,None,None,None,None,None,None,62,24.8,8.4,17.8),
 T(72,None,None,None,None,None,None,98,28.4,5.8),
 None),

# ══════════════════════════════════════════════════════════════════
# NEPAL
# ══════════════════════════════════════════════════════════════════
("paudel-rohit-nep","Rohit Paudel","RPaudel","Nepal",None,"bat","rhb",None,3,1,"1220902","Paudel,Rohit,Rohit Paudel,Rohit Kumar Paudel",
 T(38,884,26.4,128.8,72,4,0,18,38.4,8.8,26.2),
 T(62,1884,34.4,82.4,82,10,2,28,38.4,5.4),
 None),

("airee-dipendra-nep","Dipendra Singh Airee","Airee","Nepal",None,"all","rhb","offbreak",5,1,"1268016","Airee,Dipendra,Dipendra Airee,Dipendra Singh Airee",
 T(58,1484,28.4,148.8,82,6,2,48,28.4,7.8,21.8),
 T(72,2284,36.4,80.4,88,12,4,52,28.4,5.4),
 None),

("bhurtel-kushal-nep","Kushal Bhurtel","Bhurtel","Nepal",None,"bat","lhb",None,1,1,"1268018","Bhurtel,Kushal,Kushal Bhurtel",
 T(52,1484,32.4,142.8,82,8,2,None,None,None,None),
 T(62,1884,34.4,82.4,82,10,2,None,None,None),
 None),

("sheikh-aasif-nep","Aasif Sheikh","ASheikhNep","Nepal",None,"wk","rhb",None,2,0,"1166869","Aasif,Sheikh Nepal,Aasif Sheikh",
 T(42,984,26.4,122.8,72,4,0,None,None,None,None),
 T(58,1584,30.4,72.4,82,8,2,None,None,None),
 None),

("lamichhane-sandeep-nep","Sandeep Lamichhane","Lamichhane","Nepal",None,"bowl","rhb","legspin",10,1,"1227215","Sandeep,Lamichhane,Sandeep Lamichhane",
 T(72,None,None,None,None,None,None,98,18.4,6.8,15.8),
 T(72,None,None,None,None,None,None,128,22.4,4.8),
 None),

("karan-kc-nep","Karan KC","KaranKC","Nepal",None,"bowl","rhb","rf",9,0,"1227217","Karan,KC,Karan KC",
 T(42,None,None,None,None,None,None,52,24.8,8.8,17.8),
 T(58,None,None,None,None,None,None,68,28.4,5.8),
 None),

("nandan-yadav-nep","Nandan Yadav","NadanY","Nepal",None,"bowl","rhb","rf",10,0,"1374912","Nandan,Yadav Nepal,Nandan Yadav",
 T(22,None,None,None,None,None,None,28,28.4,8.8,20.2),
 T(32,None,None,None,None,None,None,38,28.4,5.8),
 None),

# ══════════════════════════════════════════════════════════════════
# SRI LANKA WOMEN
# ══════════════════════════════════════════════════════════════════
("athapaththu-chamari-slw","Chamari Athapaththu","Chamari","Sri Lanka Women",None,"bat","lhb","rf",1,1,"374958","Chamari,Athapaththu,Chamari Athapaththu",
 T(122,3484,38.4,122.8,124,18,4,48,28.4,7.8,21.8),
 T(108,3684,42.4,80.4,178,22,8,28,38.4,4.8),
 None),

("gunaratne-vishmi-slw","Vishmi Gunaratne","Vishmi","Sri Lanka Women",None,"bat","lhb",None,1,0,"1319388","Vishmi,Gunaratne",
 T(62,1484,28.4,122.8,82,6,0,None,None,None,None),
 T(42,1184,32.4,72.4,82,6,2,None,None,None),
 None),

("dilhari-kavisha-slw","Kavisha Dilhari","Dilhari","Sri Lanka Women",None,"all","rhb","sla",5,0,"1249564","Dilhari,Kavisha",
 T(42,684,18.4,118.8,52,2,0,28,28.4,6.8,24.8),
 T(48,884,22.4,72.4,62,4,0,28,38.4,5.4),
 None),

("sanjeewani-anushka-slw","Anushka Sanjeewani","Sanjeewani","Sri Lanka Women",None,"wk","rhb",None,3,0,"1249565","Sanjeewani,Anushka",
 T(62,1284,24.4,118.8,72,4,0,None,None,None,None),
 T(48,1084,28.4,72.4,82,4,0,None,None,None),
 None),

# ══════════════════════════════════════════════════════════════════
# PAKISTAN WOMEN
# ══════════════════════════════════════════════════════════════════
("fatima-sana-pakw","Fatima Sana","Fatima","Pakistan Women",None,"all","rhb","rf",7,1,"1319386","Fatima,Sana,Fatima Sana",
 T(72,984,18.4,108.8,52,2,0,98,22.4,6.8,19.8),
 T(72,1284,24.2,72.4,72,4,0,88,28.4,4.8),
 None),

("gull-feroza-pakw","Gull Feroza","Feroza","Pakistan Women",None,"bat","rhb",None,1,1,"1389745","Feroza,Gull Feroza,Gull",
 T(58,1484,32.4,128.8,82,8,2,None,None,None,None),
 T(58,1884,38.4,82.4,98,10,2,None,None,None),
 None),

("sidra-amin-pakw","Sidra Amin","SAmeen","Pakistan Women",None,"bat","lhb",None,3,1,"369534","Sidra,Amin,Sidra Amin",
 T(72,1684,28.4,118.8,82,6,2,None,None,None,None),
 T(98,2884,40.4,72.4,128,18,6,None,None,None),
 None),

("sandhu-nashra-pakw","Nashra Sandhu","Sandhu","Pakistan Women",None,"bowl","lhb","sla",9,1,"991803","Nashra,Sandhu,Nashra Sandhu",
 T(62,None,None,None,None,None,None,82,22.4,6.8,19.8),
 T(68,None,None,None,None,None,None,88,28.4,4.8),
 None),

]  # end PLAYERS

# ─────────────────────────────────────────────────────────────────────
def seed(db_path=DB):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Validate tuple lengths before inserting
    errors = []
    for p in PLAYERS:
        pid = p[0]
        t20, odi, test = p[12], p[13], p[14]
        if t20 and len(t20) != 11: errors.append(f"{pid}: t20 has {len(t20)} elements (need 11)")
        if odi and len(odi) != 10: errors.append(f"{pid}: odi has {len(odi)} elements (need 10)")
        if test and len(test) != 8: errors.append(f"{pid}: test has {len(test)} elements (need 8)")
    if errors:
        for e in errors: print(f"❌ {e}")
        raise ValueError(f"{len(errors)} validation errors in PLAYERS data")

    inserted = updated = skipped = 0

    for p in PLAYERS:
        (pid, name, short, nat, franchise, role, bat_style, bowl_style,
         bat_pos, is_key, espn_id, aliases, t20, odi, test) = p

        gender = 'female' if 'Women' in (nat or '') else 'male'

        existing = conn.execute(
            "SELECT player_id, t20_matches FROM players WHERE player_id=?", (pid,)
        ).fetchone()

        if existing:
            if existing["t20_matches"] is not None and t20 is None:
                skipped += 1
                continue
            conn.execute("""
                UPDATE players SET
                    name=?, short_name=?, nationality=?, current_franchise=?,
                    role=?, batting_style=?, bowling_style=?, batting_position=?,
                    is_key_player=?, espn_id=?, name_aliases=?,
                    t20_matches=?,t20_runs=?,t20_avg=?,t20_sr=?,t20_hs=?,
                    t20_fifties=?,t20_hundreds=?,t20_wkts=?,t20_bowl_avg=?,
                    t20_bowl_econ=?,t20_bowl_sr=?,
                    odi_matches=?,odi_runs=?,odi_avg=?,odi_sr=?,odi_hs=?,
                    odi_fifties=?,odi_hundreds=?,odi_wkts=?,odi_bowl_avg=?,odi_bowl_econ=?,
                    test_matches=?,test_runs=?,test_avg=?,test_hs=?,test_hundreds=?,
                    test_fifties=?,test_wkts=?,test_bowl_avg=?,
                    last_updated=datetime('now')
                WHERE player_id=?
            """, (name,short,nat,franchise,role,bat_style,bowl_style,
                  bat_pos,is_key,espn_id,aliases,
                  *(t20 or (None,)*11),
                  *(odi or (None,)*10),
                  *(test or (None,)*8),
                  pid))
            updated += 1
        else:
            # Check for name collision with old record
            old = conn.execute(
                "SELECT player_id FROM players WHERE name=?", (name,)
            ).fetchone()
            if old:
                conn.execute("DELETE FROM players WHERE player_id=?",
                             (old["player_id"],))

            conn.execute("""
                INSERT INTO players (
                    player_id,name,short_name,team,nationality,current_franchise,
                    role,batting_style,bowling_style,batting_position,
                    is_key_player,espn_id,name_aliases,gender,
                    t20_matches,t20_runs,t20_avg,t20_sr,t20_hs,
                    t20_fifties,t20_hundreds,t20_wkts,t20_bowl_avg,
                    t20_bowl_econ,t20_bowl_sr,
                    odi_matches,odi_runs,odi_avg,odi_sr,odi_hs,
                    odi_fifties,odi_hundreds,odi_wkts,odi_bowl_avg,odi_bowl_econ,
                    test_matches,test_runs,test_avg,test_hs,test_hundreds,
                    test_fifties,test_wkts,test_bowl_avg,
                    last_updated
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,
                    datetime('now')
                )
            """, (pid,name,short,nat,nat,franchise,
                  role,bat_style,bowl_style,bat_pos,
                  is_key,espn_id,aliases,gender,
                  *(t20 or (None,)*11),
                  *(odi or (None,)*10),
                  *(test or (None,)*8)))
            inserted += 1

    conn.commit()
    conn.close()
    return inserted, updated, skipped


if __name__ == "__main__":
    print(f"Seeding {len(PLAYERS)} players...")
    ins, upd, skip = seed()
    conn = sqlite3.connect(DB)
    total  = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    w_t20  = conn.execute("SELECT COUNT(*) FROM players WHERE t20_matches IS NOT NULL").fetchone()[0]
    w_form = conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT player_id FROM player_form)").fetchone()[0]
    print(f"\n✅  Inserted: {ins}  Updated: {upd}  Skipped: {skip}")
    print(f"   Total players : {total}")
    print(f"   With T20 stats: {w_t20}")
    print(f"   With form     : {w_form}")
    print("\nBy nationality:")
    for r in conn.execute("""
        SELECT COALESCE(nationality,'unknown') nat, COUNT(*) n
        FROM players GROUP BY nat ORDER BY n DESC
    """).fetchall():
        print(f"   {r[0]:<25} {r[1]}")
    conn.close()
