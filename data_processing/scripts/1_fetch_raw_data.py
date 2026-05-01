#!/usr/bin/env python3
"""
Step 1 — Fetch real destination content and build the raw dataset.

Fetches plain-text travel descriptions for each destination from the
Wikivoyage MediaWiki API (primary) and falls back to Wikipedia (secondary).
Synthetic reviews are used only as a last resort when both APIs return nothing.

Each destination's metadata (climate, budget_tier, etc.) is hand-assigned
from published sources (see DESTINATIONS list).  The review/description
text comes from Wikivoyage's community-authored travel guides, which contain
exactly the travel-style keywords the downstream labeler needs.

Usage (from project root):
    python data_processing/scripts/1_fetch_raw_data.py

Output:
    data_processing/data/raw/destinations_raw.csv
"""
import asyncio
import csv
import sys
from pathlib import Path

# Allow running as a standalone script from the project root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import structlog
from data_processing.config import get_config
from data_processing.scrapers.wikivoyage_scraper import WikivoyageScraper

log = structlog.get_logger()

# ── Seed destination catalogue ─────────────────────────────────────────────────
#
# Schema: (name, country, travel_style, budget_tier, climate, avg_temp, best_season, tags)
#
# travel_style choices: adventure | relaxation | culture | budget | luxury | family
# budget_tier  choices: budget | mid | luxury
# climate      choices: tropical | subtropical | temperate | continental | highland | arid
# avg_temp     float °C (annual average, rounded)
# best_season  human-readable month range
# tags         comma-separated keywords (used both for review generation and ML features)
#
# Sources for each assignment:
#   travel_style → UNESCO listings, Lonely Planet category, dominant TripAdvisor
#                  "Attraction Type" for that destination
#   budget_tier  → Numbeo Cost of Living Index + Backpacker Bible hostel pricing
#   climate      → Köppen–Geiger climate classification
#   avg_temp     → WorldWeatherOnline annual average
#   best_season  → national tourism board guidance

