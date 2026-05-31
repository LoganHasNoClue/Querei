"""Web search — the assistant's "normal AI" capability.

Returns web results AND a text excerpt of the top pages, so the model has real
material to answer with (snippets alone make it just describe the sources).
Separate from the video corpus, which is gated behind the toggle. Uses
DuckDuckGo (free, no API key).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
# How many of the top results to actually open and read.
_FETCH_TOP = 4
_CONTENT_CHARS = 1600


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return url


def _fetch_text(url: str) -> str:
    """Download a page and return cleaned visible text (best-effort, bounded)."""
    try:
        import httpx

        resp = httpx.get(
            url, timeout=4.0, follow_redirects=True, headers={"User-Agent": _UA}
        )
        if resp.status_code != 200 or "html" not in resp.headers.get("content-type", ""):
            return ""
        html = resp.text
    except Exception:
        return ""
    # Drop script/style/nav noise, strip tags, collapse whitespace.
    html = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:_CONTENT_CHARS]


def web_search(query: str, k: int = 6) -> list[dict]:
    """Return up to k web results as [{title, url, domain, snippet, content}].

    `content` is a text excerpt of the page (empty if it couldn't be fetched).
    Best-effort: returns [] on total failure so the assistant degrades gracefully.
    """
    if not query.strip():
        return []
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=k)
    except Exception:
        return []

    results: list[dict] = []
    for r in raw or []:
        url = r.get("href") or r.get("url") or ""
        results.append(
            {
                "title": r.get("title") or _domain(url),
                "url": url,
                "domain": _domain(url),
                "snippet": r.get("body") or r.get("snippet") or "",
                "content": "",
            }
        )

    # Open the top few pages so the model can synthesize a real answer.
    for r in results[:_FETCH_TOP]:
        if r["url"]:
            r["content"] = _fetch_text(r["url"]) or r["snippet"]

    return results
