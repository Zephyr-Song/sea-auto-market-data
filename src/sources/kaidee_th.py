"""Thailand used/new-car marketplace listings via Kaidee (the Japan-repo method).

Kaidee (https://www.kaidee.com) is Thailand's largest C2C/classifieds marketplace.
Its browse pages are server-rendered: the full listing payload lives in the
``__NEXT_DATA__`` JSON blob, so we can pull structured ad data with plain HTTP
(no browser needed). We scope to the cars category via ``categoryId=11`` (the
Thai "รถยนต์" = automobile category) and keep ONLY rows whose ``categoryName`` is
exactly ``"รถยนต์"`` — Kaidee's browse feed otherwise mixes in recommendations from
other categories (phones, amulets, pets...), so this filter is what makes the
table genuinely "car" data.

Each kept ad carries rich metadata:

    tracking.gtmData -> brand, model, year, mileage, fuel_type, price
    location         -> "<district> <province>"  ( province = last token )
    price / title / conditionName / firstApprovedTime / member.role

One ad == one row in ``th_car_listings``. This is the high-volume "marketplace
inventory" layer that mirrors japan-car-market's carsensor/goo-net data and gives
Thailand a dataset comparable in scale to Vietnam's VAMA model-level table.

The cars feed holds tens of thousands of live ads; we paginate (24 ads/page) to
collect the requested target.
"""
from __future__ import annotations

import json
import random
import re
import time
from typing import Iterable, Iterator

import requests

from ..config import SOURCES, USER_AGENT, REQUEST_TIMEOUT
from ..db import upsert_listing, clear_listings

COUNTRY = "TH"
SOURCE = "kaidee"
SRC = SOURCES[SOURCE]

# categoryId=11 == Thai "รถยนต์" (automobiles). Scoping here keeps the feed ~90%
# cars; the parser then hard-filters to categoryName == "รถยนต์" for a clean set.
BROWSE = "https://www.kaidee.com/browse?categoryId=11"
DETAIL = "https://www.kaidee.com/ads/{id}"
PER_PAGE = 24

# Kaidee condition labels -> normalised value
_COND_MAP = {
    "มือสอง": "used",
    "มือสอง (รถบ้าน)": "used",
    "ใหม่": "new",
    "มือหนึ่ง": "new",
}

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _norm_condition(raw: str) -> str:
    if not raw:
        return ""
    for k, v in _COND_MAP.items():
        if k in raw:
            return v
    return raw


def _province(location: str) -> str:
    if not location:
        return ""
    # "บางแค กรุงเทพมหานคร" -> last whitespace/comma token is the province.
    for sep in (",", " "):
        if sep in location:
            return location.rsplit(sep, 1)[-1].strip()
    return location.strip()


def _to_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        m = re.search(r"\d+", str(v))
        return int(m.group()) if m else None


def parse_ad(ad: dict) -> dict | None:
    """Turn one Kaidee ad object into a warehouse row (or None if unusable).

    Hard filter: keep ONLY cars (``categoryName == "รถยนต์"``). Kaidee's browse feed
    injects recommendations from other categories, so this is what guarantees the
    row is actually an automobile listing.
    """
    if not ad or not ad.get("id"):
        return None
    if (ad.get("categoryName") or "").strip() != "รถยนต์":
        return None
    gtm = (ad.get("tracking") or {}).get("gtmData") or {}
    auto = ad.get("autoInfo") or {}

    maker = (gtm.get("brand") or "").strip()
    model = (gtm.get("model") or "").strip()
    year = _to_int(gtm.get("year"))
    mileage = _to_int(gtm.get("mileage"))
    fuel = (gtm.get("fuel_type") or "").strip()
    if not maker and ad.get("title"):
        # light fallback: first title token often equals the brand
        maker = ad["title"].split()[0] if ad["title"].split() else ""
    if year is None and ad.get("title"):
        m = _YEAR_RE.search(ad["title"])
        if m:
            y = int(m.group())
            if 1980 <= y <= 2027:
                year = y

    price = _to_int(ad.get("price"))
    if price is None or price <= 0:
        return None  # price is mandatory for a usable listing row

    lid = str(ad["id"])
    return {
        "country": COUNTRY,
        "listing_id": lid,
        "source": SOURCE,
        "source_name": SRC["name"],
        "source_site": SRC["site"],
        "source_url": DETAIL.format(id=lid),
        "title": (ad.get("title") or "").strip(),
        "maker": maker,
        "model": model,
        "year": year,
        "price_thb": price,
        "province": _province(ad.get("location") or ""),
        "condition": _norm_condition(ad.get("conditionName") or ""),
        "category": (ad.get("categoryName") or "").strip(),
        "mileage_km": mileage,
        "fuel_type": fuel,
        "body_type": (auto.get("carType") or "").strip(),
        "image_url": (ad.get("image") or "").strip(),
        "seller_type": ((ad.get("member") or {}).get("role") or "").strip(),
        "listed_at": ad.get("firstApprovedTime"),
    }


