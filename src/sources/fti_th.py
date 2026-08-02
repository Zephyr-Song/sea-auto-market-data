"""Thailand — FTI monthly sales figures, by powertrain and body segment.

The Federation of Thai Industries (สภาอุตสาหกรรมแห่งประเทศไทย, "ส.อ.ท.") releases
Thailand's official monthly sales numbers through a spokesperson briefing.
AutoLife Thailand republishes those briefings verbatim and, being WordPress,
exposes a REST API — far more stable than scraping the rendered page.

Identifying a genuine briefing
------------------------------
Searching for "ยอดขายรถยนต์" alone is far too loose: only ~15% of the hits are
actual briefings, the rest are forecasts and commentary that would poison the
dataset with half-parsed numbers. Two gates are applied instead:

1. the body must name the FTI automotive spokesperson / the federation, and
2. the headline sentence must match :data:`HEADLINE_RE`.

The headline wording drifts month to month, so the regex tolerates all observed
variants::

    ยอดขายรถยนต์ เดือนมกราคม 2569 อยู่ที่ 73,936 คัน เติบโตขึ้น 53.77%
    ยอดขายรถยนต์ ในประเทศไทย เดือนมิถุนายน ของปี 2569 มียอดขายรวมอยู่ที่ 58,724 คัน เพิ่มขึ้น 17.26%
    ยอดขายรถยนต์ ในประเทศไทยเดือนพฤษภาคม 2569 มีจำนวนอยู่ที่ 57,765 คัน เพิ่มขึ้น 10.60%

Two Thai-specific gotchas:

* Years are Buddhist Era — 2569 BE == 2026 CE (offset 543).
* ``ลดลง`` ("decreased") negates the percentage; ``เพิ่มขึ้น`` / ``เติบโตขึ้น`` /
  ``โต`` ("increased"/"grew") keep it positive.
"""
from __future__ import annotations

import re

from ..config import ALT_API, THAI_MONTHS, BE_OFFSET
from .. import db
from .base import get, strip_html, to_int, to_float

SOURCE = "fti"
COUNTRY = "TH"

# Full Thai month names, longest first so the alternation never matches a prefix.
_FULL_MONTHS = sorted((m for m in THAI_MONTHS if "." not in m), key=len, reverse=True)
_MONTH_ALT = "|".join(_FULL_MONTHS)

HEADLINE_RE = re.compile(
    r"ยอดขายรถยนต์\s*(?:ในประเทศไทย)?\s*เดือน\s*(" + _MONTH_ALT + r")\s*"
    r"(?:ของปี)?\s*(25\d\d)\s*"
    r"(?:มียอดขายรวมอยู่ที่|มีจำนวนอยู่ที่|มียอดขายอยู่ที่|อยู่ที่|มีจำนวน)\s*"
    r"([\d,]+)\s*คัน"
    r"(?:\s*(เพิ่มขึ้น|ลดลง|เติบโตขึ้น|โต)\s*([\d.,]+)\s*%)?"
)

# Markers that identify an official FTI briefing rather than commentary.
OFFICIAL_MARKERS = ("ไพสิฐพัฒนพงษ์", "สภาอุตสาหกรรมแห่งประเทศไทย")

# Passenger-car powertrain breakdowns. The prefix drifts between articles:
# newer ones use "รถยนต์นั่งและรถยนต์อเนกประสงค์" (passenger car AND SUV), while
# early-2026 briefings use the shorter "รถยนต์นั่ง". The middle token also drifts
# ("เครื่องยนต์สันดาปภายใน" vs "สันดาปภายใน"; "พลังงานไฟฟ้า (BEV)" vs "ไฟฟ้า (BEV)";
# REEV paren-order flips). Anchor on the full passenger phrase so the
# commercial-vehicle BEV ("รถกระบะไฟฟ้า (BEV)") never collides.
_PREFIX = r"(?:รถยนต์นั่งและรถยนต์อเนกประสงค์|รถยนต์นั่ง)"
POWERTRAIN_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("powertrain", "ICE", re.compile(
        _PREFIX + r"(?:เครื่องยนต์)?\s*สันดาปภายใน\s*\(ICE\)")),
    ("powertrain", "BEV", re.compile(
        _PREFIX + r"(?:\s*พลังงาน)?\s*ไฟฟ้า\s*\(BEV\)")),
    ("powertrain", "PHEV", re.compile(
        _PREFIX + r"\s*ปลั๊กอินไฮบริด\s*\(PHEV\)")),
    ("powertrain", "REEV", re.compile(
        _PREFIX + r"\s*(?:REEV\s*\(Range-Extended Electric Vehicle\)|"
        r"Range-Extended Electric Vehicle\s*\(REEV\))")),
    ("powertrain", "HEV", re.compile(
        _PREFIX + r"\s*ไฮบริด\s*\(HEV\)")),
]

