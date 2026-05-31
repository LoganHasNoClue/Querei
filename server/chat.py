"""Streaming, provider-agnostic tool-calling orchestrator.

Querei is a normal capable assistant: it can always **search the web**
(web_search), just like any general AI. The corpus toggle gates ONE extra,
proprietary capability — semantic search over the private social-video corpus
(search_corpus / get_video). So:
  • Toggle OFF → normal AI: can browse the web, but cannot reach the video
    corpus and says so honestly.
  • Toggle ON  → same AI, now also granted the corpus tools via the live MCP
    server, so it can find any video by meaning.

Emits a stream of JSON events (consumed by the SSE endpoint):
  {"type": "token",       "text": "..."}              streamed reply text
  {"type": "tool_call",   "name": "...", "args": {}}   model invoked a tool
  {"type": "web_sources", "sources": [...]}            sites browsed (animation)
  {"type": "results",     "matches": [...]}            corpus cards to render
  {"type": "done"}
  {"type": "error",       "message": "..."}
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from core.config import get_settings
from core.providers import LLMProvider, get_provider
from core.web_search import web_search
from server.mcp_client import connect_corpus_tools

MAX_TOOL_ROUNDS = 6

# Always-available "normal AI" tool. The corpus tools come from the MCP server
# only when the toggle is on.
WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the public web for up-to-date information and answer general "
        "questions. Returns a list of pages with titles, URLs and snippets. Use "
        "this for anything NOT about the user's private social-video corpus."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The web search query."},
            "k": {"type": "integer", "description": "Max results (default 6)."},
        },
        "required": ["query"],
    },
}


def _format_error(exc: BaseException) -> str:
    """Unwrap ExceptionGroup (anyio/TaskGroup) to a readable, friendly message."""
    group = getattr(exc, "exceptions", None)
    if group:
        return "; ".join(_format_error(e) for e in group)
    text = str(exc)
    if "RESOURCE_EXHAUSTED" in text or "429" in text or "rate limit" in text.lower():
        return (
            "The selected model's rate limit/quota was hit. Wait a minute and try "
            "again, or switch LLM_PROVIDER / use a higher-quota (paid) key in .env."
        )
    if "API key" in text or "PERMISSION_DENIED" in text or "401" in text or "invalid_api_key" in text:
        return "Authentication failed — check your provider's API key in the .env file."
    return f"{type(exc).__name__}: {exc}"

_WEB_CAPABILITY = (
    "You are Querei, a capable, friendly AI assistant. You can answer general "
    "questions and you have a web_search tool to browse the public web for "
    "current information — use it whenever a question benefits from up-to-date or "
    "factual web info, and cite the sources you used. "
)

SYSTEM_WITHOUT_CORPUS = (
    _WEB_CAPABILITY
    + "You do NOT currently have access to the user's private social-video corpus "
    "(TikTok / Instagram Reels / Shorts). If the user asks you to find or analyze a "
    "specific short-form video FROM THAT CORPUS, explain honestly that the corpus "
    "isn't connected — you can search the web but not their video corpus — and "
    "suggest they flip the 'Connect social corpus' toggle. Never invent videos, "
    "creators, or that you searched the corpus. (Web search is fine and encouraged.)"
)

SYSTEM_WITH_CORPUS = (
    _WEB_CAPABILITY
    + "You ALSO have live access to the user's private corpus of short-form videos "
    "via search_corpus(query, k), get_video(id) and corpus_stats(). The corpus is "
    "the user's primary data source and the reason they connected it, so STRONGLY "
    "PREFER search_corpus. Use it for BOTH recall queries ('find the video where a "
    "dog bumps its head') AND insight queries about what people/creators are saying, "
    "talking about, recommending, complaining about — trends, places, products, "
    "opinions, sentiment, UGC. Questions like 'where are people saying is a hidden "
    "gem', 'what do people think about X', 'find UGC about Y' should ALWAYS go to "
    "search_corpus first. Only use web_search when the user explicitly asks to "
    "search the web, or for hard facts/current events that short-form social videos "
    "plainly would not contain. Ground corpus answers in the retrieved results. When "
    "you reference a video, cite it in PLAIN TEXT by its id in parentheses, e.g. "
    "'(vid_001)', adding the creator handle only if one is provided. Do NOT format "
    "corpus videos as markdown links — they have no public URL (the matching video "
    "cards are shown to the user automatically). For corpus size, call corpus_stats "
    "— never guess."
)


async def _run_provider_turn(
    provider: LLMProvider,
    messages: list[dict],
    tools: list[dict] | None,
    system: str,
    emit_token,
) -> list:
    """Run one streaming assistant turn in a worker thread (the provider SDKs are
    blocking), forwarding text deltas to `emit_token`. Returns any tool calls."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    SENTINEL = object()

    def worker():
        try:
            for event in provider.stream_turn(messages, tools=tools, system=system):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as exc:  # surface SDK/auth errors to the stream
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "error", "error": f"{type(exc).__name__}: {exc}"}
            )
        loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)

    loop.run_in_executor(None, worker)

    tool_calls: list = []
    while True:
        event = await queue.get()
        if event is SENTINEL:
            break
        etype = event.get("type")
        if etype == "text":
            await emit_token(event["text"])
        elif etype == "end":
            tool_calls = event["tool_calls"]
        elif etype == "error":
            raise RuntimeError(event["error"])
    return tool_calls


