"""SQLite storage layer.

Design notes
------------
* Every dimension column that participates in the natural key is NOT NULL with a
  '' default, so a plain UNIQUE constraint gives us idempotent upserts without
  needing expression indexes.
* ``sales_monthly`` is deliberately a tall/narrow fact table: one row per
  (country, period, level, maker, model, category, region, source). That keeps
  Thailand's powertrain-level figures and Vietnam's model-level figures in one
  place without forcing a lowest-common-denominator schema.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Mapping, Any

from .config import DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sales_monthly (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    country      TEXT    NOT NULL,               -- TH | VN
    year         INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    level        TEXT    NOT NULL,               -- total|powertrain|segment|maker|model
    maker        TEXT    NOT NULL DEFAULT '',
    model        TEXT    NOT NULL DEFAULT '',
    category     TEXT    NOT NULL DEFAULT '',    -- VAMA class / powertrain code / segment
    seats        TEXT    NOT NULL DEFAULT '',
    region       TEXT    NOT NULL DEFAULT 'ALL', -- North|Central|South|ALL
    units        INTEGER,
    units_ytd    INTEGER,
    yoy_pct      REAL,
    is_subtotal  INTEGER NOT NULL DEFAULT 0,
    source       TEXT    NOT NULL,
    source_url   TEXT    NOT NULL DEFAULT '',
    fetched_at   TEXT    NOT NULL,
    UNIQUE(country, year, month, level, maker, model, category, region, source)
);

CREATE INDEX IF NOT EXISTS idx_sales_period  ON sales_monthly(country, year, month);
CREATE INDEX IF NOT EXISTS idx_sales_model   ON sales_monthly(country, maker, model);
CREATE INDEX IF NOT EXISTS idx_sales_level   ON sales_monthly(level);

CREATE TABLE IF NOT EXISTS news_articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    country      TEXT NOT NULL,
    source       TEXT NOT NULL,
    lang         TEXT NOT NULL DEFAULT '',
    title        TEXT NOT NULL,
    url          TEXT NOT NULL UNIQUE,
    published_at TEXT,
    summary      TEXT NOT NULL DEFAULT '',
    categories   TEXT NOT NULL DEFAULT '',
    fetched_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_news_pub ON news_articles(country, published_at DESC);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,                   -- running|ok|error
    rows_in     INTEGER NOT NULL DEFAULT 0,
    message     TEXT NOT NULL DEFAULT ''
);

-- Records rows where region components do not add up to the reported total.
CREATE TABLE IF NOT EXISTS data_quality_flags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    country    TEXT NOT NULL,
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    entity     TEXT NOT NULL,
    issue      TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '',
    flagged_at TEXT NOT NULL,
    UNIQUE(country, year, month, entity, issue)
);
"""

SALES_COLS = (
    "country", "year", "month", "level", "maker", "model", "category", "seats",
    "region", "units", "units_ytd", "yoy_pct", "is_subtotal", "source",
    "source_url", "fetched_at",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def run_tracker(source: str):
    """Context manager that records a row in ``fetch_runs`` for observability."""
    conn = connect()
    cur = conn.execute(
        "INSERT INTO fetch_runs(source, started_at, status) VALUES (?,?,'running')",
        (source, utcnow()),
    )
    run_id = cur.lastrowid
    conn.commit()
    counter = {"rows": 0}
    try:
        yield counter
    except Exception as exc:  # noqa: BLE001 - we re-raise after recording
        conn.execute(
            "UPDATE fetch_runs SET finished_at=?, status='error', rows_in=?, message=? WHERE id=?",
            (utcnow(), counter["rows"], f"{type(exc).__name__}: {exc}"[:500], run_id),
        )
        conn.commit()
        conn.close()
        raise
    else:
        conn.execute(
            "UPDATE fetch_runs SET finished_at=?, status='ok', rows_in=? WHERE id=?",
            (utcnow(), counter["rows"], run_id),
        )
        conn.commit()
        conn.close()


def upsert_sales(rows: Iterable[Mapping[str, Any]]) -> int:
    """Insert or replace sales rows. Returns the number of rows written."""
    rows = list(rows)
    if not rows:
        return 0
    now = utcnow()
    payload = []
    for r in rows:
        rec = {c: r.get(c) for c in SALES_COLS}
        for text_col in ("maker", "model", "category", "seats", "source_url"):
            rec[text_col] = (rec[text_col] or "")
        rec["region"] = rec["region"] or "ALL"
        rec["is_subtotal"] = int(rec["is_subtotal"] or 0)
        rec["fetched_at"] = now
        payload.append(tuple(rec[c] for c in SALES_COLS))

    placeholders = ",".join("?" * len(SALES_COLS))
    sql = (
        f"INSERT INTO sales_monthly ({','.join(SALES_COLS)}) VALUES ({placeholders}) "
        "ON CONFLICT(country, year, month, level, maker, model, category, region, source) "
        "DO UPDATE SET units=excluded.units, units_ytd=excluded.units_ytd, "
        "yoy_pct=excluded.yoy_pct, seats=excluded.seats, "
        "is_subtotal=excluded.is_subtotal, source_url=excluded.source_url, "
        "fetched_at=excluded.fetched_at"
    )
    with connect() as conn:
        conn.executemany(sql, payload)
    return len(payload)


def upsert_news(rows: Iterable[Mapping[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    now = utcnow()
    payload = [
        (
            r["country"], r["source"], r.get("lang", ""), r["title"], r["url"],
            r.get("published_at"), r.get("summary", ""), r.get("categories", ""), now,
        )
        for r in rows
    ]
    sql = (
        "INSERT INTO news_articles(country, source, lang, title, url, published_at, "
        "summary, categories, fetched_at) VALUES (?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(url) DO UPDATE SET title=excluded.title, "
        "summary=excluded.summary, categories=excluded.categories"
    )
    with connect() as conn:
        conn.executemany(sql, payload)
    return len(payload)


def flag(country: str, year: int, month: int, entity: str, issue: str, detail: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO data_quality_flags"
            "(country, year, month, entity, issue, detail, flagged_at) VALUES (?,?,?,?,?,?,?)",
            (country, year, month, entity, issue, detail, utcnow()),
        )


def existing_periods(country: str, source: str) -> set[tuple[int, int]]:
    """Periods already stored, used to skip re-downloading historical months."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT year, month FROM sales_monthly WHERE country=? AND source=?",
            (country, source),
        ).fetchall()
    return {(r["year"], r["month"]) for r in rows}


def clear_source(country: str, source: str) -> int:
    """Delete every sales row for a (country, source). Used by ``--full`` so a
    re-crawl replaces history cleanly instead of leaving stale rows behind that
    the new parser no longer emits."""
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM sales_monthly WHERE country=? AND source=?", (country, source))
        return cur.rowcount


def clear_flags() -> int:
    """Delete all data-quality flags (they are regenerated on each crawl)."""
    with connect() as conn:
        cur = conn.execute("DELETE FROM data_quality_flags")
        return cur.rowcount
