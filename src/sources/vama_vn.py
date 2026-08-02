"""Vietnam — VAMA monthly sales reports (model-level).

The Vietnam Automobile Manufacturers' Association publishes a monthly bundle of
PDFs at a fully predictable URL:

    http://vama.org.vn/vn/bao-cao-ban-hang-thang-{month}-nam-{year}.html

The bundle contains several files; ``... - Detail.pdf`` is the interesting one:
a ~200-row table of every model sold by a VAMA member, broken out by region.

Table layout (14 columns, 2 header rows)::

    Maker | Model name | Vama Clasiffication | Seat |
    Sales - <Mon> <Year>: North | Central | South | Total | Share |
    Sales - YTM  <Year>: North | Central | South | Total | Share

Caveats worth knowing about the data itself:

* VAMA covers **member companies only**. VinFast, and for some periods Hyundai
  Thanh Cong, publish separately and are therefore absent from these figures.
* ``Sub-total`` rows are kept but tagged via ``is_subtotal`` so aggregate queries
  can exclude them.
* pdfplumber occasionally splits digit groups ("1 ,254"); ``to_int`` normalises.
"""
from __future__ import annotations

import re
from datetime import date

import pdfplumber

from ..config import VAMA_REPORT_URL, VAMA_START, RAW_DIR, MONTH_NAMES_EN
from .. import db
from .base import get, download, to_int

SOURCE = "vama"
COUNTRY = "VN"

# First four columns are stable across every VAMA layout; the region/total
# column positions are detected per-table by _detect_columns().
C_MAKER, C_MODEL, C_CLASS, C_SEAT = 0, 1, 2, 3

_HEADER_TOKENS = {"maker", "model name", "vama clasiffication", "seat", "north",
                  "central", "south", "total", "share"}
_SKIP_MODELS = {"không báo cáo", ""}


def _clean(cell) -> str:
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def report_page_url(year: int, month: int) -> str:
    return VAMA_REPORT_URL.format(month=month, year=year)


def find_detail_pdf(year: int, month: int) -> str | None:
    """Return the absolute URL of the model-level Detail PDF, if published."""
    try:
        resp = get(report_page_url(year, month))
    except Exception:
        return None
    links = re.findall(r'href="([^"]*\.pdf)"', resp.text, re.I)
    if not links:
        return None
    detail = [l for l in links if "detail" in l.lower()]
    chosen = detail[0] if detail else None
    if not chosen:
        return None
    if chosen.startswith("http"):
        return chosen
    return "http://vama.org.vn" + ("" if chosen.startswith("/") else "/") + chosen


def _is_header(row) -> bool:
    joined = " ".join(_clean(c).lower() for c in row[:4])
    return any(tok in joined for tok in ("maker", "model name")) or joined.strip() == ""


def _detect_columns(table: list[list]) -> tuple[list[int], list[int]] | None:
    """Locate the per-block column indices from the sub-header row.

    VAMA PDFs publish two blocks (``Sales - <Mon>`` and ``Sales - YTM``) each
    with North/Central/South/Total. Some months insert an extra ``Share``
    column, shifting the YTM block by one (15 cols vs 14) — so we can't
    hardcode indices. We scan the sub-header row for the markers and return
    ``(month_idx[N,C,S,T], ytd_idx[N,C,S,T])``.
    """
    for row in table:
        cleaned = [_clean(c).lower() for c in row]
        if "north" in cleaned and "total" in cleaned:
            idxs = sorted(i for i, c in enumerate(cleaned)
                          if c in ("north", "central", "south", "total"))
            if len(idxs) >= 8:
                return idxs[:4], idxs[4:8]
    return None


