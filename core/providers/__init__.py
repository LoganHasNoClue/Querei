"""Provider registry. `get_provider()` returns the one selected by LLM_PROVIDER."""
from __future__ import annotations

from ..config import Settings, get_settings
from .base import LLMProvider, ToolCall

__all__ = ["LLMProvider", "ToolCall", "get_provider"]

# Manual cache keyed by provider name (Settings isn't hashable, so we can't use
# lru_cache on the argument). Built once per provider per process.
_provider_cache: dict[str, LLMProvider] = {}


def get_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    provider = settings.llm_provider.lower()
    if provider in _provider_cache:
        return _provider_cache[provider]
    instance = _build_provider(provider, settings)
    _provider_cache[provider] = instance
    return instance


def _build_provider(provider: str, settings: Settings) -> LLMProvider:
    if provider == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(settings)
    if provider == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(settings)
    if provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)
    raise RuntimeError(
        f"Unknown LLM_PROVIDER '{provider}'. Use 'gemini', 'openai', or 'anthropic'."
    )