DESTINATIONS: list[tuple] = [
    # ── Thailand (20) ──────────────────────────────────────────────────────────
    ("Bangkok",           "Thailand", "culture",     "budget",  "tropical",     28, "Nov-Feb",   "temple,culture,palace,market,street-food,history,shrine,heritage"),
    ("Chiang Mai",        "Thailand", "culture",     "budget",  "tropical",     26, "Nov-Apr",   "temple,trekking,culture,elephant,tradition,mountain,heritage,night-bazaar"),
    ("Phuket",            "Thailand", "relaxation",  "mid",     "tropical",     28, "Nov-Apr",   "beach,resort,diving,snorkeling,spa,pool,sunset,island"),
    ("Krabi",             "Thailand", "adventure",   "mid",     "tropical",     28, "Nov-Apr",   "climbing,kayaking,diving,beach,limestone,adventure,rock-climbing"),
    ("Koh Samui",         "Thailand", "relaxation",  "mid",     "tropical",     28, "Dec-Apr",   "beach,spa,resort,pool,yoga,massage,tranquil,sunset"),
    ("Pattaya",           "Thailand", "budget",      "budget",  "tropical",     28, "Nov-Apr",   "budget,affordable,beach,backpacking,hostel,cheap,nightlife"),
    ("Ayutthaya",         "Thailand", "culture",     "budget",  "tropical",     28, "Nov-Feb",   "ancient,ruins,temple,UNESCO,history,monument,heritage,palace,shrine"),
    ("Koh Tao",           "Thailand", "adventure",   "budget",  "tropical",     28, "Apr-Oct",   "diving,snorkeling,scuba,beach,coral,adventure,surfing"),
    ("Pai",               "Thailand", "relaxation",  "budget",  "highland",     22, "Nov-Mar",   "yoga,meditation,peaceful,hot-springs,mountain,tranquil,zen,retreat,serene"),
    ("Chiang Rai",        "Thailand", "culture",     "budget",  "tropical",     25, "Nov-Apr",   "temple,culture,trekking,hill-tribes,heritage,ancient,shrine"),
    ("Hua Hin",           "Thailand", "family",      "mid",     "tropical",     28, "Nov-Apr",   "family,beach,safe,kids,children,resort,park,family-friendly"),
    ("Koh Phi Phi",       "Thailand", "adventure",   "mid",     "tropical",     28, "Nov-Apr",   "diving,beach,snorkeling,kayaking,limestone,adventure,cliff"),
    ("Railay Beach",      "Thailand", "adventure",   "mid",     "tropical",     28, "Nov-Apr",   "climbing,rock-climbing,beach,kayaking,isolated,adventure,limestone"),
    ("Kanchanaburi",      "Thailand", "culture",     "budget",  "tropical",     28, "Nov-Feb",   "history,heritage,ancient,rafting,culture,monument,war,traditional"),
    ("Sukhothai",         "Thailand", "culture",     "budget",  "tropical",     28, "Nov-Feb",   "ancient,ruins,UNESCO,history,temple,heritage,monument,palace"),
    ("Koh Lanta",         "Thailand", "relaxation",  "budget",  "tropical",     28, "Nov-Apr",   "beach,peaceful,quiet,serene,sunset,tranquil,yoga,spa"),
    ("Khao Yai",          "Thailand", "adventure",   "mid",     "tropical",     25, "Nov-Feb",   "wildlife,safari,trekking,hiking,adventure,national-park,elephant"),
    ("Phang Nga",         "Thailand", "adventure",   "mid",     "tropical",     28, "Nov-Apr",   "kayaking,caves,limestone,adventure,mangrove,cliff,surfing"),
    ("Samui Luxury",      "Thailand", "luxury",      "luxury",  "tropical",     28, "Dec-Apr",   "luxury,villa,resort,spa,fine-dining,exclusive,private,upscale,5-star"),
    ("Chiang Dao",        "Thailand", "adventure",   "budget",  "highland",     22, "Nov-Mar",   "trekking,hiking,mountain,cave,adventure,wildlife,climbing"),

    # ── Vietnam (15) ──────────────────────────────────────────────────────────
    ("Hanoi",             "Vietnam",  "culture",     "budget",  "subtropical",  23, "Oct-Apr",   "temple,culture,history,heritage,ancient,museum,traditional,colonial,shrine,monument"),
    ("Ho Chi Minh City",  "Vietnam",  "culture",     "budget",  "tropical",     27, "Dec-Apr",   "history,museum,culture,heritage,colonial,market,traditional,monument"),
    ("Hoi An",            "Vietnam",  "culture",     "mid",     "tropical",     26, "Feb-Jul",   "ancient,UNESCO,heritage,culture,architecture,traditional,art,lanterns"),
    ("Ha Long Bay",       "Vietnam",  "adventure",   "mid",     "subtropical",  23, "Mar-Nov",   "kayaking,diving,climbing,adventure,cave,limestone,expedition,snorkeling"),
    ("Da Nang",           "Vietnam",  "relaxation",  "mid",     "tropical",     27, "Mar-Sep",   "beach,resort,spa,swimming,pool,sunset,relaxing,calm"),
    ("Hue",               "Vietnam",  "culture",     "budget",  "subtropical",  25, "Mar-Aug",   "imperial,palace,temple,museum,heritage,cultural,ancient,history,monument,shrine"),
    ("Sa Pa",             "Vietnam",  "adventure",   "budget",  "highland",     18, "Mar-May",   "trekking,hiking,mountain,climbing,expedition,adventure,rice-terrace"),
    ("Phu Quoc",          "Vietnam",  "relaxation",  "luxury",  "tropical",     27, "Nov-Apr",   "beach,resort,spa,luxury,villa,private,sunset,paradise,pool,tranquil"),
    ("Dalat",             "Vietnam",  "relaxation",  "budget",  "highland",     17, "Nov-Apr",   "peaceful,garden,waterfall,quiet,serene,cool,calm,retreat,tranquil"),
    ("Ninh Binh",         "Vietnam",  "adventure",   "budget",  "subtropical",  24, "Sep-Dec",   "kayaking,cave,trekking,hiking,adventure,boat,cycling,expedition"),
    ("Nha Trang",         "Vietnam",  "relaxation",  "mid",     "tropical",     27, "Feb-Sep",   "beach,diving,snorkeling,resort,spa,pool,sunset,relaxing,island"),
    ("Mui Ne",            "Vietnam",  "adventure",   "budget",  "tropical",     27, "Nov-Apr",   "surfing,adventure,sand-dune,kite-surfing,beach,kayaking,hiking"),
    ("Mekong Delta",      "Vietnam",  "culture",     "budget",  "tropical",     27, "Dec-Apr",   "culture,traditional,heritage,boat,crafts,museum,market,ancient"),
    ("Hoa Lu",            "Vietnam",  "culture",     "budget",  "subtropical",  24, "Oct-Apr",   "ancient,temple,history,heritage,monument,cultural,ruins,shrine,palace"),
    ("Con Dao",           "Vietnam",  "relaxation",  "luxury",  "tropical",     27, "Nov-Apr",   "beach,paradise,peaceful,pristine,resort,private,tranquil,quiet,serene"),

    # ── Indonesia (20) ────────────────────────────────────────────────────────
    ("Bali Ubud",         "Indonesia","culture",     "mid",     "tropical",     26, "Apr-Oct",   "temple,culture,traditional,heritage,art,yoga,meditation,cultural,shrine,palace"),
    ("Bali Seminyak",     "Indonesia","luxury",      "luxury",  "tropical",     27, "Apr-Oct",   "luxury,villa,resort,fine-dining,exclusive,private,upscale,beach,spa,5-star"),
    ("Bali Kuta",         "Indonesia","budget",      "budget",  "tropical",     27, "Apr-Oct",   "surfing,budget,backpacking,affordable,cheap,hostel,beach,inexpensive"),
    ("Yogyakarta",        "Indonesia","culture",     "budget",  "tropical",     26, "Apr-Oct",   "UNESCO,ancient,temple,heritage,culture,traditional,monument,palace,ruins,history"),
    ("Lombok",            "Indonesia","adventure",   "mid",     "tropical",     27, "May-Sep",   "trekking,hiking,mountain,diving,surfing,adventure,climbing,expedition"),
    ("Komodo Island",     "Indonesia","adventure",   "mid",     "tropical",     28, "Apr-Aug",   "diving,snorkeling,trekking,wildlife,adventure,expedition,hiking,kayaking"),
    ("Raja Ampat",        "Indonesia","adventure",   "luxury",  "tropical",     27, "Oct-Apr",   "diving,snorkeling,adventure,expedition,wildlife,remote,kayaking"),
    ("Gili Islands",      "Indonesia","relaxation",  "mid",     "tropical",     27, "Apr-Aug",   "beach,snorkeling,diving,tranquil,peaceful,sunset,paradise,calm,resort"),
    ("Nusa Penida",       "Indonesia","adventure",   "mid",     "tropical",     27, "Apr-Oct",   "diving,snorkeling,cliff,adventure,hiking,kayaking,beach,wildlife"),
    ("Jakarta",           "Indonesia","culture",     "budget",  "tropical",     27, "Jun-Sep",   "museum,culture,history,heritage,traditional,colonial,market,art,architecture"),
    ("Tana Toraja",       "Indonesia","culture",     "mid",     "highland",     22, "Jul-Sep",   "traditional,culture,heritage,ceremony,ancient,cultural,monument,art"),
    ("Lake Toba Sumatra", "Indonesia","relaxation",  "budget",  "highland",     22, "Jun-Sep",   "lake,peaceful,calm,quiet,serene,tranquil,culture,yoga,retreat"),
    ("Flores",            "Indonesia","adventure",   "budget",  "tropical",     27, "Apr-Oct",   "trekking,hiking,adventure,diving,expedition,climbing,mountain,wildlife"),
    ("Amed Bali",         "Indonesia","adventure",   "budget",  "tropical",     28, "Apr-Oct",   "diving,snorkeling,adventure,beach,coral,expedition,kayaking"),
    ("Bromo Java",        "Indonesia","adventure",   "mid",     "highland",     15, "Apr-Sep",   "volcano,trekking,hiking,adventure,sunrise,expedition,climbing,mountain"),
    ("Bandung",           "Indonesia","budget",      "budget",  "highland",     22, "May-Sep",   "budget,affordable,cheap,hostel,shopping,backpacking,inexpensive,value"),
    ("Bintan",            "Indonesia","luxury",      "luxury",  "tropical",     27, "Jun-Sep",   "resort,luxury,spa,villa,private,exclusive,beach,fine-dining,upscale,5-star"),
    ("Bogor",             "Indonesia","family",      "budget",  "tropical",     25, "Jun-Sep",   "family,park,kids,children,educational,garden,zoo,safe,family-friendly"),
    ("Manado",            "Indonesia","adventure",   "mid",     "tropical",     27, "Jun-Aug",   "diving,snorkeling,adventure,expedition,coral,wildlife,kayaking,trekking"),
    ("Belitung",          "Indonesia","relaxation",  "mid",     "tropical",     27, "Apr-Oct",   "beach,peaceful,pristine,quiet,serene,tranquil,paradise,sunset,calm"),

    # ── Japan (20) ────────────────────────────────────────────────────────────
    ("Tokyo",             "Japan",    "culture",     "luxury",  "temperate",    16, "Mar-May,Sep-Nov", "temple,culture,museum,heritage,architecture,traditional,art,palace,shrine,history"),
    ("Kyoto",             "Japan",    "culture",     "mid",     "temperate",    15, "Mar-May,Oct-Nov", "temple,shrine,UNESCO,culture,heritage,traditional,ancient,history,palace,monument,geisha"),
    ("Osaka",             "Japan",    "culture",     "budget",  "temperate",    16, "Mar-May,Sep-Nov", "culture,history,museum,castle,architecture,street-food,heritage,traditional,affordable"),
    ("Hiroshima",         "Japan",    "culture",     "mid",     "temperate",    16, "Apr-May,Oct",    "peace,history,monument,UNESCO,heritage,museum,cultural,ancient,memorial"),
    ("Hakone",            "Japan",    "relaxation",  "luxury",  "temperate",    13, "Oct-Nov,Jan-Mar","onsen,hot-springs,resort,spa,peaceful,tranquil,mountain,calm,zen,yoga,retreat"),
    ("Nara",              "Japan",    "culture",     "mid",     "temperate",    15, "Mar-May,Oct-Nov","temple,heritage,UNESCO,ancient,history,monument,shrine,cultural,park,museum"),
    ("Okinawa",           "Japan",    "relaxation",  "mid",     "subtropical",  23, "Apr-Jun",       "beach,diving,snorkeling,resort,spa,peaceful,island,paradise,calm,sunset"),
    ("Hokkaido",          "Japan",    "adventure",   "mid",     "continental",   8, "Jun-Sep,Jan-Feb","skiing,hiking,trekking,wildlife,adventure,mountain,expedition,climbing,safari"),
    ("Nagano",            "Japan",    "adventure",   "mid",     "continental",  10, "Dec-Mar,Jun-Sep","skiing,hiking,trekking,mountain,adventure,hot-springs,expedition,climbing"),
    ("Kanazawa",          "Japan",    "culture",     "mid",     "temperate",    13, "Apr-May,Oct-Nov","geisha,traditional,culture,arts,heritage,ancient,museum,palace,shrine"),
    ("Arashiyama",        "Japan",    "relaxation",  "mid",     "temperate",    15, "Mar-Apr,Nov",   "peaceful,zen,temple,bamboo,tranquil,serene,calm,garden,meditation,quiet"),
    ("Nikko",             "Japan",    "culture",     "mid",     "temperate",    10, "Apr-May,Oct-Nov","shrine,temple,UNESCO,heritage,monument,ancient,cultural,architecture,history"),
    ("Fuji Five Lakes",   "Japan",    "adventure",   "mid",     "temperate",    10, "Apr-May,Jul-Sep","hiking,trekking,climbing,adventure,mountain,expedition,surf,kayaking"),
    ("Sapporo",           "Japan",    "adventure",   "budget",  "continental",   8, "Feb-Mar,Jul-Aug","skiing,adventure,budget,affordable,cheap,hostel,trekking,hiking,backpacking"),
    ("Takayama",          "Japan",    "culture",     "mid",     "continental",  11, "Apr-May,Oct-Nov","traditional,culture,heritage,ancient,festival,sake,monument,museum,art,shrine"),
    ("Miyajima",          "Japan",    "culture",     "mid",     "temperate",    15, "Apr-May,Oct-Nov","shrine,UNESCO,heritage,culture,ancient,monument,temple,history,architecture"),
    ("Kamakura",          "Japan",    "culture",     "mid",     "temperate",    15, "Mar-May,Sep-Nov","temple,ancient,heritage,culture,monument,shrine,history,hiking,trekking"),
    ("Shinjuku Japan",    "Japan",    "budget",      "budget",  "temperate",    16, "Mar-May,Sep-Nov","budget,affordable,hostel,cheap,street-food,nightlife,backpacking,inexpensive"),
    ("Beppu Onsen",       "Japan",    "relaxation",  "mid",     "subtropical",  17, "Oct-Nov,Mar-May","onsen,hot-springs,spa,relaxing,resort,peaceful,tranquil,zen,calm,massage"),
    ("Sendai",            "Japan",    "culture",     "mid",     "temperate",    12, "Apr-May,Aug",   "culture,castle,history,heritage,museum,traditional,shrine,ancient,monument"),

    # ── South Korea (10) ──────────────────────────────────────────────────────
    ("Seoul",             "South Korea","culture",   "budget",  "temperate",    13, "Mar-May,Sep-Nov","palace,culture,heritage,history,traditional,museum,monument,ancient,shrine,affordable"),
    ("Busan",             "South Korea","relaxation","mid",     "temperate",    14, "Jun-Sep",       "beach,spa,resort,peaceful,temple,tranquil,calm,seafood,sunset"),
    ("Jeju Island",       "South Korea","adventure", "mid",     "subtropical",  15, "Mar-Jun,Sep-Nov","trekking,hiking,volcano,adventure,diving,beach,climbing,expedition,mountain"),
    ("Gyeongju",          "South Korea","culture",   "budget",  "temperate",    13, "Apr-May,Oct",   "UNESCO,ancient,temple,heritage,history,tombs,cultural,monument,shrine,ruins"),
    ("Jeonju",            "South Korea","culture",   "budget",  "temperate",    13, "Mar-May,Sep-Nov","traditional,heritage,culture,ancient,architecture,museum,art,shrine,cultural"),
    ("Seoraksan",         "South Korea","adventure", "budget",  "temperate",    10, "Sep-Oct",       "hiking,trekking,mountain,adventure,climbing,expedition,wildlife,national-park"),
    ("Incheon",           "South Korea","budget",    "budget",  "temperate",    13, "Apr-May,Sep-Oct","budget,affordable,cheap,hostel,backpacking,inexpensive,market,street-food"),
    ("Andong",            "South Korea","culture",   "budget",  "temperate",    13, "Sep-Oct",       "traditional,folk-village,heritage,culture,ancient,history,museum,art,cultural"),
    ("Namhansanseong",    "South Korea","adventure", "budget",  "temperate",    13, "Mar-May,Oct-Nov","hiking,trekking,mountain,fortress,adventure,climbing,expedition"),
    ("Sokcho",            "South Korea","adventure", "budget",  "temperate",    13, "Jul-Aug,Oct",   "hiking,trekking,beach,adventure,mountain,climbing,national-park,wildlife"),

    # ── Nepal (10) ────────────────────────────────────────────────────────────
    ("Kathmandu",         "Nepal",    "culture",     "budget",  "highland",     17, "Oct-Dec,Mar-May","temple,culture,heritage,history,traditional,shrine,monument,palace,ancient,UNESCO"),
    ("Pokhara",           "Nepal",    "adventure",   "budget",  "highland",     18, "Oct-Dec,Mar-May","trekking,hiking,paragliding,mountain,adventure,climbing,expedition,lake"),
    ("Everest Base Camp", "Nepal",    "adventure",   "mid",     "highland",      0, "Oct-Nov,Apr-May","extreme,trekking,mountaineering,expedition,climbing,hiking,adventure,mountain"),
    ("Annapurna Circuit", "Nepal",    "adventure",   "budget",  "highland",      5, "Oct-Nov,Mar-Apr","trekking,hiking,mountain,expedition,adventure,climbing,remote,extreme"),
    ("Chitwan",           "Nepal",    "adventure",   "mid",     "subtropical",  26, "Oct-Mar",       "wildlife,safari,elephant,tigers,adventure,trekking,national-park,expedition"),
    ("Lumbini",           "Nepal",    "culture",     "budget",  "subtropical",  24, "Oct-Mar",       "UNESCO,heritage,pilgrimage,temple,monument,ancient,cultural,history,shrine"),
    ("Patan",             "Nepal",    "culture",     "budget",  "highland",     17, "Oct-Dec,Mar-May","medieval,ancient,temple,UNESCO,heritage,traditional,architecture,monument,art"),
    ("Bhaktapur",         "Nepal",    "culture",     "budget",  "highland",     17, "Oct-Nov,Mar-Apr","medieval,ancient,UNESCO,temple,heritage,traditional,pottery,monument,shrine"),
    ("Bardia",            "Nepal",    "adventure",   "mid",     "subtropical",  26, "Oct-Apr",       "wildlife,safari,tigers,trekking,adventure,expedition,national-park,remote"),
    ("Bandipur",          "Nepal",    "relaxation",  "budget",  "highland",     18, "Oct-Nov,Mar-Apr","peaceful,tranquil,quiet,serene,hilltop,calm,zen,retreat,views,village"),

    # ── Philippines (10) ──────────────────────────────────────────────────────
    ("El Nido Palawan",   "Philippines","adventure", "mid",     "tropical",     28, "Dec-May",   "diving,kayaking,snorkeling,beach,cliff,adventure,limestone,expedition"),
    ("Boracay",           "Philippines","relaxation","mid",     "tropical",     28, "Nov-May",   "beach,resort,spa,water-sports,sunset,tranquil,paradise,pool,calm,yoga"),
    ("Cebu",              "Philippines","budget",    "budget",  "tropical",     28, "Dec-May",   "diving,budget,affordable,backpacking,cheap,hostel,island,street-food,inexpensive"),
    ("Siargao",           "Philippines","adventure", "mid",     "tropical",     27, "Mar-May",   "surfing,adventure,diving,beach,kayaking,expedition,island"),
    ("Bohol",             "Philippines","adventure", "mid",     "tropical",     28, "Dec-May",   "diving,island-hopping,adventure,wildlife,trekking,kayaking,snorkeling"),
    ("Manila",            "Philippines","culture",   "budget",  "tropical",     28, "Dec-May",   "history,museum,culture,heritage,colonial,architecture,traditional,market,monument"),
    ("Coron Palawan",     "Philippines","adventure", "mid",     "tropical",     28, "Dec-May",   "diving,snorkeling,kayaking,adventure,lagoon,expedition,beach,cliff"),
    ("Batanes Islands",   "Philippines","relaxation","mid",     "subtropical",  24, "Mar-Jun",   "peaceful,quiet,remote,tranquil,serene,views,calm,rolling-hills,zen"),
    ("Siquijor",          "Philippines","relaxation","budget",  "tropical",     28, "Dec-May",   "beach,diving,peaceful,tranquil,waterfall,quiet,calm,serene,paradise"),
    ("Vigan",             "Philippines","culture",   "budget",  "subtropical",  27, "Nov-Apr",   "UNESCO,heritage,colonial,architecture,history,cultural,monument,ancient,traditional"),

    # ── Cambodia (8) ──────────────────────────────────────────────────────────
    ("Siem Reap",         "Cambodia", "culture",     "budget",  "tropical",     28, "Nov-Apr",   "UNESCO,Angkor,temple,ruins,ancient,heritage,history,monument,cultural,shrine"),
    ("Phnom Penh",        "Cambodia", "culture",     "budget",  "tropical",     27, "Nov-Apr",   "history,museum,heritage,colonial,cultural,market,monument,traditional,ancient"),
    ("Kampot",            "Cambodia", "relaxation",  "budget",  "tropical",     28, "Nov-Apr",   "peaceful,riverside,calm,cycling,quiet,tranquil,serene,budget,affordable,cheap"),
    ("Koh Rong",          "Cambodia", "relaxation",  "budget",  "tropical",     28, "Nov-Apr",   "beach,diving,snorkeling,peaceful,paradise,tranquil,budget,island,calm,sunset"),
    ("Battambang",        "Cambodia", "culture",     "budget",  "tropical",     28, "Nov-Apr",   "colonial,heritage,culture,traditional,history,art,museum,ancient,cultural"),
    ("Kratie",            "Cambodia", "adventure",   "budget",  "tropical",     27, "Nov-Apr",   "wildlife,cycling,adventure,boat,river,expedition,remote,kayaking"),
    ("Mondulkiri",        "Cambodia", "adventure",   "mid",     "highland",     22, "Nov-Apr",   "elephant,wildlife,trekking,hiking,adventure,waterfall,expedition,safari,national-park"),
    ("Kep",               "Cambodia", "relaxation",  "budget",  "tropical",     28, "Nov-Apr",   "beach,seafood,peaceful,quiet,tranquil,serene,calm,resort,relaxing"),

    # ── Singapore (5) ─────────────────────────────────────────────────────────
    ("Singapore City",    "Singapore","luxury",      "luxury",  "tropical",     27, "all-year",  "luxury,fine-dining,exclusive,5-star,upscale,resort,private,villa,marina"),
    ("Sentosa Singapore", "Singapore","family",      "luxury",  "tropical",     27, "all-year",  "family,kids,children,aquarium,theme-park,resort,beach,safe,park,educational"),
    ("Little India SG",   "Singapore","culture",     "budget",  "tropical",     27, "all-year",  "culture,temple,heritage,traditional,market,street-food,history,monument,shrine"),
    ("Clarke Quay SG",    "Singapore","budget",      "mid",     "tropical",     27, "all-year",  "budget,nightlife,riverside,affordable,food,hostel,backpacking,cheap,inexpensive"),
    ("Chinatown SG",      "Singapore","culture",     "budget",  "tropical",     27, "all-year",  "temple,culture,heritage,traditional,market,history,street-food,shrine,monument"),

    # ── Malaysia (10) ─────────────────────────────────────────────────────────
    ("Kuala Lumpur",      "Malaysia", "culture",     "budget",  "tropical",     27, "May-Jul",   "culture,museum,heritage,colonial,architecture,traditional,monument,market,shrine,history"),
    ("Penang",            "Malaysia", "culture",     "budget",  "tropical",     27, "Dec-Feb",   "UNESCO,heritage,culture,traditional,street-food,temple,art,architecture,monument,history"),
    ("Langkawi",          "Malaysia", "relaxation",  "mid",     "tropical",     28, "Nov-Apr",   "beach,resort,mangrove,spa,tranquil,peaceful,paradise,island,calm,sunset"),
    ("Kota Kinabalu",     "Malaysia", "adventure",   "mid",     "tropical",     27, "Apr-Oct",   "trekking,hiking,mountain,adventure,diving,wildlife,expedition,climbing,safari"),
    ("Cameron Highlands", "Malaysia", "relaxation",  "budget",  "highland",     18, "all-year",  "peaceful,tea,hiking,quiet,tranquil,cool,calm,serene,yoga,garden,retreat"),
    ("Malacca",           "Malaysia", "culture",     "budget",  "tropical",     27, "Jun-Aug",   "UNESCO,heritage,colonial,culture,history,traditional,architecture,monument,shrine,ancient"),
    ("Perhentian Islands","Malaysia", "relaxation",  "budget",  "tropical",     28, "Apr-Oct",   "beach,snorkeling,diving,peaceful,paradise,tranquil,calm,island,sunset,serene"),
    ("Tioman Island",     "Malaysia", "adventure",   "mid",     "tropical",     28, "Apr-Sep",   "diving,snorkeling,trekking,adventure,jungle,beach,kayaking,wildlife,expedition"),
    ("Taman Negara",      "Malaysia", "adventure",   "mid",     "tropical",     26, "Apr-Oct",   "trekking,hiking,wildlife,adventure,jungle,safari,expedition,canopy,kayaking"),
    ("Ipoh",              "Malaysia", "culture",     "budget",  "tropical",     27, "Nov-Jan",   "heritage,culture,temple,history,architecture,traditional,museum,monument,colonial,ancient"),

    # ── Myanmar (8) ───────────────────────────────────────────────────────────
    ("Yangon",            "Myanmar",  "culture",     "budget",  "tropical",     27, "Nov-Feb",   "UNESCO,pagoda,temple,heritage,culture,history,colonial,traditional,monument,shrine"),
    ("Bagan",             "Myanmar",  "culture",     "mid",     "tropical",     28, "Nov-Feb",   "ancient,temple,ruins,UNESCO,heritage,monument,palace,history,cultural,shrine"),
    ("Mandalay",          "Myanmar",  "culture",     "budget",  "tropical",     27, "Nov-Feb",   "palace,temple,culture,heritage,traditional,ancient,monastery,shrine,history,monument"),
    ("Inle Lake",         "Myanmar",  "culture",     "mid",     "highland",     22, "Nov-Feb",   "traditional,culture,heritage,crafts,floating-village,ancient,cultural,peaceful,lake"),
    ("Ngapali",           "Myanmar",  "relaxation",  "mid",     "tropical",     27, "Oct-Apr",   "beach,peaceful,pristine,tranquil,quiet,serene,paradise,resort,sunset,calm"),
    ("Hsipaw",            "Myanmar",  "adventure",   "budget",  "highland",     22, "Nov-Feb",   "trekking,hiking,adventure,remote,hill-tribes,mountain,expedition,climbing,wildlife"),
    ("Hpa An",            "Myanmar",  "culture",     "budget",  "tropical",     28, "Nov-Mar",   "cave,temple,culture,ancient,heritage,monument,karst,shrine,traditional,ruins"),
    ("Mrauk U",           "Myanmar",  "culture",     "budget",  "tropical",     28, "Nov-Feb",   "ancient,temple,ruins,heritage,remote,monument,cultural,shrine,history,palace"),

    # ── Laos (8) ──────────────────────────────────────────────────────────────
    ("Luang Prabang",     "Laos",     "culture",     "budget",  "tropical",     26, "Oct-Apr",   "UNESCO,temple,culture,heritage,traditional,monastery,shrine,history,monument,colonial"),
    ("Vang Vieng",        "Laos",     "adventure",   "budget",  "tropical",     26, "Oct-May",   "tubing,kayaking,rock-climbing,cave,adventure,trekking,budget,cheap,backpacking,hostel"),
    ("Vientiane",         "Laos",     "culture",     "budget",  "tropical",     27, "Oct-Apr",   "temple,culture,heritage,traditional,museum,monument,colonial,shrine,ancient,history"),
    ("4000 Islands",      "Laos",     "relaxation",  "budget",  "tropical",     28, "Oct-May",   "peaceful,hammock,tranquil,budget,calm,quiet,serene,cheap,affordable,island"),
    ("Nong Khiaw",        "Laos",     "relaxation",  "budget",  "tropical",     27, "Oct-Apr",   "peaceful,quiet,serene,remote,tranquil,calm,trekking,river,mountain,zen"),
    ("Plain of Jars",     "Laos",     "culture",     "budget",  "highland",     20, "Oct-Apr",   "ancient,UNESCO,heritage,mysterious,cultural,monument,history,ruins,traditional"),
    ("Luang Namtha",      "Laos",     "adventure",   "budget",  "highland",     22, "Oct-Apr",   "trekking,hiking,adventure,remote,tribal,expedition,cycling,wildlife,mountain"),
    ("Pakse",             "Laos",     "adventure",   "budget",  "tropical",     28, "Oct-Apr",   "trekking,hiking,cycling,adventure,waterfall,coffee,expedition,mountain,kayaking"),

    # ── Bhutan (3) ────────────────────────────────────────────────────────────
    ("Paro",              "Bhutan",   "culture",     "luxury",  "highland",     10, "Mar-May,Sep-Nov","temple,monastery,trekking,heritage,culture,traditional,ancient,shrine,UNESCO,hiking"),
    ("Thimphu",           "Bhutan",   "culture",     "luxury",  "highland",     10, "Mar-May,Sep-Nov","culture,museum,monastery,heritage,traditional,temple,ancient,monument,shrine,UNESCO"),
    ("Punakha",           "Bhutan",   "culture",     "luxury",  "highland",     16, "Mar-May,Sep-Nov","monastery,temple,culture,heritage,traditional,ancient,monument,shrine,fortress"),

    # ── Sri Lanka (3) ─────────────────────────────────────────────────────────
    ("Colombo",           "Sri Lanka","culture",     "budget",  "tropical",     27, "Dec-Apr",   "culture,temple,history,heritage,colonial,traditional,market,monument,shrine,ancient"),
    ("Galle",             "Sri Lanka","culture",     "mid",     "tropical",     27, "Dec-Apr",   "Dutch,UNESCO,heritage,colonial,architecture,culture,fort,monument,history,beach,traditional"),
    ("Sigiriya",          "Sri Lanka","adventure",   "mid",     "tropical",     27, "Jan-Apr",   "ancient,ruins,trekking,climbing,adventure,heritage,UNESCO,monument,history,expedition"),
]

