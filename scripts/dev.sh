#!/usr/bin/env bash
# Start the ScholarAI backend + frontend for local development (SA-007).
# Usage: ./scripts/dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# --- Backend -----------------------------------------------------------------
if [ ! -d "$BACKEND/.venv" ]; then
  echo "→ Creating backend virtualenv..."
  python3 -m venv "$BACKEND/.venv"
  "$BACKEND/.venv/bin/pip" install -q --upgrade pip
  echo "→ Installing backend deps (core; run with .[ml] for embeddings)..."
  "$BACKEND/.venv/bin/pip" install -q -e "$BACKEND"
fi

echo "→ Starting backend on http://localhost:8000 ..."
( cd "$BACKEND" && ./.venv/bin/uvicorn app.main:app --reload --port 8000 ) &
BACKEND_PID=$!

# --- Frontend ----------------------------------------------------------------
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "→ Installing frontend deps..."
  ( cd "$FRONTEND" && npm install )
fi

echo "→ Starting frontend on http://localhost:5173 ..."
( cd "$FRONTEND" && npm run dev ) &
FRONTEND_PID=$!

trap 'echo; echo "Shutting down..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' INT TERM
wait
