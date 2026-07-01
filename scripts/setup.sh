#!/usr/bin/env bash
# One-command setup for ScholarAI (SA-100): backend venv + deps, frontend deps,
# a seeded demo space, and a clear check of the local LLM. Safe to re-run.
#
#   ./scripts/setup.sh          # set everything up
#   ./scripts/setup.sh --model llama3.2:3b   # also pull this Ollama model
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
MODEL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL="${2:-}"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "→ [1/4] Backend virtualenv + dependencies..."
if [ ! -d "$BACKEND/.venv" ]; then
  python3 -m venv "$BACKEND/.venv"
fi
"$BACKEND/.venv/bin/pip" install -q --upgrade pip
"$BACKEND/.venv/bin/pip" install -q -e "$BACKEND[ml,dev]"

echo "→ [2/4] Frontend dependencies..."
if [ ! -d "$FRONTEND/node_modules" ]; then
  ( cd "$FRONTEND" && npm install )
else
  echo "   (node_modules present — skipping npm install)"
fi

echo "→ [3/4] Local LLM (Ollama) check..."
if ! command -v ollama >/dev/null 2>&1; then
  echo "   ⚠ Ollama is not installed. Install it from https://ollama.com, then re-run."
  echo "     (The app boots without it — chat/quizzes/extraction just stay offline until it's up.)"
elif ! curl -s -m 3 http://localhost:11434/api/version >/dev/null 2>&1; then
  echo "   ⚠ Ollama is installed but not running. Start it with:  ollama serve"
else
  echo "   ✓ Ollama is running."
  if [ -n "$MODEL" ]; then
    echo "   → Pulling model '$MODEL' (one-time)..."
    ollama pull "$MODEL"
    echo "     Set it as the app default:  echo 'SCHOLARAI_OLLAMA_MODEL=$MODEL' >> backend/.env"
  else
    echo "     Pull a model when ready, e.g.:  ollama pull llama3.2:3b"
    echo "     (non-thinking models like llama3.2:3b are snappiest on CPU)"
  fi
fi

echo "→ [4/4] Seeding a demo space..."
"$BACKEND/.venv/bin/python" "$ROOT/scripts/seed_demo.py" || true

echo
echo "✓ Setup complete. Start the app with:  ./scripts/dev.sh"
echo "  Then open http://localhost:5173 and explore the “ScholarAI Demo” space."
