#!/usr/bin/env bash
# AgentOps 2.0 — start the backend (macOS/Linux)
# The FastAPI "app" package lives in backend/, so uvicorn must run with that as app dir.
set -e
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/backend" && pwd)"
PYTHON="$BACKEND_DIR/.venv/bin/python"
if [ ! -f "$PYTHON" ]; then
  echo "Creating virtual environment and installing dependencies..."
  python3 -m venv "$BACKEND_DIR/.venv"
  "$PYTHON" -m pip install -q -r "$BACKEND_DIR/requirements.txt"
fi
exec "$PYTHON" -m uvicorn --app-dir "$BACKEND_DIR" app.main:app --host 0.0.0.0 --port 8000 --reload
