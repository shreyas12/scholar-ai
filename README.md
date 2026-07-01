# ScholarAI

A **local-first platform for evidence-based learning** that turns your personal notes into an intelligent tutor — and measures your actual *mastery* of the material instead of tracking document completion.

> Create a learning space → Add documents → Chat with your notes → Measure your understanding → *Am I interview-ready?*

Built on production-style RAG (a Knowledge Processing Pipeline + staged retrieval),
a concept graph, and an event-driven mastery model. No accounts. No cloud. No
subscriptions. No API keys required for the default experience.

## Status

✅ **Phase 0 (skeleton) + Phase 1 (core loop) complete.**

- **Phase 0:** FastAPI backend (`/health`, config, storage, Ollama + embeddings
  wrappers, prompt versioning); React/Tailwind/shadcn frontend with setup status.
- **Phase 1:** Learning spaces (CRUD), document upload + simple ingest
  (extract → chunk → embed → FAISS) with change detection, and grounded
  streaming chat with citations + persisted history. **36 backend tests pass**,
  including real embedding + FAISS retrieval.

- **Phase 2:** basic concept extraction — an LLM pass builds a per-space concept
  set from the chunks; chat tags retrieved chunks with concepts and records
  **coverage** (concepts encountered, not documents read); a Dashboard tab shows
  the concept map + coverage bar. **44 backend tests pass.**

The full loop works today: **create a space → upload notes → chat with citations
→ watch the concept map fill in**. Chat + concept extraction need
[Ollama](https://ollama.com) running (`ollama pull qwen3:8b`); everything else
(spaces, upload, ingest, retrieval, coverage) runs with no external services.

Next: Phase 3 (the full Knowledge Processing Pipeline + advanced retrieval).

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
