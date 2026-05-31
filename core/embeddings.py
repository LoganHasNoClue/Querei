"""Swappable embedding layer.

The rest of the system only knows `get_embedder().embed(texts) -> list[vector]`.
Swap the provider in .env (EMBEDDING_PROVIDER) with no code changes elsewhere.

At scale, embedding ~100M `searchable_text` blobs is a real cost line and would
be batched + cached aggressively; the interface here is identical regardless.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache

from .config import Settings, get_settings


class Embedder(ABC):
    #: Dimensionality of the produced vectors (used to name the Chroma collection
    #: so switching providers can't silently mix incompatible vectors).
    name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class GeminiEmbedder(Embedder):
    def __init__(self, settings: Settings):
        from google import genai

        self._client = genai.Client(api_key=settings.require_key("gemini"))
        self._model = settings.gemini_embed_model
        self.name = f"gemini::{self._model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # The google-genai SDK accepts a list of contents and returns one
        # embedding per item.
        resp = self._client.models.embed_content(model=self._model, contents=texts)
        return [list(e.values) for e in resp.embeddings]


class OpenAIEmbedder(Embedder):
    def __init__(self, settings: Settings):
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.require_key("openai"))
        self._model = settings.openai_embed_model
        self.name = f"openai::{self._model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]


def embedder_identity(settings: Settings) -> str:
    """The embedder's name WITHOUT building a client (needs no API key).

    Used to name the vector collection so the app can boot / report the corpus
    size before a key is present, while still guaranteeing that switching
    embedding providers can never silently mix incompatible vectors.
    """
    provider = settings.embedding_provider.lower()
    if provider == "gemini":
        return f"gemini::{settings.gemini_embed_model}"
    if provider == "openai":
        return f"openai::{settings.openai_embed_model}"
    return f"unknown::{provider}"


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "gemini":
        return GeminiEmbedder(settings)
    if provider == "openai":
        return OpenAIEmbedder(settings)
    raise RuntimeError(
        f"Unknown EMBEDDING_PROVIDER '{provider}'. Use 'gemini' or 'openai'. "
        f"(Anthropic does not offer an embedding model.)"
    )
