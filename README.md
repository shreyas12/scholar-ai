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

- **Epic 9:** setup & polish — one-command `setup.sh`, in-UI setup guidance when
  Ollama/the model isn't ready, error toasts, structured request logging, a
  fully-offline mode, and a seeded **demo space** so the first run is populated.

Next: the flagship **Interview Readiness mode** — walk a topic's prerequisites
over the concept graph, analyse gaps, and generate an adaptive interview.

See:

- [`docs/PLAN.md`](docs/PLAN.md) — architecture, data model, phasing, key decisions
- [`docs/TICKETS.md`](docs/TICKETS.md) — the work broken into epics and tickets

## Repo layout

```
backend/    FastAPI app (app/), versioned prompts (prompts/), tests (tests/)
frontend/   Vite + React + Tailwind + shadcn/ui
scripts/    setup.sh (one-command setup) · dev.sh (run both) · seed_demo.py
docs/       PLAN.md, TICKETS.md
```

## Develop

```bash
./scripts/setup.sh        # first time: venvs, deps, demo space
./scripts/dev.sh          # backend :8000 + frontend :5173

# or individually:
cd backend && python3 -m venv .venv && ./.venv/bin/pip install -e ".[ml,dev]"
./.venv/bin/uvicorn app.main:app --reload      # API
./.venv/bin/pytest                             # tests (112)

cd frontend && npm install && npm run dev       # UI

# reseed the demo space anytime:
./backend/.venv/bin/python scripts/seed_demo.py --force
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

## Quickstart (< 5 min)

```bash
git clone <repo> && cd scholar-ai

# 1. One command: backend venv + deps, frontend deps, and a seeded demo space.
./scripts/setup.sh

# 2. Install a local model (skip if you already have Ollama + a model).
#    On CPU, a non-thinking model like llama3.2:3b is snappiest:
ollama pull llama3.2:3b
echo 'SCHOLARAI_OLLAMA_MODEL=llama3.2:3b' >> backend/.env

# 3. Run it.
./scripts/dev.sh        # backend :8000 + frontend :5173
```

Open <http://localhost:5173> and pick the **ScholarAI Demo** space — the concept
graph and demonstrated mastery are already populated. The app boots and serves
the UI even without Ollama; the header tells you exactly what's missing and how to
fix it.

**Model choice.** The app defaults to `qwen3:8b`. `qwen3` models *reason* before
answering — great quality, but slow on CPU (a long silent pause per call). On a
CPU-only machine prefer a non-thinking model (`llama3.2:3b`) via
`SCHOLARAI_OLLAMA_MODEL`.

### Running fully offline

Everything runs locally: the LLM is Ollama on your machine, embeddings are a
local `sentence-transformers` model, and all data is plain files. The *only*
outbound network calls are a one-time download of the embedding model from the
Hugging Face Hub on first ingest (and whatever `ollama pull` fetches). After the
embedding model is cached, set `SCHOLARAI_OFFLINE=1` (in `backend/.env`) to forbid
all further network access — the loader then reads only the local cache.