# ── Synthetic review generation ────────────────────────────────────────────────

_REVIEW_FRAMES: list[str] = [
    "Loved the {} here — absolutely highlight of my trip.",
    "The {} scene is world-class, nothing like it anywhere.",
    "Spent most days enjoying {} activities — highly recommend.",
    "If you're into {}, this destination is unmissable.",
    "Best {} experience of my travels so far.",
    "The quality of {} was far beyond expectations.",
    "Can't say enough good things about {} here.",
    "Came for the {}, stayed for the whole vibe.",
    "{} enthusiasts will be completely blown away.",
    "The local {} culture and offerings are incredible.",
    "Great {} options throughout — every budget welcome.",
    "Really impressed by the standard of {} available.",
    "Would come back just for the {} alone.",
    "{} here beats anywhere else in the region.",
    "The {} opportunities are unparalleled — go.",
]


def _generate_seed_reviews(tags: str, num: int = 50) -> list[str]:
    """Create `num` synthetic review sentences seeded from destination tags.

    Tags drive keyword density: each tag is embedded into a review frame,
    cycling through frames and tags until `num` sentences are produced.
    This guarantees consistent keyword density that the labeler can
    measure, reproduce, and audit via labeling_rules.json.
    """
    kws = [t.strip() for t in tags.split(",") if t.strip()]
    if not kws:
        kws = ["travel", "destination", "visit"]
    reviews = []
    for i in range(num):
        frame = _REVIEW_FRAMES[i % len(_REVIEW_FRAMES)]
        kw = kws[i % len(kws)]
        reviews.append(frame.format(kw))
    return reviews


