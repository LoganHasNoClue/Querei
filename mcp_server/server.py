"""Querei MCP server — the toggle's backend.

Exposes the search service as two Model Context Protocol tools:

  • search_corpus(query, k) -> ranked matches, each with a one-line reason
  • get_video(id)          -> the full structured record for one video

This is a *real* MCP server. Run it standalone over stdio and any MCP client
(Claude Desktop, the Querei chat backend, etc.) can connect and the model
literally gains these tools. The web demo's "Connect social corpus" toggle works
by connecting to / disconnecting from exactly this server.

Run directly:   python -m mcp_server.server
Claude Desktop: see README "Use the corpus from Claude Desktop".
"""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from core.search import get_index

mcp = FastMCP("querei")


@mcp.tool()
def search_corpus(query: str, k: int = 5) -> str:
    """Search the short-form video corpus by natural-language meaning.

    Use this for BOTH:
      • Recall — finding a specific video ("the guy dancing on a car").
      • Insight — gathering evidence for business questions ("what objections
        do people raise about supplements?", "find UGC we could repost",
        "show negative reactions to this product").

    Args:
        query: A natural-language description of what to find.
        k: Max number of results to return (default 5).

    Returns:
        JSON array of matches, each with id, score, creator, caption, a short
        description, thumbnail_path, source_url, and a one-line `reason` it
        matched. Returns [] if the corpus is empty.
    """
    matches = get_index().search(query, k=k)
    return json.dumps([m.model_dump() for m in matches], ensure_ascii=False)


@mcp.tool()
def get_video(id: str) -> str:
    """Fetch the full structured record for one video by its id.

    Args:
        id: The video id (e.g. "vid_001"), as returned by search_corpus.

    Returns:
        JSON object with every field (transcript, on_screen_text,
        visual_description, objects, actions, setting, vibe, entities, ...),
        or a JSON error object if the id is unknown.
    """
    rec = get_index().get_video(id)
    if rec is None:
        return json.dumps({"error": f"No video with id '{id}'"})
    return json.dumps(rec.model_dump(), ensure_ascii=False)


@mcp.tool()
def corpus_stats() -> str:
    """Return the TRUE size and source of the indexed corpus. Never fabricated."""
    index = get_index()
    return json.dumps({"count": index.count(), "source": index.corpus_source})


if __name__ == "__main__":
    mcp.run()
