"""Gemini provider (default). Chat + tool-calling + streaming via google-genai."""
from __future__ import annotations

import uuid
from typing import Any, Iterator

from ..config import Settings
from .base import LLMProvider, ToolCall


class GeminiProvider(LLMProvider):
    def __init__(self, settings: Settings):
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=settings.require_key("gemini"))
        self._model = settings.gemini_chat_model
        self.name = f"gemini::{self._model}"

    # --- translation helpers ----------------------------------------------
    def _to_contents(self, messages: list[dict]) -> list[Any]:
        from google.genai import types

        contents: list[Any] = []
        for m in messages:
            role = m["role"]
            if role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=m["content"])]))
            elif role == "assistant":
                parts: list[Any] = []
                if m.get("content"):
                    parts.append(types.Part(text=m["content"]))
                for tc in m.get("tool_calls", []):
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(name=tc.name, args=tc.args)
                        )
                    )
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif role == "tool":
                # Gemini carries tool results as a function_response in a user turn.
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=m["name"],
                                    response={"result": m["content"]},
                                )
                            )
                        ],
                    )
                )
        return contents

    def _to_tools(self, tools: list[dict] | None):
        from google.genai import types

        if not tools:
            return None
        decls = [
            types.FunctionDeclaration(
                name=t["name"], description=t["description"], parameters=t["parameters"]
            )
            for t in tools
        ]
        return [types.Tool(function_declarations=decls)]

    # --- interface ---------------------------------------------------------
    def complete_text(self, prompt: str) -> str:
        resp = self._client.models.generate_content(model=self._model, contents=prompt)
        return resp.text or ""

    def stream_turn(self, messages, tools=None, system=None) -> Iterator[dict]:
        from google.genai import types

        config = types.GenerateContentConfig(
            tools=self._to_tools(tools),
            system_instruction=system,
        )
        tool_calls: list[ToolCall] = []
        stream = self._client.models.generate_content_stream(
            model=self._model,
            contents=self._to_contents(messages),
            config=config,
        )
        for chunk in stream:
            for cand in chunk.candidates or []:
                if not cand.content or not cand.content.parts:
                    continue
                for part in cand.content.parts:
                    if getattr(part, "text", None):
                        yield {"type": "text", "text": part.text}
                    fc = getattr(part, "function_call", None)
                    if fc:
                        tool_calls.append(
                            ToolCall(
                                id=str(uuid.uuid4()),
                                name=fc.name,
                                args=dict(fc.args or {}),
                            )
                        )
        yield {"type": "end", "tool_calls": tool_calls}
