"""Anthropic provider. Chat + tool-calling + streaming via the anthropic SDK.

Note: Anthropic has no embedding model, so EMBEDDING_PROVIDER must be 'gemini'
or 'openai' even when LLM_PROVIDER='anthropic'.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

from ..config import Settings
from .base import LLMProvider, ToolCall


class AnthropicProvider(LLMProvider):
    def __init__(self, settings: Settings):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.require_key("anthropic"))
        self._model = settings.anthropic_chat_model
        self.name = f"anthropic::{self._model}"

    def _to_messages(self, messages: list[dict]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                blocks: list[dict] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls", []):
                    blocks.append(
                        {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.args}
                    )
                out.append({"role": "assistant", "content": blocks})
            elif m["role"] == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m["tool_call_id"],
                                "content": m["content"],
                            }
                        ],
                    }
                )
        return out

    def _to_tools(self, tools: list[dict] | None):
        if not tools:
            return None
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tools
        ]

    def complete_text(self, prompt: str) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    def stream_turn(self, messages, tools=None, system=None) -> Iterator[dict]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 2048,
            "messages": self._to_messages(messages),
        }
        if system:
            kwargs["system"] = system
        an_tools = self._to_tools(tools)
        if an_tools:
            kwargs["tools"] = an_tools

        tool_calls: list[ToolCall] = []
        with self._client.messages.stream(**kwargs) as stream:
            for event in stream:
                if event.type == "text":
                    yield {"type": "text", "text": event.text}
            final = stream.get_final_message()
            for block in final.content:
                if block.type == "tool_use":
                    tool_calls.append(
                        ToolCall(id=block.id, name=block.name, args=dict(block.input or {}))
                    )
        yield {"type": "end", "tool_calls": tool_calls}