# Commercial-vehicle (pickup / 1-ton) breakdowns. PICKUP_1T is the "pure pickup"
# total; the electric / REEV / HEV pickups underneath it are ignored. The
# phrasing differs too: "ยอดขายรถกระบะ" / "ยอดขายรถกระบะ (Pure Pickup)" vs the
# older "รถกระบะ 1 ตัน".
PICKUP_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("segment", "PICKUP_1T", re.compile(
        r"(?:ยอดขายรถกระบะ(?:\s*\(Pure Pickup\))?|รถกระบะ\s*1\s*ตัน)")),
    ("segment", "PPV", re.compile(r"รถกระบะดัดแปลง\s*\(PPV\)")),
]

# Cumulative (year-to-date) total sales sentence, best-effort.
_YTD_TOTAL_RE = re.compile(
    r"ยอดขายรถยนต์\s*สะสม\s*\d+\s*เดือน[^คัน]*?อยู่ที่\s*([\d,]+)\s*คัน")

_DECREASE = ("ลดลง",)
# Value always follows a verb phrase; requiring it avoids grabbing the share %.
_VALUE_RE = re.compile(
    r"(?:มียอดขายอยู่ที่|มีจำนวนอยู่ที่|มีจำนวน|อยู่ที่)\s*([\d,]+)\s*คัน?")
_PCT_RE = re.compile(r"(ลดลง|เพิ่มขึ้น|เติบโตขึ้น|โต)\s*([\d.,]+)\s*%")
# A YoY % / YTD test must belong to the same clause as its value. Stop the
# search at the next "และ" (and) / "ส่วน" or the next vehicle category's anchor,
# so the following category's % (or the YTD block's "ช่วงเดียวกัน") can't leak
# backwards into the current clause (e.g. monthly PPV must not read as YTD).
_BOUNDARY = re.compile(
    r" และ| ส่วน|รถยนต์นั่งและ| รถกระบะ| รถจักรยานยนต์| รถบรรทุก| รถประเภทอื่น")

SEARCH_TERMS = ("ยอดขายรถยนต์", "ไพสิฐพัฒนพงษ์")


def _signed_pct(direction: str | None, value: float | None) -> float | None:
    if value is None:
        return None
    return -value if direction in _DECREASE else value


def _extract_metric(text: str, start: int) -> dict | None:
    """From ``start`` (end of a code anchor), pull the following value, YoY % and
    whether the sentence is a year-to-date (cumulative) figure.

    The value must sit close to the anchor — briefings sometimes mention
    "ยอดขายรถกระบะ" in commentary with no nearby number, and a loose search would
    swallow a far-away YTD total. Capping the window at 90 chars rejects those.
    """
    window = text[start: start + 90]
    vm = _VALUE_RE.search(window)
    if not vm:
        return None
    val = to_int(vm.group(1))
    after = start + vm.end()
    # Bound the % search (and the YTD test) to the current clause, so neither
    # can reach into the next category or the YTD block.
    bnd = _BOUNDARY.search(text, after)
    end = bnd.start() if bnd else after + 120
    pm = _PCT_RE.search(text, after, end)
    pct = _signed_pct(pm.group(1), to_float(pm.group(2))) if pm else None
    seg = text[after: end]
    # Within one clause only one of the two markers appears; the monthly one
    # wins if both somehow show (it never should once the clause is bounded).
    if "เดือนเดียวกัน" in seg:
        is_ytd = False
    elif "ช่วงเดียวกัน" in seg:
        is_ytd = True
    else:
        is_ytd = False
    return {"units": val, "yoy_pct": pct, "is_ytd": is_ytd}


