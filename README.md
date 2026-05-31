# Querei — Semantic Video Search for AI Agents

Querei turns a corpus of short-form videos (TikTok / Reels / Shorts style) into
a knowledge base an LLM can **search by meaning** and **reason over** — exposed as
infrastructure (a real [MCP](https://modelcontextprotocol.io) server), not a
dashboard.

The demo is a chat app with **one toggle**:

- **Toggle OFF** → a normal, capable assistant. It can **browse the web** (with a
  live "visiting sites" animation) like any AI — but it has **no access to your
  private social-video corpus** and says so honestly.
- **Toggle ON** → the *same* model is additionally granted live corpus search and
  can find any video by description ("the guy dancing on a car", "a dog that
  bumps its head") and answer business questions grounded in what it retrieves.

The point: the open web is already searchable by AI; short-form video isn't —
until you connect Querei. The toggle gates exactly that one proprietary
capability, nothing else.

> Everything shown is real. The corpus count is the true number of indexed
> videos, results come from an actual vector + keyword search over the corpus,
> and an unrehearsed query typed live will return sensible matches. Nothing is
> hardcoded. The same code path that searches 100 videos searches 100M — only
> cost and coverage change, not capability.

---

## Quick start (3 steps)

You need **[Python](https://www.python.org/downloads/) 3.10–3.12** and
**[Node.js](https://nodejs.org) 18+** installed. Then, in this folder:

```bash
make setup        # 1. install everything + create your .env
```

Open the new **`.env`** file and paste your API key. Querei is provider-agnostic
and ships configured for **OpenAI** (chat + embeddings):

```
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...        # https://platform.openai.com/api-keys
```

Prefer Gemini or Anthropic? Just change `LLM_PROVIDER` / `EMBEDDING_PROVIDER`
and set that provider's key — see "Switching the LLM provider" below.

```bash
make index        # 2. build the search index over the bundled sample corpus
make dev          # 3. start the app  →  open http://localhost:5173
```

That's it. The app opens with a small **sample corpus already searchable**, so
you can verify the whole thing works before adding your own videos.

> No Python/Node yet? On a Mac: `brew install python@3.12 node ffmpeg`.

---

## Try the demo (the "aha" sequence)

1. **Leave the toggle OFF.** Ask: *"Find me a video of a guy dancing on a car."*
   → It explains it has no access to any corpus. (It genuinely doesn't.)
2. **Flip the toggle ON** — it visibly powers on and shows the true corpus count.
3. **Ask the same question again.** → It now finds the video, shows a result
   card, and tells you *why* it matched — phrased in a way it never saw.
4. **Type your own query**, e.g. *"a pet that hurts itself being clumsy"* →
   sensible matches, nothing rehearsed.
5. **Ask a business question:** *"What objections do people raise about
   supplements?"* or *"Find UGC we could repost about skincare."* → it searches,
   then answers grounded in specific videos and cites their ids/creators.

The bundled sample corpus (5 videos in `data/sample/`) is chosen so all of the
above work out of the box.

---

## Load your own videos (e.g. ~10 to test)

The pipeline is: **ingest → analyze each video with Gemini (native video
understanding: transcript + on-screen text + visual description) → embed with
your embedding provider → store in the local Chroma vector DB**. You don't set
up any database — Chroma persists to `data/chroma/` automatically.

**Step 1 — make sure the Gemini key is set** (Gemini reads the video files):
```
# in .env
GEMINI_API_KEY=your_gemini_key      # used ONLY for video analysis
VISUAL_ANALYZER=gemini
```
Your chat/embeddings can stay on OpenAI; only the offline analysis uses Gemini.

**Step 2 — (recommended) install ffmpeg for thumbnails:** `brew install ffmpeg`

**Step 3 — add your videos, two options:**

*Option A — local files:* drop `.mp4/.mov/.webm` files into `data/raw/`.
Optionally add a sidecar `<name>.json` next to each file with any metadata you
know:
```json
{ "creator": "@handle", "caption": "the caption text",
  "hashtags": ["fyp","dogs"], "source_url": "https://..." }
```

*Option B — public URLs:* put one URL per line in a file, downloaded via yt-dlp:
```bash
printf "%s\n%s\n" "https://www.tiktok.com/@x/video/123" "https://..." > myvideos.txt
```

**Step 4 — run the pipeline:**
```bash
make pipeline                 # processes data/raw/
# or:
make pipeline URLS=myvideos.txt
```
This writes `data/descriptions.json` (your corpus), which automatically takes
precedence over the bundled sample, then embeds + indexes it. Re-embed anytime
with `make index`. Restart the app and your videos are searchable.

> **Gemini rate limits:** the free tier caps `gemini-2.5-flash` at ~20
> requests/day. ~10 videos = ~10 analysis calls — fine, but the pipeline will
> auto-wait and retry if it hits a per-minute limit. For larger batches use a
> paid Gemini key, or set `VISUAL_ANALYZER=none` to skip visual analysis and
> index from captions/transcripts only.

> **Legal / ToS:** prefer videos you have rights to or that are publicly posted,
> and keep the corpus small. Querei uses the standard `yt-dlp` downloader only —
> there is deliberately **no** scraping-at-scale or anti-detection machinery;
> that's out of scope and a legal risk.

### Which database?
**ChromaDB**, embedded and local — no server, no account, no config. It persists
to `data/chroma/`. It's a real vector database (same code path would serve
100M vectors); for the demo's scale it's the simplest possible choice. The store
is wrapped behind a small interface (`core/vectorstore.py`) so swapping to
LanceDB / sqlite-vec / a hosted DB later touches one file.

---

## Switching the LLM provider (no code changes)

Edit `.env`:

| Setting | Options | Notes |
|---|---|---|
| `LLM_PROVIDER` | `gemini` · `openai` · `anthropic` | chat + tool-calling |
| `EMBEDDING_PROVIDER` | `gemini` · `openai` | search embeddings (Anthropic has none) |
| `VISUAL_ANALYZER` | `gemini` · `keyframes` · `none` | pipeline video analysis |

Set the matching key (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`), restart, done.
Tool-calling works on whichever provider is selected. If you change
`EMBEDDING_PROVIDER`, re-run `make index` (different models = different vectors).

---

## Use the corpus from Claude Desktop (real MCP)

The search tools are a standalone MCP server, so any MCP client can use them.
Add this to your Claude Desktop config
(`~/Library/Application Support/Claude/claude_desktop_config.json`):

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

Restart Claude Desktop and it gains `search_corpus`, `get_video`, and
`corpus_stats`. The web app's toggle connects to this exact server.

---

## How it works

```
OFFLINE (run once, builds /data):
  ingest ─► analyze (Gemini native video) ─► structured descriptions
         ─► embed (OpenAI/Gemini) ─► vector store (Chroma, local)

ONLINE:
  React chat + toggle ─► FastAPI chat backend (provider-agnostic, streaming)
        │                   │
        │                   ├─ web_search  (ALWAYS on — normal-AI web browsing)
        │                   └─ toggle ON → connects as an MCP client ▼
        │                                 MCP server ─► search service ─► Chroma + BM25
        │                                 (search_corpus / get_video)
```

| Path | What's there |
|---|---|
| `core/` | shared: config, schema, embeddings, vector store, **hybrid search**, provider-agnostic LLM layer (Gemini/OpenAI/Anthropic) |
| `pipeline/` | offline: `ingest` → `analyze` → `build_index` |
| `mcp_server/` | the real MCP server exposing `search_corpus` / `get_video` |
| `server/` | FastAPI chat backend + MCP client; the toggle gates tool access |
| `web/` | React + Vite + Tailwind chat UI |
| `data/` | `sample/` (committed), plus built `descriptions.json`, thumbnails, `chroma/` (git-ignored) |

**Search** is hybrid: semantic vector similarity fused with a BM25 keyword pass
(robust to exact names/hashtags), with an optional one-line LLM "why it matched"
per result. The same `search()` serves both recall and insight queries — the
calling LLM decides how to use the results.

**Cost-aware by design.** The analysis pipeline separates a cheap text layer
(caption, transcript, on-screen text) from the expensive visual layer. At scale
you'd run the cheap layer broadly and gate the visual call selectively; the code
path is identical for 100 or 100M videos — only throughput, index size, and
spend grow. These spots are commented in `pipeline/analyze.py` and
`core/vectorstore.py`.

---

## Troubleshooting

- **"Missing API key for provider '…'"** — paste the key for your selected
  provider into `.env` (e.g. `OPENAI_API_KEY=...`) and restart `make dev`.
- **Gemini "RESOURCE_EXHAUSTED / 429"** — the free tier caps gemini-2.5-flash at
  ~20 requests/day and a low per-minute rate. Wait a minute, switch to
  `LLM_PROVIDER=openai`, or use a paid key.
- **Toggle ON but no results** — run `make index` first; the count in the header
  shows how many vectors are indexed.
- **Thumbnails for your own videos are blank** — install ffmpeg
  (`brew install ffmpeg`), then re-run `make pipeline`. (Sample thumbnails always
  render.)
- **`make setup` can't find Python 3.10–3.12** — install one and re-run; 3.13/3.14
  may not have prebuilt ML packages yet.

---

## What this demo is — and isn't

It proves the **capability** on a small corpus with an architecture that is
deliberately corpus-size-agnostic. The only things between this and the full
vision ("make all of short-form video searchable by agents") are **cost and
coverage**, not capability. Numbers shown are always the true corpus size; no
result, count, or match is ever faked.
