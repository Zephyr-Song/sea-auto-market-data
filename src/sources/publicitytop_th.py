"""Thailand new-car sales by brand & model — publicitytop.com monthly rankings.

publicitytop.com publishes a monthly ``Thailand <Month> <Year>:`` report with the
full brand ranking (Top ~45) and model ranking (Top ~206) embedded as
*concatenated text* inside ``<p>`` tags (e.g. ``"PosBrandMay-25%Apr2025%PosFY24
1Toyota20,17036.7%1103,79639.0%1..."``). A WordPress REST API
(``wp-json/wp/v2/posts``) lets us enumerate every Thailand sales-report post.

We parse each post into :data:`sales_monthly` rows at ``level='maker'`` and
``level='model'`` (``country=TH``). Together with the Kaidee marketplace
inventory (``th_car_listings``) and the FTI monthly totals, this gives Thailand a
dense, Japan-style brand/model sales layer — the kind of structure that lets the
project cross 10,000 Thai rows and supports real market-share analysis.

Parsing notes
-------------
* The ranking text has no fixed column width; values are glued together. The
  reliable anchors are: the **brand/model name** (starts with a letter, may
  contain digits for models like ``BYD Sealion 6 Dm-i``) followed by the
  **monthly sales** (a thousands-comma-grouped integer, e.g. ``20,170``) followed
  by the **monthly share** (``36.7%``). We anchor on that triple and let the
  optional year-to-date tail (prev-rank, FY sales, FY share) be consumed so it
  never bleeds into the next row.
* Market share is *computed* in the analysis layer (brand units / total units per
  month) rather than trusted from the glued text, so it is internally consistent.
* The leading position integer is intentionally ignored; rank = sequential match
  order within a section.
"""
from __future__ import annotations

import re
import time
from typing import Iterable, Iterator

import requests

from ..config import USER_AGENT, REQUEST_TIMEOUT, SOURCES
from .. import db

SOURCE = "publicitytop"
COUNTRY = "TH"
API = "https://publicitytop.com/wp-json/wp/v2/posts"
WP_H = {"User-Agent": USER_AGENT}
PAGE_H = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

# One ranking row: Name + monthly sales (comma-grouped) + monthly share, with an
# optional FY (year-to-date) tail we consume so it can't bleed into the next row.
ROW = re.compile(
    r'([A-Za-z][A-Za-z0-9 &.\x80\x99\'\\-]*?)'          # 1 Name
    r'(\d{1,3}(?:,\d{3})*)'                              # 2 MonthlySales
    r'([\d.]+%)'                                         # 3 MonthlyShare
    r'(?:[^%]*?(\d{1,3}(?:,\d{3})*)\s*([\d.]+%))?'       # 4,5 optional FY sales/share
)

MONTHLY_RE = re.compile(
    r"Thailand\s+(" + "|".join(MONTHS) + r")\s+(\d{4})\s*:", re.I)
ANNUAL_RE = re.compile(r"Thailand\s+Full\s+Year\s+(\d{4})\s*:", re.I)


def _to_int(s: str | None) -> int | None:
    if not s:
        return None
    return int(s.replace(",", "").strip())


def _to_pct(s: str | None) -> float | None:
    if not s:
        return None
    return float(s.replace("%", "").strip())


def parse_title(title: str) -> tuple[int, int, str] | None:
    """Return ``(year, month, kind)`` for a sales-report title, else ``None``.

    ``kind`` is ``'month'`` (month 1-12) or ``'year'`` (month 0 = annual).
    """
    m = ANNUAL_RE.search(title)
    if m:
        return int(m.group(1)), 0, "year"
    m = MONTHLY_RE.search(title)
    if m:
        return int(m.group(2)), MONTHS[m.group(1).capitalize()], "month"
    return None


