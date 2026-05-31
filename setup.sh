#!/usr/bin/env bash
# One-shot setup for Aperture. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

echo "▶ Aperture setup"

# --- pick a Python 3.10–3.12 interpreter (3.13/3.14 may lack ML wheels) ---
PYBIN=""
for cand in python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver=$("$cand" -c 'import sys;print("%d.%d"%sys.version_info[:2])')
    case "$ver" in 3.10|3.11|3.12) PYBIN="$cand"; break;; esac
  fi
done
if [ -z "$PYBIN" ]; then
  echo "✗ Need Python 3.10, 3.11, or 3.12. Install one (e.g. 'brew install python@3.12') and re-run." >&2
  exit 1
fi
echo "  • using $PYBIN ($($PYBIN --version))"

# --- Python venv + deps ---
if [ ! -d .venv ]; then
  "$PYBIN" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip -q
echo "  • installing Python dependencies (this can take a minute)…"
.venv/bin/pip install -r requirements.txt -q

# --- frontend deps ---
if command -v npm >/dev/null 2>&1; then
  echo "  • installing frontend dependencies…"
  (cd web && npm install --silent)
else
  echo "  ! npm not found — install Node 18+ to run the web UI (https://nodejs.org)"
fi

# --- .env ---
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  • created .env from template"
fi

# --- optional but recommended: ffmpeg (thumbnails + keyframe analysis) ---
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "  ! ffmpeg not found (optional). For thumbnails from your own videos: 'brew install ffmpeg'"
fi

echo ""
echo "✓ Setup complete. Next:"
echo "  1) Open .env and paste your key after GEMINI_API_KEY="
echo "     (free key: https://aistudio.google.com/apikey)"
echo "  2) make index     # build the search index over the sample corpus"
echo "  3) make dev       # open http://localhost:5173"