def parse_detail_pdf(path, year: int, month: int, source_url: str) -> list[dict]:
    """Parse a Detail PDF into tall sales rows."""
    rows: list[dict] = []
    current_maker = ""

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                cols = _detect_columns(table)
                if cols is None:
                    continue
                m_idx, y_idx = cols  # [N, C, S, T] for month / ytd blocks
                need = max(m_idx[-1], y_idx[-1])
                for raw in table:
                    if not raw or len(raw) <= need:
                        continue
                    cells = [_clean(c) for c in raw]
                    if _is_header(cells):
                        continue

                    raw_maker = cells[C_MAKER]
                    model = cells[C_MODEL]
                    if model.lower() in _SKIP_MODELS:
                        continue
                    # current_maker only tracks *real* makers (must contain a
                    # letter); pure-number / legend rows must not poison it.
                    if raw_maker and any(c.isalpha() for c in raw_maker):
                        current_maker = raw_maker
                    maker = raw_maker or current_maker

                    # Drop non-data rows: empty model, percentage/summary footer
                    # rows, or a maker with no alphabetic characters at all
                    # (e.g. a run of period numbers "2 3 4 5 ... 11").
                    if not model:
                        continue
                    if "%" in model or "percentage" in model.lower():
                        continue
                    if not any(c.isalpha() for c in maker):
                        continue

                    is_subtotal = model.lower().startswith("sub-total") or model.lower() == "total"
                    m_total = to_int(cells[m_idx[3]])
                    y_total = to_int(cells[y_idx[3]])
                    parts = {
                        "North": (to_int(cells[m_idx[0]]), to_int(cells[y_idx[0]])),
                        "Central": (to_int(cells[m_idx[1]]), to_int(cells[y_idx[1]])),
                        "South": (to_int(cells[m_idx[2]]), to_int(cells[y_idx[2]])),
                    }

                    # Gather EVERY numeric value this row would write so a single
                    # cap protects all of them. pdfplumber sometimes merges cells
                    # across columns, dumping a multi-million number into a region
                    # cell while leaving the ALL total empty — that previously
                    # slipped past the m_total/y_total-only cap and got stored.
                    all_vals = [v for v in (m_total, y_total) if v is not None]
                    for mu, yu in parts.values():
                        if mu is not None:
                            all_vals.append(mu)
                        if yu is not None:
                            all_vals.append(yu)

                    # Hard cap: no individual VAMA model/maker cell can exceed the
                    # size of the entire monthly market (~100k). Anything larger is
                    # a parsing artifact — flag it for transparency but never store.
                    if any(v > 100_000 for v in all_vals):
                        db.flag(COUNTRY, year, month, f"{maker}|{model}",
                                "implausible_value",
                                f"m_total={m_total} y_total={y_total} regions={parts}")
                        continue

                    # Rows with no numbers at all carry no information.
                    if not all_vals:
                        continue

                    # Region-sum reconciliation is the definitive artifact check:
                    # a mis-aligned row has regions that don't add to its total.
                    comp_m = [v for v in (parts["North"][0], parts["Central"][0],
                                          parts["South"][0]) if v is not None]
                    if m_total is not None and comp_m:
                        s = sum(comp_m)
                        if abs(m_total - s) > max(20, 0.20 * m_total):
                            db.flag(COUNTRY, year, month, f"{maker}|{model}",
                                    "region_sum_mismatch",
                                    f"month parts={s} total={m_total}")
                            continue
                        if m_total != s:
                            db.flag(COUNTRY, year, month, f"{maker}|{model}",
                                    "region_sum_mismatch",
                                    f"month parts={s} total={m_total}")

                    comp_y = [v for v in (parts["North"][1], parts["Central"][1],
                                          parts["South"][1]) if v is not None]
                    if y_total is not None and comp_y:
                        s = sum(comp_y)
                        if abs(y_total - s) > max(20, 0.20 * y_total):
                            db.flag(COUNTRY, year, month, f"{maker}|{model}",
                                    "region_sum_mismatch",
                                    f"ytd parts={s} total={y_total}")
                            continue
                        if y_total != s:
                            db.flag(COUNTRY, year, month, f"{maker}|{model}",
                                    "region_sum_mismatch",
                                    f"ytd parts={s} total={y_total}")

                    base = {
                        "country": COUNTRY, "year": year, "month": month,
                        "level": "maker" if is_subtotal else "model",
                        "maker": maker, "model": "" if is_subtotal else model,
                        "category": cells[C_CLASS], "seats": cells[C_SEAT],
                        "is_subtotal": int(is_subtotal),
                        "source": SOURCE, "source_url": source_url,
                    }
                    rows.append({**base, "region": "ALL",
                                 "units": m_total, "units_ytd": y_total})
                    for region, (mu, yu) in parts.items():
                        if mu is None and yu is None:
                            continue
                        rows.append({**base, "region": region,
                                     "units": mu, "units_ytd": yu})
    return rows


def months_to_fetch(full: bool = False) -> list[tuple[int, int]]:
    """Months to attempt, newest first. Incremental mode skips stored periods."""
    today = date.today()
    out: list[tuple[int, int]] = []
    y, m = VAMA_START
    while (y, m) <= (today.year, today.month):
        out.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    if not full:
        have = db.existing_periods(COUNTRY, SOURCE)
        # Always re-check the two most recent months (reports get revised).
        recent = set(out[-2:])
        out = [p for p in out if p not in have or p in recent]
    return sorted(out, reverse=True)


def fetch(full: bool = False, limit: int | None = None) -> int:
    total = 0
    if full:
        n = db.clear_source(COUNTRY, SOURCE)
        db.clear_flags()
        print(f"  [vama] cleared {n} stale rows + flags for clean --full re-crawl")
    targets = months_to_fetch(full)
    if limit:
        targets = targets[:limit]
    with db.run_tracker(f"{SOURCE}:sales") as counter:
        for year, month in targets:
            url = find_detail_pdf(year, month)
            if not url:
                print(f"  [vama] {year}-{month:02d} no Detail PDF")
                continue
            dest = RAW_DIR / "vama" / f"vama_{year}_{month:02d}_detail.pdf"
            try:
                path = download(url, dest)
                rows = parse_detail_pdf(path, year, month, url)
            except Exception as exc:  # noqa: BLE001
                print(f"  [vama] {year}-{month:02d} parse failed: {exc}")
                continue
            n = db.upsert_sales(rows)
            total += n
            counter["rows"] = total
            label = MONTH_NAMES_EN[month - 1]
            print(f"  [vama] {year}-{month:02d} ({label}) -> {n} rows")
    return total