# ── Main ───────────────────────────────────────────────────────────────────────

async def generate_raw_csv() -> None:
    """Fetch Wikivoyage content and write destinations_raw.csv."""
    config = get_config()
    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = config.RAW_DATA_DIR / "destinations_raw.csv"

    fieldnames = [
        "destination_name", "country", "travel_style", "budget_tier",
        "climate", "avg_temp", "best_season", "tags",
        "num_reviews", "price_level", "reviews",
    ]

    _PRICE = {"budget": "$", "mid": "$$", "luxury": "$$$$"}

    rows = []
    synthetic_count = 0
    real_count = 0

    async with WikivoyageScraper() as scraper:
        for entry in DESTINATIONS:
            name, country, style, tier, climate, temp, season, tags = entry

            reviews = await scraper.fetch_reviews(name, country)

            if not reviews:
                log.warning("fallback_to_synthetic", destination=name)
                reviews = _generate_seed_reviews(tags, num=50)
                synthetic_count += 1
            else:
                real_count += 1

            rows.append({
                "destination_name": name,
                "country": country,
                "travel_style": style,
                "budget_tier": tier,
                "climate": climate,
                "avg_temp": temp,
                "best_season": season,
                "tags": tags,
                "num_reviews": len(reviews),
                "price_level": _PRICE[tier],
                "reviews": "|".join(reviews),
            })

    with open(output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    log.info(
        "raw_csv_written",
        path=str(output),
        total=len(rows),
        real_content=real_count,
        synthetic_fallback=synthetic_count,
    )
    print(f"Written {len(rows)} destinations -> {output}")
    print(f"  Real Wikivoyage/Wikipedia content: {real_count}")
    print(f"  Synthetic fallback: {synthetic_count}")


if __name__ == "__main__":
    asyncio.run(generate_raw_csv())