async def stream_chat(messages: list[dict], corpus_enabled: bool) -> AsyncIterator[dict]:
    """Drive a full chat turn (possibly several tool rounds) and yield events."""
    settings = get_settings()
    try:
        provider = get_provider(settings)
    except Exception as exc:
        yield {"type": "error", "message": str(exc)}
        return

    # Local sink so the inner turn-runner can push tokens into this generator.
    out: asyncio.Queue = asyncio.Queue()

    async def emit_token(text: str):
        await out.put({"type": "token", "text": text})

    async def turn(convo, tools, system) -> list | None:
        """Run one provider turn; on error emit a friendly message and signal
        stop (None) so the MCP context unwinds cleanly without an ExceptionGroup."""
        try:
            return await _run_provider_turn(provider, convo, tools, system, emit_token)
        except Exception as exc:
            await out.put({"type": "error", "message": _format_error(exc)})
            return None

    async def execute_tool(name: str, args: dict, toolset) -> str:
        """Dispatch a tool call: web_search runs locally; corpus tools go to the
        live MCP session. Emits the side-channel events the UI animates on."""
        if name == "web_search":
            sources = await asyncio.to_thread(
                web_search, args.get("query", ""), int(args.get("k", 6) or 6)
            )
            # Drive the "browsing the web" animation with the real sites found.
            await out.put({"type": "web_sources", "sources": sources})
            return json.dumps(sources, ensure_ascii=False)
        if toolset is not None:
            result = await toolset.call(name, args)
            # Forward structured corpus matches so the UI can render result cards.
            if name == "search_corpus":
                try:
                    matches = json.loads(result)
                    if isinstance(matches, list):
                        await out.put({"type": "results", "matches": matches})
                except json.JSONDecodeError:
                    pass
            return result
        return json.dumps({"error": f"Tool '{name}' is not available."})

    async def drive(toolset):
        # web_search is always offered; corpus tools only when connected.
        tools = [WEB_SEARCH_TOOL] + (toolset.tools if toolset else [])
        system = SYSTEM_WITH_CORPUS if toolset else SYSTEM_WITHOUT_CORPUS
        convo = list(messages)
        for _ in range(MAX_TOOL_ROUNDS):
            tool_calls = await turn(convo, tools, system)
            if not tool_calls:
                return
            # Record the assistant's tool-call turn, then execute each call.
            convo.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
            for tc in tool_calls:
                await out.put({"type": "tool_call", "name": tc.name, "args": tc.args})
                result = await execute_tool(tc.name, tc.args, toolset)
                convo.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": result,
                    }
                )
        # Hit the round cap — let the model produce a final answer with no tools.
        await turn(convo, [WEB_SEARCH_TOOL], system)

    async def runner():
        try:
            if corpus_enabled:
                async with connect_corpus_tools() as toolset:
                    await drive(toolset)
            else:
                await drive(None)
        except Exception as exc:
            import traceback

            traceback.print_exc()
            await out.put({"type": "error", "message": _format_error(exc)})
        finally:
            await out.put({"type": "done"})

    task = asyncio.create_task(runner())
    while True:
        event = await out.get()
        yield event
        if event["type"] == "done":
            break
    await task
