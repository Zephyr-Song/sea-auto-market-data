"""Shared HTTP + parsing helpers for all source adapters."""
from __future__ import annotations

import re
import time
from pathlib import Path

import requests

from ..config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "th,vi,en;q=0.8",
        })
        _session = s
    return _session


def get(url: str, *, binary: bool = False, retries: int = 3, **kwargs):
    """GET with retry/backoff. Returns ``requests.Response`` or raises."""
    last = None
    for attempt in range(retries):
        try:
            resp = session().get(url, timeout=REQUEST_TIMEOUT, **kwargs)
            if resp.status_code == 200:
                time.sleep(REQUEST_DELAY)
                return resp
            last = RuntimeError(f"HTTP {resp.status_code} for {url}")
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(1.5 * (attempt + 1))
    raise last if last else RuntimeError(f"failed: {url}")


def download(url: str, dest: Path) -> Path:
    """Download to ``dest``, reusing the cached file when it already exists."""
    if dest.exists() and dest.stat().st_size > 1024:
        return dest
    resp = get(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(html_text: str) -> str:
    """Flatten HTML to whitespace-normalised text, keeping token order intact."""
    import html as _html

    cleaned = re.sub(r"<(script|style|noscript).*?</\1>", " ", html_text, flags=re.S | re.I)
    text = _TAG_RE.sub(" ", cleaned)
    return _WS_RE.sub(" ", _html.unescape(text)).strip()


_NUM_CLEAN_RE = re.compile(r"[^\d\-]")


def to_int(raw) -> int | None:
    """Parse an integer out of a messy PDF/HTML cell.

    pdfplumber frequently splits digit groups with stray spaces (``"1 ,254"``,
    ``"3 60"``), so all non-digit characters are dropped before conversion.
    Placeholder cells such as ``'-'`` or ``''`` map to ``None``.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in {"-", "–", "—", "n/a", "N/A"}:
        return None
    s = _NUM_CLEAN_RE.sub("", s)
    if not s or s == "-":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def to_float(raw) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "").replace("%", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None
