"""The search service — the single function that powers both the MCP tools and
every "recall" / "insight" query.

`search(query, k)`:
  1. embed the query and pull the vector top-N (semantic meaning),
  2. run a lexical BM25 pass over the same corpus (robustness for names,
     hashtags, exact words the embedding might wash out),
  3. fuse the two scores,
  4. optionally ask the LLM for a one-line reason each match fits.

The *calling* LLM decides whether the results answer a "find that video"
(recall) question or a "what do people say about X" (insight) question — the
service is identical for both. Nothing here is rigged to any query.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from typing import Callable

from rank_bm25 import BM25Okapi

from .config import Settings, get_settings
from .embeddings import Embedder, embedder_identity, get_embedder
from .schema import SearchMatch, VideoRecord
from .vectorstore import VectorStore

_TOKEN_RE = re.compile(r"[a-z0-9#@]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _short_description(rec: VideoRecord, limit: int = 220) -> str:
    text = rec.visual_description or rec.caption or rec.transcript or ""
    text = text.strip().replace("\n", " ")
    return text[: limit - 1] + "…" if len(text) > limit else text


def _safe_collection_name(embedder_name: str) -> str:
    # Chroma collection names must be 3-63 chars, alnum/._- ; encode the embedder
    # identity so switching providers can never mix incompatible vectors.
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", embedder_name)
    return f"corpus_{slug}"[:63]


class CorpusIndex:
    """Holds the loaded corpus + its vector and lexical indexes."""

    def __init__(self, settings: Settings, embedder_factory: Callable[[], Embedder]):
        self.settings = settings
        # The embedder is built lazily: loading the corpus, reporting the true
        # count, and running the keyword pass all work with NO API key. Only
        # vector embedding (indexing, or embedding a query when an index exists)
        # needs the key — so the app boots and degrades gracefully without one.
        self._embedder_factory = embedder_factory
        self._embedder: Optional[Embedder] = None
        self.collection_name = _safe_collection_name(embedder_identity(settings))
        self.store = VectorStore(settings.chroma_dir, self.collection_name)
        self.records: dict[str, VideoRecord] = {}
        self.order: list[str] = []
        self._bm25: Optional[BM25Okapi] = None
        self._load_corpus()
        self._build_bm25()

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = self._embedder_factory()
        return self._embedder

    # --- loading -----------------------------------------------------------
    def _load_corpus(self) -> None:
        path = self.settings.active_corpus_file
        if not path.exists():
            return
        data = json.loads(Path(path).read_text())
        for raw in data:
            rec = VideoRecord(**raw).ensure_searchable_text()
            self.records[rec.id] = rec
            self.order.append(rec.id)

    def _build_bm25(self) -> None:
        if not self.order:
            self._bm25 = None
            return
        corpus_tokens = [_tokenize(self.records[i].searchable_text or "") for i in self.order]
        self._bm25 = BM25Okapi(corpus_tokens)

    @property
    def corpus_source(self) -> str:
        active = self.settings.active_corpus_file
        return "operator" if active == self.settings.corpus_file else "sample"

    def count(self) -> int:
        return len(self.records)

    # --- (re)indexing ------------------------------------------------------
    def reindex(self) -> int:
        """Embed every record and (re)build the vector store. Run offline."""
        self.store.reset()
        if not self.order:
            return 0
        texts = [self.records[i].searchable_text or "" for i in self.order]
        embeddings = self.embedder.embed(texts)
        self.store.add(ids=list(self.order), embeddings=embeddings, documents=texts)
        return len(self.order)

    # --- query -------------------------------------------------------------
    def search(self, query: str, k: Optional[int] = None, synthesize: Optional[bool] = None) -> list[SearchMatch]:
        k = k or self.settings.search_default_k
        if not self.records:
            return []

        vw = self.settings.search_vector_weight

        # 1) Semantic / vector pass — pull a wide candidate set to fuse.
        # If no vectors are indexed yet, or the query can't be embedded (e.g. no
        # API key), we transparently fall back to the keyword pass below.
        vector_scores: dict[str, float] = {}
        if self.store.count() > 0:
            try:
                q_emb = self.embedder.embed_one(query)
                for vid, sim in self.store.query(q_emb, k=max(k * 4, k)):
                    vector_scores[vid] = max(0.0, min(1.0, sim))
            except Exception:
                pass

        # 2) Lexical / keyword pass over the whole corpus.
        keyword_scores: dict[str, float] = {}
        if self._bm25 is not None:
            raw = self._bm25.get_scores(_tokenize(query))
            top = max(raw) if len(raw) else 0.0
            if top > 0:
                for idx, score in enumerate(raw):
                    if score > 0:
                        keyword_scores[self.order[idx]] = score / top

        # 3) Fuse. Either signal alone can surface a candidate.
        candidates = set(vector_scores) | set(keyword_scores)
        fused: list[tuple[str, float]] = []
        for vid in candidates:
            combined = vw * vector_scores.get(vid, 0.0) + (1 - vw) * keyword_scores.get(vid, 0.0)
            fused.append((vid, combined))
        fused.sort(key=lambda x: x[1], reverse=True)
        top_matches = fused[:k]

        matches = [
            SearchMatch(
                id=vid,
                score=round(score, 4),
                creator=self.records[vid].creator,
                caption=self.records[vid].caption,
                description=_short_description(self.records[vid]),
                thumbnail_path=self.records[vid].thumbnail_path,
                source_url=self.records[vid].source_url,
            )
            for vid, score in top_matches
        ]

        # 4) Optional one-line "why it matched" reasons.
        do_synth = self.settings.search_synthesize_reasons if synthesize is None else synthesize
        if do_synth and matches:
            self._add_reasons(query, matches)
        return matches

    def get_video(self, video_id: str) -> Optional[VideoRecord]:
        return self.records.get(video_id)

    # --- reason synthesis (best-effort; never fails a search) --------------
    def _add_reasons(self, query: str, matches: list[SearchMatch]) -> None:
        try:
            from .providers import get_provider  # local import avoids cycle

            provider = get_provider(self.settings)
            payload = [
                {"id": m.id, "creator": m.creator, "description": m.description}
                for m in matches
            ]
            prompt = (
                "A user searched a video corpus. For EACH result, write a single "
                "short sentence explaining why it matches the query. Be concrete and "
                "grounded only in the provided description — do not invent details.\n\n"
                f"Query: {query!r}\n\nResults (JSON): {json.dumps(payload)}\n\n"
                'Respond with ONLY a JSON object mapping each id to its reason string, '
                'e.g. {"vid_001": "..."}.'
            )
            text = provider.complete_text(prompt)
            reasons = json.loads(_extract_json(text))
            for m in matches:
                if m.id in reasons:
                    m.reason = str(reasons[m.id])
        except Exception:
            # Reasons are a nicety; never let them break search.
            pass


def _extract_json(text: str) -> str:
    """Pull the first {...} block out of a possibly fenced LLM reply."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip("`").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


@lru_cache
def get_index() -> CorpusIndex:
    """Process-wide corpus index. Cached so the corpus loads once per process.

    The embedder is passed as a factory (not an instance) so constructing the
    index never requires an API key — see CorpusIndex.__init__."""
    return CorpusIndex(get_settings(), get_embedder)
