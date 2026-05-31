"""Querei shared core: config, schema, embeddings, vector store, search,
and the provider-agnostic LLM layer. Imported by the pipeline, the server, and
the MCP server so all three run the exact same code path."""
import logging as _logging

# Keep the console readable: the SDK/HTTP clients log every request at INFO.
for _noisy in ("google_genai", "google.genai", "httpx", "httpcore", "chromadb.telemetry"):
    _logging.getLogger(_noisy).setLevel(_logging.WARNING)
