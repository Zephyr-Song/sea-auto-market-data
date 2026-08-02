"""Export the SQLite warehouse to Git-friendly CSV/JSON artifacts.

Everything is written with a deterministic ORDER BY so that a re-run with
unchanged data produces a byte-identical file — otherwise the monthly GitHub
Action would churn a diff on every run.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from .config import CSV_DIR, JSON_DIR, DATA_DIR, SOURCES, NEWS_FEEDS
from .db import connect

EXPORTS: dict[str, str] = {
    "sales_monthly": """
        SELECT country, year, month, level, maker, model, category, seats,
               region, units, units_ytd, yoy_pct, is_subtotal, source, source_url,
               source_name, source_site
        FROM sales_monthly
        ORDER BY country, year DESC, month DESC, level, maker, model, region
    """,
    "sales_vn_model": """
        SELECT year, month, maker, model, category AS vama_class, seats, units, units_ytd
        FROM sales_monthly
        WHERE country='VN' AND level='model' AND region='ALL' AND is_subtotal=0
        ORDER BY year DESC, month DESC, units DESC
    """,
    "sales_vn_maker": """
        SELECT year, month, maker, units, units_ytd
        FROM sales_monthly
        WHERE country='VN' AND level='maker' AND region='ALL'
        ORDER BY year DESC, month DESC, units DESC
    """,
    "sales_th_monthly": """
        SELECT year, month, level, category, units, yoy_pct
        FROM sales_monthly
        WHERE country='TH'
        ORDER BY year DESC, month DESC, level, category
    """,
    "news_articles": """
        SELECT country, source, lang, published_at, title, url, source_site, categories
        FROM news_articles
        ORDER BY published_at DESC, source
    """,
    "data_quality_flags": """
        SELECT country, year, month, entity, issue, detail
        FROM data_quality_flags
        ORDER BY country, year DESC, month DESC, entity
    """,
}


def _rows(sql: str):
    with connect() as conn:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description]
        return cols, [dict(zip(cols, r)) for r in cur.fetchall()]


def export_all() -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, sql in EXPORTS.items():
        cols, rows = _rows(sql)
        counts[name] = len(rows)

        with open(CSV_DIR / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)

        with open(JSON_DIR / f"{name}.json", "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)

    _write_manifest(counts)
    return counts


def _write_manifest(counts: dict[str, int]) -> None:
    with connect() as conn:
        cov = conn.execute("""
            SELECT country, source, MIN(year*100+month) AS first_period,
                   MAX(year*100+month) AS last_period,
                   COUNT(DISTINCT year*100+month) AS months,
                   COUNT(*) AS rows
            FROM sales_monthly GROUP BY country, source
        """).fetchall()
        news = conn.execute("""
            SELECT country, source, COUNT(*) AS items,
                   MIN(published_at) AS oldest, MAX(published_at) AS newest
            FROM news_articles GROUP BY country, source
        """).fetchall()
        runs = conn.execute("""
            SELECT source, status, started_at, rows_in, message
            FROM fetch_runs ORDER BY id DESC LIMIT 12
        """).fetchall()

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "export_row_counts": counts,
        "sources": {
            "sales": {
                code: {"name": s["name"], "site": s["site"], "url": s["url"],
                       "country": s["country"], "note": s["note"]}
                for code, s in SOURCES.items()
            },
            "news": {
                f["source"]: {"name": f["name"], "site": f["site"], "url": f["url"],
                              "country": f["country"]}
                for f in NEWS_FEEDS
            },
        },
        "sales_coverage": [dict(r) for r in cov],
        "news_coverage": [dict(r) for r in news],
        "recent_runs": [dict(r) for r in runs],
    }
    with open(DATA_DIR / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