def _fetch_page(session: requests.Session, page: int, extra: dict, delay: float) -> list[dict]:
    """Return the list of raw ad dicts on one browse page.

    Kaidee throttles long crawls: a throttled page often comes back as HTTP 200
    with NO ``ads`` (or no ``__NEXT_DATA__`` at all) rather than a 429. We treat
    that as *transient throttle*: back off ONCE with a long sleep and retry the
    same page a couple of times. We deliberately keep this to 2 tries / few
    requests — hammering a throttled endpoint only prolongs the throttle.
    """
    params = {"page": page, **extra}
    url = BROWSE + "&" + "&".join(f"{k}={v}" for k, v in params.items())
    last: list[dict] = []
    for attempt in range(2):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
        except Exception:
            time.sleep(5 + attempt * 5)
            continue
        if r.status_code == 200:
            m = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
            if not m:
                time.sleep(10 + attempt * 10)  # blocked/empty HTML -> throttle
                continue
            try:
                d = json.loads(m.group(1))
            except Exception:
                time.sleep(5 + attempt * 5)
                continue
            ads = ((d.get("props") or {}).get("pageProps") or {}).get("ads") or []
            if not ads:
                time.sleep(10 + attempt * 10)  # 200 but empty -> throttle
                continue
            return ads
        if r.status_code in (429, 503):
            time.sleep(15 + attempt * 15)
            continue
        return []  # other hard status (e.g. 403) -> give up this page
    return last


def iter_ads(extra: dict | None = None, target: int = 13_000,
             max_pages: int = 8000, consecutive_empty_limit: int = 30,
             delay: float = 1.5, start_page: int = 1) -> Iterator[dict]:
    """Yield parsed car-listing rows for one browse query, paginating until
    ``target``, ``max_pages``, or ``consecutive_empty_limit`` consecutive empty
    pages.

    Kaidee throttles aggressive crawlers, so we stay polite (≈1.5s between pages
    with jitter) and treat a short run of empty pages as a transient throttle
    rather than the end of the result set — only a long run of empties (e.g. a
    sustained block) means we are genuinely done. The car feed itself runs deep
    (800+ pages), so a polite crawl reaches the 10k+ target without trouble.

    ``start_page`` lets a crawl resume past already-collected pages instead of
    re-fetching them.
    """
    extra = extra or {}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    collected = 0
    consecutive_empty = 0
    for page in range(start_page, max_pages + 1):
        ads = _fetch_page(session, page, extra, delay)
        if not ads:
            consecutive_empty += 1
            if consecutive_empty >= consecutive_empty_limit:
                break
            time.sleep(min(consecutive_empty * 4, 60))  # ride out throttle windows
            continue
        consecutive_empty = 0
        for ad in ads:
            row = parse_ad(ad)
            if row:
                yield row
                collected += 1
        if collected >= target:
            break
        time.sleep(delay * (0.8 + random.random() * 0.5))  # jitter
    return


# Major brands on the Thai used/new-car market. Brand-filtered browse paginates
# independently of the global view, so looping brands guarantees we cross the
# 10k-row target even if the global browse caps out.
BRANDS = [
    "Toyota", "Honda", "Isuzu", "Mazda", "Ford", "MG", "BYD", "Nissan",
    "Mitsubishi", "Chevrolet", "Suzuki", "Kia", "Hyundai", "Mercedes-Benz",
    "BMW", "Hino", "Mazda", "Subaru", "Volkswagen", "Audi",
]


def fetch(full: bool = False, limit: int | None = None, start_page: int = 1) -> int:
    """Crawl Kaidee listings and store them.

    ``full`` clears existing rows first (clean re-crawl). ``limit`` caps the number
    of listings collected (default 13,000 -> comfortably above the 10k target).
    ``start_page`` resumes the global browse past already-collected pages.
    Starts from the global car browse, then tops up with per-brand browses (dedup
    by listing_id) until the target is met.
    """
    target = limit or 13_000
    if full:
        clear_listings(SOURCE)
    rows: list[dict] = []
    for row in iter_ads(target=target, start_page=start_page):
        rows.append(row)
    if len(rows) < target:
        for brand in BRANDS:
            for row in iter_ads(extra={"q": brand}, target=target - len(rows)):
                rows.append(row)
            if len(rows) >= target:
                break
            time.sleep(0.8)
    written = upsert_listing(rows)
    return written