def parse_briefing(text: str, url: str) -> tuple[int, int, list[dict]] | None:
    """Parse one briefing. Returns ``(year, month, rows)`` or ``None``."""
    if not any(mk in text for mk in OFFICIAL_MARKERS):
        return None
    head = HEADLINE_RE.search(text)
    if not head:
        return None

    month = THAI_MONTHS[head.group(1)]
    year = int(head.group(2)) - BE_OFFSET
    base = {
        "country": COUNTRY, "year": year, "month": month,
        "maker": "", "model": "", "seats": "", "region": "ALL",
        "units_ytd": None, "is_subtotal": 0,
        "source": SOURCE, "source_url": url,
    }

    # TOTAL (monthly) from the headline sentence.
    rows = [{
        **base, "level": "total", "category": "TOTAL",
        "units": to_int(head.group(3)),
        "yoy_pct": _signed_pct(head.group(4), to_float(head.group(5))),
    }]
    # TOTAL YTD, best-effort.
    ytd_total = _YTD_TOTAL_RE.search(text)
    if ytd_total:
        rows[0]["units_ytd"] = to_int(ytd_total.group(1))

    # Powertrain + pickup breakdowns. Each code appears up to twice (monthly,
    # then YTD); collect both, keyed by category.
    collected: dict[str, dict] = {}
    for level, code, pat in (*POWERTRAIN_PATTERNS, *PICKUP_PATTERNS):
        for m in pat.finditer(text):
            info = _extract_metric(text, m.end())
            if not info:
                continue
            slot = collected.setdefault(code, {"level": level, "monthly": None, "ytd": None})
            if info["is_ytd"]:
                if slot["ytd"] is None:
                    slot["ytd"] = info
            else:
                if slot["monthly"] is None:
                    slot["monthly"] = info

    for code, slot in collected.items():
        mo = slot["monthly"]
        ytd = slot["ytd"]
        if not mo and not ytd:
            continue
        # Never fabricate a monthly figure from a YTD-only sentence: some months
        # (e.g. 2026-03) report only the cumulative number.
        units = mo["units"] if mo else None
        yoy = mo["yoy_pct"] if mo else None
        units_ytd = ytd["units"] if ytd else None
        rows.append({
            **base, "level": slot["level"], "category": code,
            "units": units, "yoy_pct": yoy, "units_ytd": units_ytd,
        })

    seen, out = set(), []
    for r in rows:
        if r["category"] in seen:
            continue
        if r["units"] is None and r["units_ytd"] is None:
            continue
        seen.add(r["category"])
        out.append(r)
    return year, month, out


def _iter_posts(max_pages: int = 5):
    seen_links: set[str] = set()
    for term in SEARCH_TERMS:
        for page in range(1, max_pages + 1):
            try:
                resp = get(ALT_API, params={
                    "search": term, "per_page": 50, "page": page,
                    "_fields": "id,date,link,title,content",
                })
                batch = resp.json()
            except Exception:
                break
            if not isinstance(batch, list) or not batch:
                break
            for post in batch:
                link = post.get("link")
                if link and link not in seen_links:
                    seen_links.add(link)
                    yield post
            if len(batch) < 50:
                break


def fetch(full: bool = False, limit: int | None = None) -> int:
    total = 0
    if full:
        n = db.clear_source(COUNTRY, SOURCE)
        print(f"  [fti] cleared {n} stale rows for clean --full re-crawl")
    have = set() if full else db.existing_periods(COUNTRY, SOURCE)
    latest = max(have) if have else None  # always refresh the newest stored month
    briefings = 0

    with db.run_tracker(f"{SOURCE}:sales") as counter:
        for post in _iter_posts():
            body = strip_html(post["content"]["rendered"])
            parsed = parse_briefing(body, post["link"])
            if not parsed:
                continue
            year, month, rows = parsed
            briefings += 1
            if (year, month) in have and (year, month) != latest:
                continue
            if not rows:
                continue
            n = db.upsert_sales(rows)
            total += n
            counter["rows"] = total
            cats = ",".join(r["category"] for r in rows)
            print(f"  [fti] {year}-{month:02d} -> {n} metrics [{cats}]")
            if limit and total >= limit:
                break
    print(f"  [fti] official briefings recognised: {briefings}")
    return total
