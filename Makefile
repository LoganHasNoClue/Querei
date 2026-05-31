# Aperture — minimal command surface for a non-technical operator.
# Typical flow:   make setup   →   edit .env (add GEMINI_API_KEY)   →   make index   →   make dev

PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: help setup index pipeline server web dev mcp clean

help:
	@echo "Aperture commands:"
	@echo "  make setup     Install everything (Python venv + frontend deps + .env)"
	@echo "  make index     Build the search index over the active corpus (needs GEMINI_API_KEY)"
	@echo "  make dev       Run backend + frontend together (open http://localhost:5173)"
	@echo "  make server    Run only the backend API (http://localhost:8000)"
	@echo "  make web       Run only the frontend dev server"
	@echo "  make mcp       Run the standalone MCP server (for Claude Desktop etc.)"
	@echo "  make pipeline  Ingest + analyze videos in data/raw (or use URLS=file.txt)"
	@echo "  make clean     Remove the built vector index"

setup:
	@bash setup.sh

index:
	$(PY) -m pipeline.build_index --reindex-only

# Full offline pipeline. Optionally:  make pipeline URLS=myvideos.txt
pipeline:
ifdef URLS
	$(PY) -m pipeline.build_index --urls $(URLS)
else
	$(PY) -m pipeline.build_index
endif

server:
	.venv/bin/uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

web:
	cd web && npm run dev

# Run backend + frontend together; Ctrl-C stops both.
dev:
	@echo "Starting Aperture — frontend: http://localhost:5173  (backend: http://localhost:8000)"
	@trap 'kill 0' EXIT INT TERM; \
	.venv/bin/uvicorn server.main:app --host 0.0.0.0 --port 8000 & \
	(cd web && npm run dev) & \
	wait

mcp:
	$(PY) -m mcp_server.server

clean:
	rm -rf data/chroma
	@echo "Removed vector index. Run 'make index' to rebuild."
