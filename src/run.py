"""CLI entry point.

    python -m src.run fetch            # incremental refresh of every source
    python -m src.run fetch --full     # re-crawl all history
    python -m src.run fetch --only vama
    python -m src.run export
    python -m src.run stats
"""
from __future__ import annotations

import argparse
import sys

from . import db
from .export import export_all
from .sources import vama_vn, fti_th, news_rss, kaidee_th

SOURCES = {
    "vama": vama_vn,
    "fti": fti_th,
    "kaidee": kaidee_th,
    "news": news_rss,
}


def cmd_fetch(args) -> int:
    db.init_db()
    names = [args.only] if args.only else list(SOURCES)
    grand = 0
    for name in names:
        mod = SOURCES.get(name)
        if not mod:
            print(f"unknown source: {name}", file=sys.stderr)
            return 2
        print(f"[{name}] fetching...")
        try:
            n = mod.fetch(full=args.full, limit=args.limit)
            print(f"[{name}] {n} rows\n")
            grand += n
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] FAILED: {type(exc).__name__}: {exc}\n", file=sys.stderr)
    print(f"total rows written: {grand}")
    return 0


def cmd_export(_args) -> int:
    db.init_db()
    counts = export_all()
    for name, n in counts.items():
        print(f"  {name:22s} {n:>7,} rows")
    return 0


def cmd_stats(_args) -> int:
    db.init_db()
    with db.connect() as conn:
        print("=== sales coverage ===")
        for r in conn.execute("""
            SELECT country, source, level, COUNT(*) rows,
                   COUNT(DISTINCT year*100+month) months,
                   MIN(year*100+month) first, MAX(year*100+month) last
            FROM sales_monthly GROUP BY country, source, level
            ORDER BY country, source, level
        """):
            print(f"  {r['country']} {r['source']:6s} {r['level']:10s} "
                  f"{r['rows']:>6} rows  {r['months']:>3} months  "
                  f"{r['first']}..{r['last']}")

        print("\n=== news ===")
        for r in conn.execute("""
            SELECT country, source, COUNT(*) n FROM news_articles
            GROUP BY country, source ORDER BY country, source
        """):
            print(f"  {r['country']} {r['source']:20s} {r['n']:>5} items")

        q = conn.execute("SELECT COUNT(*) n FROM data_quality_flags").fetchone()
        print(f"\ndata-quality flags: {q['n']}")

        print("\n=== Thailand marketplace listings ===")
        for r in conn.execute("""
            SELECT COUNT(*) n, COUNT(DISTINCT maker) makers,
                   COUNT(DISTINCT province) prov, MIN(year) y0, MAX(year) y1
            FROM th_car_listings
        """):
            print(f"  th_car_listings: {r['n']:>7,} rows | "
                  f"{r['makers']} makers | {r['prov']} provinces | "
                  f"years {r['y0']}..{r['y1']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="sea-auto-market-data")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="crawl sources into SQLite")
    f.add_argument("--full", action="store_true", help="re-crawl all history")
    f.add_argument("--only", choices=list(SOURCES), help="run a single source")
    f.add_argument("--limit", type=int, help="cap items (debug)")
    f.set_defaults(func=cmd_fetch)

    e = sub.add_parser("export", help="write CSV/JSON artifacts")
    e.set_defaults(func=cmd_export)

    s = sub.add_parser("stats", help="print coverage summary")
    s.set_defaults(func=cmd_stats)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
