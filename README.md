# Querei — Semantic Search for Social Video

**Querei makes the world's short-form video searchable by AI agents.**

The open web is searchable; short-form video (TikTok, Reels, Shorts) — the
fastest-growing content on earth — is not. You can't grep a TikTok. Querei turns
that firehose into a knowledge base an AI agent can **search by meaning** and
**reason over**, delivered as infrastructure: an API and a real
[MCP](https://modelcontextprotocol.io) server, not another dashboard.

Ask it like you'd ask a person who has watched everything:

- **Recall** — *"find the clip of the guy dancing on a car"*, *"the dog that bumps its head"*
- **Insight** — *"where are people saying is a cheap, hidden-gem place to buy property in Italy?"*, *"what objections do people raise about this product?"*, *"find UGC we could repost"*

Answers are grounded in real videos and cite the exact clips.

---

## The toggle

The whole idea in one switch:

- **OFF** — a normal, capable AI. It can browse the web, but it's blind to social
  video and says so.
- **ON** — the *same* model is granted live search over the social-video corpus
  and instantly finds any clip by description and answers business questions,
  citing specific videos.

Same model, **blind → all-seeing**, the instant it connects to Querei.

---

## How it works

```
INGEST ─► ANALYZE ─► EMBED ─► INDEX ─► SERVE
 social    cheap text layer (caption, transcript, on-screen OCR)
 video   + visual layer (a model natively watches each video:
           scene, objects, actions, vibe, named entities)
         → one structured, searchable record per video
         → vectors in a vector DB + hybrid (semantic + keyword) search
         → exposed as MCP tools an AI agent can call mid-conversation
```

| Layer | What it does |
|---|---|
| **Analysis** | Tiered: a cheap text layer over everything + an expensive visual layer that *watches* each video. Fused into a rich, queryable record. |
| **Search** | Hybrid semantic (vector) + keyword search over a local vector store; returns ranked matches with relevance. |
| **MCP server** | Exposes `search_corpus` / `get_video` as standard tools — any agent (e.g. Claude Desktop) can use Querei live. |
| **Chat backend** | Provider-agnostic (OpenAI · Anthropic · Gemini, swappable via config) with a streaming tool-calling loop. |
| **Frontend** | Fast, dark, single-column chat with the corpus toggle, a web-browsing animation, and rich result cards. |

**Corpus-size-agnostic by design.** The exact code path that searches a starter
corpus searches the entire firehose — only cost and coverage grow, never the
capability. That's the whole bet: the architecture is the product.

---

## Run it locally

Requires **Python 3.10–3.12** and **Node 18+**.

```bash
git clone https://github.com/LoganHasNoClue/Querei.git && cd Querei
make setup            # install backend + frontend, create .env
```

Add your API key to `.env` (ships configured for OpenAI):

```
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

```bash
make index            # build the search index over the corpus
make dev              # → http://localhost:5173
```

Flip the toggle on and ask away.

---

## Swap the AI provider (no code changes)

Edit `.env` — `LLM_PROVIDER` and `EMBEDDING_PROVIDER` accept `openai`, `gemini`,
or `anthropic` (set that provider's key). Tool-calling works on whichever is
selected.

## Use it from Claude Desktop (real MCP)

The search tools are a standalone MCP server, so any MCP client can call them.
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "querei": {
      "command": "/ABSOLUTE/PATH/TO/Querei/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/ABSOLUTE/PATH/TO/Querei"
    }
  }
}
```

## Deploy

A `Dockerfile` and `render.yaml` ship a single-image deploy (the backend serves
the API and the built UI on one origin). Set `OPENAI_API_KEY`, `GEMINI_API_KEY`,
and an optional `APP_PASSWORD` (shared-password gate) as environment variables on
the host.

---

*Querei · semantic video search for AI agents · provider-agnostic · MCP-native*
