# Querei — Make all of social video searchable by AI

### The problem
Short-form video (TikTok, Reels, Shorts) is the fastest-growing and **least-searchable** content on earth. You can't grep a TikTok. Modern AI agents can read and search the open web, but they are **blind to the firehose of social video** — exactly where today's culture, opinions, product reviews, and buying signals actually live. There is no "search what people are *showing and saying*" layer for short-form video.

### The solution
**Querei turns any corpus of short-form videos into a knowledge base an AI agent can search by meaning and reason over** — delivered as infrastructure (an API / MCP server), not another dashboard. Once connected, an LLM can instantly answer:
- **Recall:** *"find the clip where a dog bumps its head"*
- **Insight:** *"where are people saying is a cheap, hidden-gem place to buy property in Italy?"* → grounded in real videos, citing the specific clips.

### The product — one toggle
A single switch makes the value visceral:
- **OFF:** a normal, capable AI — it can browse the web, but it is blind to social video and honestly says so.
- **ON:** the *same* model is granted live search over the social-video corpus and instantly finds any clip by description and answers business questions, citing specific videos.

Same model, **blind → all-seeing**, the instant it connects to Querei.

### How it works
1. **Ingest** — pull short-form videos from across social platforms.
2. **Analyze (cost-aware, tiered)** — a *cheap text layer* (caption, transcript, on-screen text/OCR) plus an *expensive visual layer* that **natively watches each video** (scene, objects, actions, vibe, named entities). Both are fused into one structured, searchable record.
3. **Embed + index** — each record is embedded into a vector database; search is **hybrid** (semantic vectors + keyword) for robustness.
4. **Serve** — a **real MCP server** exposes `search_corpus` / `get_video`; a **provider-agnostic** chat backend (OpenAI · Anthropic · Gemini, swappable) hands the model those tools the moment the corpus is connected.

### Why it's credible
- **Real results.** Nothing is hardcoded; results come from live semantic search over the corpus and survive arbitrary, unrehearsed queries typed on the spot.
- **Corpus-size-agnostic — the architecture is the product.** The exact code path that searches a starter corpus searches the entire social-video firehose. The only things between today and full coverage are **cost and infrastructure — not capability.**
- **Standards-based.** Because it's exposed over the **Model Context Protocol**, any AI agent can use Querei as a live tool today.

### The business
The open web is already searchable by AI; **social video isn't.** Querei is the search/data layer for it — sold as an **API/MCP endpoint**: brands mine UGC to repost and surface objections/negative reactions, agencies detect trends, and AI agents finally get eyes on the world's largest unsearchable content type.

---
*Querei · semantic video search for AI agents · provider-agnostic · runs locally · MCP-native*
