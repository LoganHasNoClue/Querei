# Single-image deploy: builds the React frontend, then runs the FastAPI backend
# which serves both the API and the built UI on one port. Your corpus (the data/
# folder, minus raw videos) is baked in at build time. API keys are NOT baked in
# — provide them as environment variables on the host.

# --- Stage 1: build the frontend ---
FROM node:20-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Stage 2: backend runtime ---
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY server/ ./server/
COPY mcp_server/ ./mcp_server/
COPY pipeline/ ./pipeline/
# Built corpus: descriptions.json, thumbnails, chroma index, sample corpus.
# (data/raw is excluded via .dockerignore — source videos aren't needed at runtime.)
COPY data/ ./data/
COPY --from=web /web/dist ./web/dist

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