def iter_post_links() -> Iterator[tuple[str, str, tuple[int, int, str]]]:
    """Yield ``(link, title, (year, month, kind))`` for Thailand sales reports."""
    page = 1
    while True:
        try:
            resp = requests.get(API, params={
                "search": "Thailand", "per_page": 100, "page": page,
                "_fields": "date,link,title",
            }, headers=WP_H, timeout=REQUEST_TIMEOUT)
            data = resp.json()
        except Exception:
            break
        if not isinstance(data, list) or not data:
            break
        for post in data:
            title = re.sub(r"<[^>]+>", "", post.get("title", {}).get("rendered", ""))
            meta = parse_title(title)
            if not meta:
                continue
            yield post.get("link"), title, meta
        if len(data) < 100:
            break
        page += 1


def _extract_section(html: str, start_marker: str, end_marker: str | None = None) -> str:
    """Return the ranking text between ``start_marker`` and ``end_marker``.

    HTML tags are stripped, trailing conclusion prose (after the table, usually
    introduced by the word 'below') is cut off, and the leading header row is
    stripped at the first 'FY24' column label. Returns '' if the start marker is
    absent (e.g. annual summary posts that carry no ranking table).
    """
    i = html.find(start_marker)
    if i < 0:
        return ""
    if end_marker:
        j = html.find(end_marker, i + len(start_marker))
        seg = html[i:j] if j > i else html[i:i + 60000]
    else:
        seg = html[i:i + 60000]
    seg = re.sub(r"<[^>]+>", "", seg)
    # cut trailing conclusion prose after the ranking table
    for stop in ("below", "Below", "BELOW"):
        k = seg.find(stop)
        if k > 0:
            seg = seg[:k]
            break
    # Strip the column-header row ("PosBrandJan-26%/25Dec" / "PosModel...").
    # CRITICAL: if left in, the regex matches it as a fake brand and its optional
    # FY tail *consumes the #1 brand's number*, silently dropping every month's
    # top brand (e.g. Toyota). Remove it up to the first "rank + real brand"
    # position. We exclude month abbreviations (Jan..Dec) from the lookahead so
    # the prev-month column label (e.g. "/25Dec") is not mistaken for a brand.
    seg = re.sub(
        r"Pos(?:Brand|Model).*?(?=\d+(?!Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|"
        r"Oct|Nov|Dec)[A-Z][a-z])", "", seg, flags=re.S)
    # strip the header row up to the first FY24 column label (some layouts)
    seg = seg.split("FY24", 1)[-1]
    return seg


def parse_rows(text: str) -> list[dict]:
    """Parse a ranking section into rows of
    ``{name, units, share_pct, ytd}`` (units/ytd already ints)."""
    out = []
    for m in ROW.finditer(text):
        name = m.group(1).strip()
        if not name:
            continue
        out.append({
            "name": name,
            "units": _to_int(m.group(2)),
            "share_pct": _to_pct(m.group(3)),
            "ytd": _to_int(m.group(4)),
        })
    return out


def _split_maker_model(model_name: str, brands: set[str]) -> tuple[str, str]:
    """Split a model string into (maker, model) using known brand prefixes.

    Falls back to first-token / whole-string if no brand matches.
    """
    s = model_name.strip()
    best = None
    for b in brands:
        if s == b:
            return b, ""
        if s.startswith(b + " "):
            if best is None or len(b) > len(best):
                best = b
    if best:
        return best, s[len(best):].strip()
    # fallback: first token is the maker
    parts = s.split(" ", 1)
    return parts[0], (parts[1].strip() if len(parts) > 1 else "")


def _base_row(year: int, month: int, kind: str, link: str) -> dict:
    src = SOURCES[SOURCE]
    return {
        "country": COUNTRY, "year": year, "month": month,
        "level": "", "maker": "", "model": "", "category": "",
        "seats": "", "region": "ALL",
        "units": None, "units_ytd": None, "yoy_pct": None, "is_subtotal": 0,
        "source": SOURCE, "source_url": link,
        "source_name": src["name"], "source_site": src["site"],
    }


