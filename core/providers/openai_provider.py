"""OpenAI provider. Chat + tool-calling + streaming via the openai SDK."""
from __future__ import annotations

import json
from typing import Any, Iterator

from ..config import Settings
from .base import LLMProvider, ToolCall


class OpenAIProvider(LLMProvider):
    def __init__(self, settings: Settings):
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.require_key("openai"))
        self._model = settings.openai_chat_model
        self.name = f"openai::{self._model}"

    def _to_messages(self, messages: list[dict], system: str | None) -> list[dict]:
        out: list[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                msg: dict[str, Any] = {"role": "assistant", "content": m.get("content") or ""}
                if m.get("tool_calls"):
                    msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.args)},
                        }
                        for tc in m["tool_calls"]
                    ]
                    msg["content"] = m.get("content") or None
                out.append(msg)
            elif m["role"] == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": m["tool_call_id"],
                        "content": m["content"],
                    }
                )
        return out

    def _to_tools(self, tools: list[dict] | None):
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]

    def complete_text(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model, messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content or ""

    def stream_turn(self, messages, tools=None, system=None) -> Iterator[dict]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": self._to_messages(messages, system),
            "stream": True,
        }
        oa_tools = self._to_tools(tools)
        if oa_tools:
            kwargs["tools"] = oa_tools

        # Tool-call fragments arrive incrementally across chunks; assemble by index.
        partial: dict[int, dict] = {}
        stream = self._client.chat.completions.create(**kwargs)
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield {"type": "text", "text": delta.content}
            for tc in delta.tool_calls or []:
                slot = partial.setdefault(tc.index, {"id": None, "name": "", "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments

        tool_calls: list[ToolCall] = []
        for slot in partial.values():
            try:
                args = json.loads(slot["args"]) if slot["args"] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=slot["id"] or slot["name"], name=slot["name"], args=args))
        yield {"type": "end", "tool_calls": tool_calls}
