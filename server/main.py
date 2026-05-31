"""Querei FastAPI app: chat (SSE), truthful corpus stats, static thumbnails."""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from core.config import ROOT, get_settings
from core.search import get_index
from server.chat import stream_chat

settings = get_settings()
app = FastAPI(title="Querei", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve raw assets (thumbnails) referenced by `thumbnail_path`, e.g.
# data/sample/thumbs/vid_001.svg -> GET /files/data/sample/thumbs/vid_001.svg
app.mount("/files", StaticFiles(directory=str(ROOT)), name="files")


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    corpus_enabled: bool = False


@app.get("/api/health")
def health():
    return {"ok": True, "provider": settings.llm_provider}


@app.get("/api/corpus/stats")
def corpus_stats():
    """The TRUE corpus size + source. Whatever the UI shows comes from here."""
    index = get_index()
    return {
        "count": index.count(),
        "source": index.corpus_source,
        "indexed_vectors": index.store.count(),
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    async def event_source():
        async for event in stream_chat(messages, req.corpus_enabled):
            yield {"data": json.dumps(event, ensure_ascii=False)}

    return EventSourceResponse(event_source())
