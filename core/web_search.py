"""Web search — the assistant's "normal AI" capability.

This is intentionally separate from the video corpus: web search is always
available (it's what any general assistant can do), whereas the social-video
corpus is gated behind the toggle. Uses DuckDuckGo (free, no API key).
"""
from __future__ import annotations

from urllib.parse import urlparse


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return url


def web_search(query: str, k: int = 6) -> list[dict]:
    """Return up to k web results as [{title, url, domain, snippet}].

    Best-effort: returns [] on any failure so the assistant can degrade to a
    plain answer with a note rather than crashing.
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
            }
        )
    return results
