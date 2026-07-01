# ScholarAI

A **local-first platform for evidence-based learning** that turns your personal notes into an intelligent tutor — and measures your actual *mastery* of the material instead of tracking document completion.

> Create a learning space → Add documents → Chat with your notes → Measure your understanding → *Am I interview-ready?*

Built on production-style RAG (a Knowledge Processing Pipeline + staged retrieval),
a concept graph, and an event-driven mastery model. No accounts. No cloud. No
subscriptions. No API keys required for the default experience.

## Status

✅ **Phase 0 (skeleton) complete** — FastAPI backend with `/health`, config,
storage layer, Ollama + embeddings service wrappers, prompt versioning; React +
Tailwind + shadcn/ui frontend with a live setup-status screen. Next: Phase 1
(spaces → documents → chat).

See:

- [`docs/PLAN.md`](docs/PLAN.md) — architecture, data model, phasing, key decisions
- [`docs/TICKETS.md`](docs/TICKETS.md) — the work broken into epics and tickets

## Repo layout

```
backend/    FastAPI app (app/), versioned prompts (prompts/), tests (tests/)
frontend/   Vite + React + Tailwind + shadcn/ui
scripts/    dev.sh — one command to run both
docs/       PLAN.md, TICKETS.md
```

## Develop

```bash
./scripts/dev.sh          # backend :8000 + frontend :5173

# or individually:
cd backend && python3 -m venv .venv && ./.venv/bin/pip install -e ".[ml,dev]"
./.venv/bin/uvicorn app.main:app --reload      # API
./.venv/bin/pytest                             # tests

cd frontend && npm install && npm run dev       # UI
```

## Stack (planned)

| Layer      | Choice                              |
|------------|-------------------------------------|
| LLM        | Ollama (`qwen3:8b` / `gemma3:12b`)  |
| Embeddings | `BAAI/bge-small-en-v1.5` (local)    |
| Backend    | FastAPI                             |
| Frontend   | React + TailwindCSS + shadcn/ui     |
| Vector DB  | FAISS                               |
| Storage    | Local filesystem (per-space folders)|

## Quickstart (target experience)

```bash
git clone <repo> && cd scholar-ai
# install Ollama, then:
ollama pull qwen3:8b
./scripts/dev.sh        # starts backend + frontend
```
