"""Local, free, persistent vector store (ChromaDB).

Wrapped behind a tiny interface so the store is swappable (LanceDB, sqlite-vec,
a managed DB at scale) without touching the search service. We pass our own
embeddings in explicitly rather than letting Chroma embed — the embedder is the
single source of truth (see core/embeddings.py).

Corpus-size note: Chroma persists an HNSW index to disk under CHROMA_DIR. The
same add/query calls serve 100 or 100M vectors; at 100M you would shard the
collection and the index would need real RAM/disk, but the code path is this.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

# Disable Chroma's telemetry (and silence a noisy posthog version mismatch) before import.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

import chromadb
from chromadb.config import Settings as ChromaSettings


class VectorStore:
    def __init__(self, persist_dir: Path, collection: str):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection_name = collection
        self._collection = self._client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}
        )

    def reset(self) -> None:
        """Drop and recreate the collection (used on a fresh index build)."""
        try:
            self._client.delete_collection(self._collection_name)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name, metadata={"hnsw:space": "cosine"}
        )

    def add(self, ids: list[str], embeddings: list[list[float]], documents: list[str]) -> None:
        if not ids:
            return
        self._collection.add(ids=ids, embeddings=embeddings, documents=documents)

    def query(self, embedding: list[float], k: int) -> list[tuple[str, float]]:
        """Return [(id, similarity_score)] best-first. Score in [0,1]."""
        count = self.count()
        if count == 0:
            return []
        res = self._collection.query(
            query_embeddings=[embedding], n_results=min(k, count)
        )
        ids = res["ids"][0]
        # Chroma returns cosine *distance*; convert to a 0..1 similarity.
        distances = res["distances"][0]
        return [(i, 1.0 - float(d)) for i, d in zip(ids, distances)]

    def count(self) -> int:
        return self._collection.count()


_store: Optional[VectorStore] = None


def get_store(persist_dir: Path, collection: str) -> VectorStore:
    """Process-wide singleton keyed implicitly by the first caller's config."""
    global _store
    if _store is None:
        _store = VectorStore(persist_dir, collection)
    return _store
