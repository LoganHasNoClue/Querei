"""MCP client used by the chat backend.

When the corpus toggle is ON, the backend spawns the real Querei MCP server
(`python -m mcp_server.server`) over stdio and talks to it as a genuine MCP
client — the same protocol an external client like Claude Desktop would use. The
model's tools therefore come from the live MCP server, not a local shortcut, so
the toggle literally grants/revokes MCP access. When OFF, no session is opened
and the model is handed no tools at all.
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.config import ROOT


@dataclass
class MCPToolset:
    session: ClientSession
    tools: list[dict]  # neutral tool definitions for the provider layer

    async def call(self, name: str, args: dict) -> str:
        result = await self.session.call_tool(name, args)
        # MCP tool results are a list of content blocks; concatenate text.
        chunks = [c.text for c in result.content if getattr(c, "type", None) == "text"]
        return "\n".join(chunks) if chunks else "(no content)"


@asynccontextmanager
async def connect_corpus_tools():
    """Yield an MCPToolset connected to the live Querei MCP server."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(ROOT),
        env=os.environ.copy(),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema or {"type": "object", "properties": {}},
                }
                for t in listed.tools
            ]
            yield MCPToolset(session=session, tools=tools)