def fetch(full: bool = False, limit: int | None = None) -> int:
    """Crawl publicitytop Thailand rankings and store them.

    ``full`` clears existing rows first (clean re-crawl). Monthly reports become
    ``level='maker'`` / ``level='model'`` rows (month 1-12). Full-Year (annual)
    posts are skipped — they carry annual cumulative figures, not monthly data,
    and their glued text corrupts the per-model parse.
    """
    if full:
        n = db.clear_source(COUNTRY, SOURCE)
        print(f"  [publicitytop] cleared {n} stale rows for clean --full re-crawl")

    total = 0
    posts = list(iter_post_links())
    print(f"  [publicitytop] found {len(posts)} Thailand sales-report posts")

    with db.run_tracker(f"{SOURCE}:sales") as counter:
        for link, title, (year, month, kind) in posts:
            # Full-Year (month=0) posts carry annual cumulative figures, not
            # monthly — they are not comparable to the monthly series and their
            # glued text also corrupts the per-model parse, so we skip them.
            if kind == "year":
                print(f"  [publicitytop] skip annual post: {title}")
                continue
            try:
                r = requests.get(link, headers=PAGE_H, timeout=REQUEST_TIMEOUT)
                html = r.text
            except Exception as e:
                print(f"  [publicitytop] fetch failed {link}: {e}")
                continue

            brands_text = _extract_section(html, "brands:", "models:")
            models_text = _extract_section(html, "models:")
            brand_rows = parse_rows(brands_text)
            model_rows = parse_rows(models_text)
            if not brand_rows and not model_rows:
                print(f"  [publicitytop] no rows parsed: {title}")
                continue

            # Brand total for this month — used to recompute model units from the
            # reliably-parsed share% (the glued model units are corrupted whenever
            # a model name ends in a digit, e.g. "BYD Sealion 7" -> "71,151"), and
            # to validate each model row against its maker's total.
            t_brand = sum(b["units"] for b in brand_rows if b["units"])
            maker_total = {b["name"]: b["units"] for b in brand_rows if b["units"]}

            brands = {b["name"] for b in brand_rows}
            rows: list[dict] = []

            for b in brand_rows:
                if b["units"] is None:
                    continue
                r0 = _base_row(year, month, kind, link)
                r0.update(level="maker", maker=b["name"], model="",
                          units=b["units"], units_ytd=b["ytd"] or None)
                rows.append(r0)

            for m in model_rows:
                if m["units"] is None or m["share_pct"] is None:
                    continue
                maker, model = _split_maker_model(m["name"], brands)
                # Brand-subtotal lines inside the model section (e.g. "MG 46,359"
                # with no share) parse as model='' — redundant with maker level.
                if model == "" or maker not in maker_total:
                    continue
                # Recompute model units from the reliably-parsed share% × brand
                # total (consistent, immune to name/number gluing).
                units = round(m["share_pct"] * t_brand / 100.0) if t_brand else m["units"]
                # A genuine model can never exceed its maker's monthly total;
                # rows that do are corrupted brand-subtotal/glue artifacts
                # (whose share is also wrong) and are dropped.
                if units <= 0 or units > maker_total[maker]:
                    continue
                r0 = _base_row(year, month, kind, link)
                r0.update(level="model", maker=maker, model=model,
                          units=units, units_ytd=None)
                rows.append(r0)

            written = db.upsert_sales(rows)
            total += written
            counter["rows"] = total
            print(f"  [publicitytop] {title} -> {written} rows "
                  f"({len(brand_rows)} brands / {len(model_rows)} models)")
            if limit and total >= limit:
                break
            time.sleep(0.4)
    return total


# Re-export for callers that iterate posts directly (used by analysis/preview).
__all__ = ["fetch", "iter_post_links", "parse_title", "parse_rows"]
