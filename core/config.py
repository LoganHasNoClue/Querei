"""Central configuration for Querei.

Everything that distinguishes "demo" from "production" lives here as config:
the corpus location, the LLM/embedding provider, model names, and the vector
store path. There is *no* code path that special-cases a small corpus — 100
videos and 100M videos run the exact same functions; only cost and the values
below change.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = parent of this file's package directory.
ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Provider selection (swappable with zero code changes) ---
    # One of: "gemini", "openai", "anthropic"
    llm_provider: str = "gemini"
    # One of: "gemini", "openai". (Anthropic has no embedding model.)
    embedding_provider: str = "gemini"
    # Visual analyzer for the offline pipeline: "gemini" (native video) or
    # "keyframes" (sample frames -> vision model) or "none" (text-only).
    visual_analyzer: str = "gemini"

    # --- API keys (only the selected provider's key is required to run) ---
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # --- Model names (override in .env to taste) ---
    # NOTE on quota: free-tier Gemini keys vary in which models they can call.
    # gemini-2.5-flash is the broadly-available free model (≈20 requests/day cap
    # on free tier). A paid key removes the cap and unlocks all models. Each
    # toggle-ON query uses ~2 chat calls + 1 embedding, so plan ~10 ON queries/
    # day on free tier. Override here or in .env if your key differs.
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_video_model: str = "gemini-2.5-flash"
    openai_chat_model: str = "gpt-4o"
    openai_embed_model: str = "text-embedding-3-large"
    anthropic_chat_model: str = "claude-sonnet-4-5"

    # --- Paths ---
    data_dir: Path = ROOT / "data"
    corpus_file: Path = ROOT / "data" / "descriptions.json"
    chroma_dir: Path = ROOT / "data" / "chroma"
    thumbs_dir: Path = ROOT / "data" / "thumbs"
    raw_dir: Path = ROOT / "data" / "raw"
    # Committed sample corpus used until the operator drops in their own videos.
    sample_corpus_file: Path = ROOT / "data" / "sample" / "descriptions.json"

    # --- Search behaviour ---
    search_default_k: int = 5
    # Vector vs. keyword fusion weight (0 = pure keyword, 1 = pure vector).
    search_vector_weight: float = 0.7
    # Ask the LLM to write a one-line "why it matched" per result. Costs one
    # extra LLM call per search; off by default to conserve free-tier quota
    # (the chat model already explains matches in its grounded answer). Set to
    # true for richer result cards if you have quota/budget to spare.
    search_synthesize_reasons: bool = False

    # --- Server ---
    cors_origins: str = "*"

    @property
    def active_corpus_file(self) -> Path:
        """Use the operator's corpus if present, else the committed sample."""
        if self.corpus_file.exists():
            return self.corpus_file
        return self.sample_corpus_file

    def require_key(self, provider: str) -> str:
        key = {
            "gemini": self.gemini_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
        }.get(provider, "")
        if not key:
            raise RuntimeError(
                f"Missing API key for provider '{provider}'. "
                f"Set {provider.upper()}_API_KEY in your .env file. "
                f"See .env.example for the exact variable name."
            )
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()
