"""Central configuration for the SEA auto market data pipeline."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "market.db"
CSV_DIR = DATA_DIR / "csv"
JSON_DIR = DATA_DIR / "json"
RAW_DIR = DATA_DIR / "raw"

for _d in (DATA_DIR, CSV_DIR, JSON_DIR, RAW_DIR):
    _d.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 45
REQUEST_DELAY = 1.2  # polite crawl delay, seconds

# --- Vietnam: VAMA monthly sales reports -------------------------------------
# NOTE: vama.org.vn presents a broken TLS chain; plain HTTP is the working path.
VAMA_BASE = "http://vama.org.vn"
VAMA_REPORT_URL = VAMA_BASE + "/vn/bao-cao-ban-hang-thang-{month}-nam-{year}.html"
VAMA_START = (2024, 1)  # earliest month published on the current site

# --- Thailand: FTI monthly sales figures -------------------------------------
# Reported by the Federation of Thai Industries (สภาอุตสาหกรรมแห่งประเทศไทย)
# and republished in full by AutoLife Thailand, which exposes a WordPress REST API.
ALT_API = "https://autolifethailand.tv/wp-json/wp/v2/posts"
ALT_SEARCH_TERMS = ["ยอดขายรถยนต์", "ยอดขาย รถยนต์"]

# --- Data-source registry (provenance) ---------------------------------------
# Every sales row is tagged with the organisation that published the figure and
# the website it was actually crawled from, so the exported data is
# self-describing. ``site`` is the exact domain crawled; ``name`` is the
# publisher; ``url`` is the entry point.
SOURCES = {
    "vama": {
        "name": "VAMA (Vietnam Automobile Manufacturers' Association)",
        "site": "vama.org.vn",
        "url": "http://vama.org.vn",
        "country": "VN",
        "note": "Member companies only; VinFast (and some periods Hyundai "
                "Thanh Cong) publish separately and are absent.",
    },
    "fti": {
        "name": "FTI (Federation of Thai Industries) via AutoLife Thailand",
        "site": "autolifethailand.tv",
        "url": "https://autolifethailand.tv",
        "country": "TH",
        "note": "Official FTI automotive-club figures, republished in full by "
                "AutoLife Thailand; Thai Buddhist Era calendar (BE-543 = CE).",
    },
    "kaidee": {
        "name": "Kaidee (Thailand online classifieds marketplace)",
        "site": "kaidee.com",
        "url": "https://www.kaidee.com/browse?category=cars",
        "country": "TH",
        "note": "Thailand's largest C2C/classifieds marketplace. Each car ad is one "
                "row (used + new inventory), giving the high-volume 'marketplace "
                "listings' layer that mirrors the Japan project's carsensor/goo-net "
                "data. Brand/model/year/mileage/fuel parsed from the ad's tracking "
                "metadata; province parsed from the ad location.",
    },
    "publicitytop": {
        "name": "Publicity Top (Thailand new-car sales rankings by brand & model)",
        "site": "publicitytop.com",
        "url": "https://publicitytop.com",
        "country": "TH",
        "note": "Publishes a monthly 'Thailand <Month> <Year>:' report with the full "
                "brand ranking (Top ~45) and model ranking (Top ~206) as "
                "concatenated text. A WordPress REST API enumerates every report. We "
                "parse each into sales_monthly at level='maker'/'model', giving "
                "Thailand a dense, Japan-style brand/model sales layer on top of the "
                "Kaidee marketplace inventory.",
    },
}

# --- News feeds ---------------------------------------------------------------
NEWS_FEEDS = [
    {"country": "TH", "source": "headlightmag", "lang": "th",
     "site": "headlightmag.com", "name": "Headlight Magazine",
     "url": "https://www.headlightmag.com/feed/"},
    {"country": "TH", "source": "autolifethailand", "lang": "th",
     "site": "autolifethailand.tv", "name": "AutoLife Thailand",
     "url": "https://autolifethailand.tv/feed/"},
    {"country": "VN", "source": "vnexpress-oto", "lang": "vi",
     "site": "vnexpress.net", "name": "VnExpress Ô tô",
     "url": "https://vnexpress.net/rss/oto-xe-may.rss"},
    {"country": "VN", "source": "tuoitre-xe", "lang": "vi",
     "site": "tuoitre.vn", "name": "Tuổi Trẻ Xe",
     "url": "https://tuoitre.vn/rss/xe.rss"},
    {"country": "VN", "source": "thanhnien-xe", "lang": "vi",
     "site": "thanhnien.vn", "name": "Thanh Niên Xe",
     "url": "https://thanhnien.vn/rss/xe.rss"},
]

# Thai month names -> month number (full and abbreviated forms)
THAI_MONTHS = {
    "มกราคม": 1, "ม.ค.": 1,
    "กุมภาพันธ์": 2, "ก.พ.": 2,
    "มีนาคม": 3, "มี.ค.": 3,
    "เมษายน": 4, "เม.ย.": 4,
    "พฤษภาคม": 5, "พ.ค.": 5,
    "มิถุนายน": 6, "มิ.ย.": 6,
    "กรกฎาคม": 7, "ก.ค.": 7,
    "สิงหาคม": 8, "ส.ค.": 8,
    "กันยายน": 9, "ก.ย.": 9,
    "ตุลาคม": 10, "ต.ค.": 10,
    "พฤศจิกายน": 11, "พ.ย.": 11,
    "ธันวาคม": 12, "ธ.ค.": 12,
}

# Buddhist Era -> Common Era
BE_OFFSET = 543

ENGLISH_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
MONTH_NAMES_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
