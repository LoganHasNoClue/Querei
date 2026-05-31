"""Provider-agnostic LLM interface.

Every provider (Gemini, OpenAI, Anthropic) implements the same two methods, so
the chat backend and the search reason-synthesizer never know which model is
behind them. Selected by LLM_PROVIDER in .env — no code changes to swap.

Neutral message format (list of dicts), translated per-provider on each call:
  {"role": "user",      "content": "..."}
  {"role": "assistant", "content": "..." | None, "tool_calls": [ToolCall, ...]}
  {"role": "tool",      "tool_call_id": "...", "name": "...", "content": "..."}

Neutral tool format:
  {"name": str, "description": str, "parameters": <JSON Schema object>}

`stream_turn` is a generator yielding streaming events:
  {"type": "text", "text": <delta>}                     # token(s) of the reply
  {"type": "end",  "tool_calls": [ToolCall, ...]}        # always last
If `tool_calls` is non-empty the caller executes them, appends tool results, and
calls `stream_turn` again — a standard tool-calling loop.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete_text(self, prompt: str) -> str:
        """One-shot, non-streaming completion (used for short utility calls)."""

    @abstractmethod
    def stream_turn(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> Iterator[dict]:
        """Stream one assistant turn. See module docstring for event shapes."""
