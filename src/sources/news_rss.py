"""New-model / market news feeds for Thailand and Vietnam.

Five RSS feeds are polled (all verified publicly reachable, full-fidelity items):

    TH  headlightmag.com          | autolifethailand.tv
    VN  vnexpress.net (oto-xe-may)| tuoitre.vn (xe) | thanhnien.vn (xe)

Feeds are append-only from the pipeline's point of view: items are keyed on URL,
so re-running never duplicates, and the archive grows month over month even
though each feed only exposes a short rolling window.
"""
from __future__ import annotations

from datetime import datetime, timezone

import feedparser

from ..config import NEWS_FEEDS
from .. import db
from .base import get, strip_html

SOURCE = "rss"


def _published(entry) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        tm = entry.get(key)
        if tm:
            return datetime(*tm[:6], tzinfo=timezone.utc).isoformat(timespec="seconds")
    return entry.get("published") or entry.get("updated")


def fetch(full: bool = False, limit: int | None = None) -> int:
    total = 0
    with db.run_tracker(f"{SOURCE}:news") as counter:
        for feed in NEWS_FEEDS:
            try:
                resp = get(feed["url"])
                parsed = feedparser.parse(resp.content)
            except Exception as exc:  # noqa: BLE001
                print(f"  [rss] {feed['source']} failed: {exc}")
                continue

            rows = []
            for e in parsed.entries:
                url = e.get("link")
                title = strip_html(e.get("title", ""))
                if not url or not title:
                    continue
                cats = ",".join(
                    sorted({strip_html(t.get("term", "")) for t in e.get("tags", []) if t.get("term")})
                )
                rows.append({
                    "country": feed["country"], "source": feed["source"],
                    "lang": feed["lang"], "title": title, "url": url,
                    "published_at": _published(e),
                    "summary": strip_html(e.get("summary", ""))[:800],
                    "categories": cats,
                    "source_site": feed["site"],
                })
            n = db.upsert_news(rows)
            total += n
            counter["rows"] = total
            print(f"  [rss] {feed['country']} {feed['source']} -> {n} items")
    return total
