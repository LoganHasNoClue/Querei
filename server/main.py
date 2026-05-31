"""Querei FastAPI app: chat (SSE), truthful corpus stats, static thumbnails."""
from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# Endpoints reachable without the password (so the UI can show the gate).
_OPEN_PATHS = {"/api/health", "/api/config"}


@app.middleware("http")
async def password_gate(request: Request, call_next):
    """If APP_PASSWORD is set, every /api call must carry it in X-Querei-Auth.
    Protects API spend on a public deploy. No password set = open (local dev)."""
    pw = settings.app_password
    path = request.url.path
    if pw and path.startswith("/api") and path not in _OPEN_PATHS:
        if request.headers.get("x-querei-auth") != pw:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.on_event("startup")
def _ensure_index():
    """Build the vector index on first boot if the corpus is present but not yet
    embedded (e.g. fresh container with no persisted Chroma disk)."""
    try:
        index = get_index()
        if index.count() > 0 and index.store.count() == 0:
            print(f"Warming up index for {index.count()} videos…")
            index.reindex()
    except Exception as exc:  # never block startup
        print(f"Index warmup skipped: {exc}")

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


@app.get("/api/config")
def config():
    """Public: tells the UI whether to show the password gate."""
    return {"auth_required": bool(settings.app_password)}


@app.get("/api/auth")
def auth():
    """Gated by the middleware — a 200 here means the password was correct."""
    return {"ok": True}


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


# In production (single-service deploy) the backend also serves the built React
# app, so the whole thing lives on one origin/domain. In local dev this folder
# doesn't exist and Vite serves the UI instead (proxying /api here). Mounted last
# so it never shadows the /api routes above.
_DIST = ROOT / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
