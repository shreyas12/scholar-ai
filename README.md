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

- **Phase 2:** basic concept extraction + **coverage** (concepts encountered, not
  documents read).
- **Phase 3:** the full **Knowledge Processing Pipeline** — structured extraction,
  cleaning, hierarchical + adaptive + multi-level chunking, quality scoring,
  keywords, semantic boundaries, dedup, parent-child hierarchy — plus advanced
  retrieval (rerank, neighbor expansion, compression, retrieval confidence, query
  expansion, multi-query). Toggleable stages via `pipeline.yaml`.
- **Phase 4:** the **concept graph** — canonicalized concepts, LLM-inferred
  prerequisite edges, a graph API, and "ready to learn" coverage.
- **Phase 5:** **assessment + event-driven mastery** — per-concept quizzes
  (recall / recognition / application) generated from your material, LLM-judge
  grading for free-text + deterministic MCQ grading, confidence capture,
  misconception flags, an append-only event log, and mastery computed as a
  replayable projection over that log. A **retention model** decays mastery from
  the last correct recall (stability grows with practice) and schedules the next
  review — all computed on read. A Quiz tab drives it; the **learning dashboard**
  shows bucket counts (mastered / learning / weak / untested), "next study
  targets" that jump straight into a quiz, and an expandable per-concept card
  (recall / recognition / application / confidence / retention / evidence / last
  correct / review-by).

**112 backend tests pass.** The loop works today: **create a space → upload notes
→ chat with grounded, confidence-scored citations → build the concept map + graph
→ quiz yourself and watch demonstrated mastery accumulate (and decay if you don't
review)**. LLM features (chat generation, concept extraction, question
generation, grading, summaries, query expansion) need
[Ollama](https://ollama.com) (`ollama pull qwen3:8b`); everything else runs with
no external services.

Next: Epic 9 — setup / offline / polish (one-command setup, Ollama guidance in
UI, offline verification, error toasts, demo space) and the flagship Interview
Readiness mode.

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
