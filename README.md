# ScholarAI

**A local-first, private study companion that measures what you actually
*understand* — not how many pages you've read.**

Point it at your notes, textbooks, or papers. It builds a searchable knowledge
base, maps the *concepts* inside it (and how they depend on each other), then
generates quizzes and grades your answers to track **demonstrated mastery** of
each concept over time — with a forgetting curve that tells you when to review.

Everything runs on your machine. No accounts, no cloud, no API keys, no data
leaves your laptop.

> **The core idea:** most "learning" apps track *consumption* — documents opened,
> videos watched, checkboxes ticked. ScholarAI treats that as a vanity metric.
> It models a subject as a **graph of concepts** and only counts a concept as
> *mastered* when you've **demonstrated** it — explained it, recognised it, and
> applied it — grading each attempt against your own source material.

---

## Table of contents

- [Why this project is interesting](#why-this-project-is-interesting)
- [What you can do with it](#what-you-can-do-with-it)
- [How it works (architecture)](#how-it-works-architecture)
- [Getting started](#getting-started)
- [Using the app](#using-the-app)
- [Design decisions worth calling out](#design-decisions-worth-calling-out)
- [Testing](#testing)
- [Project status & roadmap](#project-status--roadmap)
- [Tech stack](#tech-stack)
- [Repo layout](#repo-layout)

---

## Why this project is interesting

A quick tour of the engineering, for anyone evaluating the work:

- **Event-sourced mastery.** Every graded interaction is an immutable event in an
  append-only log. A concept's mastery score is *never stored* — it's a
  **projection recomputed from the event log on read**. Tune the scoring formula
  and replay history; no evidence is ever lost, and you can always answer *"why
  is this concept at 82%?"* by pointing at the events.
- **A retention model that decays on read.** Mastery follows a forgetting curve
  from your last correct recall; the stability grows the more you practise
  (spaced-repetition intuition). Decay is a pure function of event timestamps, so
  a concept quietly slips out of "mastered" and flags itself for review if you
  neglect it. The clock is *injectable*, which keeps the whole thing
  deterministically unit-testable.
- **Production-style RAG, not a toy.** Ingestion is an 11-stage *Knowledge
  Processing Pipeline*: structured block extraction → hierarchical sectioning →
  cleaning → adaptive multi-level chunking → quality scoring → keyword/summary
  enrichment → embedding, with semantic-boundary detection and index-time dedup.
  Retrieval adds rerank-by-diversity, parent/neighbour expansion, context
  compression to a token budget, a **retrieval-confidence** signal, and optional
  LLM query-expansion / multi-query. Every stage is toggleable via `pipeline.yaml`.
- **A real concept graph.** Concepts are extracted per section, **canonicalised by
  embedding similarity** (so "HNSW" and "HNSW algorithm" merge), and linked with
  **LLM-inferred prerequisite edges** — which powers "ready to learn" hints and,
  soon, interview prep.
- **Auditable LLM usage.** Prompts are versioned files (`prompts/<name>_v<N>.md`);
  every LLM-produced record is stamped with the exact prompt version that made
  it, so you can tell *why* a grade or extraction changed after a prompt edit.
- **Graceful degradation & offline-first.** The API boots and serves the UI with
  no model installed; LLM features fail *cleanly* with actionable messages instead
  of crashing. After a one-time model download it runs with **zero network
  access**.
- **Tested like it matters.** **112 tests** cover real embedding + FAISS retrieval
  and full mocked-LLM loops (ingest → extract → quiz → grade → mastery), plus pure
  unit tests for the scoring/retention math.

Roughly **7,500 lines** across a FastAPI backend (3.9k), a React/TypeScript
frontend (2.2k), and tests (1.4k) — **22 REST endpoints**, **9 versioned
prompts**, built from a **96-ticket plan** (86 shipped so far).

---

## What you can do with it

1. **Create a learning space** — one isolated workspace per subject.
2. **Upload documents** (PDF / DOCX / Markdown / TXT). They're parsed, chunked,
   embedded, and indexed locally.
3. **Chat with your material** — grounded, streaming answers with **citations**
   and a **confidence badge** showing how well-supported each answer is. It won't
   make things up: no relevant material → it says so.
4. **Extract the concept map** — the concepts in your space, canonicalised, with
   prerequisite edges and "ready to learn" hints.
5. **Quiz yourself** — auto-generated **recall / recognition (MCQ) / application**
   questions per concept, with a confidence slider. Free-text answers are graded
   by an LLM judge against your sources; MCQs are graded deterministically.
6. **Track mastery** — a dashboard of Mastered / Learning / Weak / Untested
   buckets, **"next study targets"** that jump straight into a quiz, flagged
   **misconceptions** (confidently wrong answers), and **review-due** concepts
   whose retention has decayed.

> **Want to see it without any setup?** Running `./scripts/setup.sh` seeds a
> **"ScholarAI Demo"** space with a populated concept graph and mastery dashboard,
> so you can explore the finished experience in seconds.

---

## How it works (architecture)

```
┌────────────────────────────────────────────────────────────────────┐
│  React + Vite + Tailwind + shadcn/ui                                 │
│  Spaces · Documents · Chat (streaming) · Quiz · Mastery Dashboard    │
└───────────────────────────────┬────────────────────────────────────┘
                                 │  REST / NDJSON stream
┌───────────────────────────────▼────────────────────────────────────┐
│  FastAPI backend                                                     │
│                                                                      │
│  Knowledge Pipeline   Retrieval           Assessment & Mastery       │
│  ─────────────────    ─────────           ──────────────────────     │
│  extract → section    embed query         question generator         │
│  → clean → chunk      → FAISS search      LLM-judge / MCQ grader      │
│  (multi-level)        → rerank            append-only event log ──┐   │
│  → score → enrich     → neighbour expand                         │   │
│  → embed → FAISS      → compress          mastery = projection ◄──┘   │
│         │             → confidence        over the event log         │
│         ▼                  │                    │  (+ retention decay) │
│   Concept graph  ◄─────────┘                    ▼                     │
│   (canonicalise +                          Learning dashboard        │
│    prerequisite edges)                                               │
└───────────────────────────────┬────────────────────────────────────┘
                    ┌────────────┴────────────┐
                    ▼                          ▼
             Ollama (local LLM)        sentence-transformers
             qwen3 / llama3.2          bge-small (local embeddings)
                    │
                    ▼
        Plain-file storage per space:
        documents/ · vectors/index.faiss · concepts.json ·
        progress.json · events.json     (atomic writes + file locks)
```

**Data model.** Each space is a folder of plain files — no database. Chunks,
sections, the concept graph, coverage, and the event log are all JSON;
FAISS holds only vectors plus a row→chunk_id map. Writes are atomic (temp file +
`os.replace`) under a file lock, so a crash never corrupts state.

For the full design — the 11 pipeline stages, the mastery model, and the key
decisions — see [`docs/PLAN.md`](docs/PLAN.md). The work is broken into epics and
tickets in [`docs/TICKETS.md`](docs/TICKETS.md).

---

## Getting started

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.12+** | Backend + embeddings |
| **Node 18+** | Frontend |
| **[Ollama](https://ollama.com)** | *Optional but recommended* — the local LLM. The app runs without it (browse spaces, upload docs), but chat / quizzes / concept extraction need it. |
| **~3 GB disk** | For one local model + the embedding model |

### 1. Set everything up (one command)

```bash
git clone <repo> && cd scholar-ai
./scripts/setup.sh
```

This creates the backend virtualenv, installs backend + frontend dependencies,
and seeds the demo space. It also checks whether Ollama is running and tells you
what to do if not.

### 2. Install a local model

If you don't already have Ollama running with a model pulled:

```bash
# Install Ollama from https://ollama.com, then start it:
ollama serve

# Pull a model. On a CPU-only machine, a *non-thinking* model is much snappier:
ollama pull llama3.2:3b
echo 'SCHOLARAI_OLLAMA_MODEL=llama3.2:3b' >> backend/.env
```

> **Choosing a model.** The app defaults to `qwen3:8b` for quality. But `qwen3`
> is a *reasoning* model — it generates a long hidden "thinking" pass before every
> answer, which is slow on a CPU (a multi-second silent wait per call). On
> CPU-only hardware, prefer a non-thinking model like **`llama3.2:3b`** (fast,
> ~2 GB) and set it via `SCHOLARAI_OLLAMA_MODEL`. With a GPU, `qwen3:8b` is great.

### 3. Run it

```bash
./scripts/dev.sh          # backend on :8000, frontend on :5173
```

Open **<http://localhost:5173>** and open the **ScholarAI Demo** space to see a
populated dashboard immediately.

The header shows a live readiness indicator; if Ollama or the model isn't ready,
a banner tells you the **exact command** to fix it.

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| Header says "Setup incomplete" | Follow the on-screen banner — it prints the exact command (start Ollama / pull the model / install ML deps). |
| Chat/quiz answers are very slow | You're likely on a CPU with a reasoning model. Switch to `llama3.2:3b` (see step 2). |
| First document upload pauses ~5 s | One-time embedding-model load into memory. Normal; only once per run. |
| "I don't have enough material…" in chat | Correct behaviour — upload documents first. Chat is grounded and won't hallucinate. |

### Running fully offline

Everything is local: the LLM is Ollama on your machine, embeddings are a local
`sentence-transformers` model, and all data is plain files. The *only* outbound
calls are one-time model downloads (the embedding model on first ingest, plus
`ollama pull`). Once the embedding model is cached, set `SCHOLARAI_OFFLINE=1` in
`backend/.env` to forbid all further network access.

---

## Using the app

1. **Documents tab** — upload notes for a subject. Watch them ingest.
2. **Dashboard tab → Extract concepts** — build the concept map + prerequisite
   graph from your material.
3. **Chat tab** — ask questions; get grounded answers with citations and a
   confidence badge.
4. **Quiz tab** — pick a concept, answer recall/MCQ/application questions, rate
   your confidence, get graded feedback (with misconceptions flagged).
5. **Dashboard tab** — watch demonstrated mastery accumulate, see your weakest
   concepts surfaced as study targets, and revisit concepts as their retention
   decays.

---

## Design decisions worth calling out

- **Mastery is a projection, never a stored number.** Event-sourcing makes the
  system auditable ("show me the evidence") and future-proof (retune the formula
  and replay). The scoring math lives in one isolated, unit-tested module.
- **Deterministic-first pipeline.** Concept extraction and the deterministic
  ingest pipeline were built *before* the fancy LLM enrichment, so the core loop
  works and is testable without a model running.
- **Per-section concept extraction** (not per-chunk): concepts belong to a
  section's material, and a section maps to chunks at every granularity — so
  tagging by section is cheaper *and* robust to which chunk level was retrieved.
- **Everything degrades gracefully.** Ollama down? Retrieval still works; LLM
  features return a clean 503 with an actionable message. Embeddings missing? The
  API still boots and serves `/health`.
- **Testability designed in.** The mastery clock is injectable; LLM calls are
  mocked in tests by routing on prompt content; the full pipeline is exercised
  end-to-end without a live model.
- **Privacy by construction.** No accounts, no telemetry, no cloud. Your study
  material and your performance data live only in `~/scholar-ai-data`.

---

## Testing

```bash
cd backend && ./.venv/bin/pytest        # 112 tests, ~45s
```

The suite covers real embedding + FAISS retrieval, the full ingest→quiz→grade→
mastery loop (with a mocked LLM), the concept-graph canonicalisation and
prerequisite parsing, and pure-function tests for the mastery blend, confidence
modifier, buckets, and retention curve. The frontend is type-checked with
`tsc --noEmit` and builds with `vite build`.

---

## Project status & roadmap

**Phases 0–5 complete + fully polished (Epics 0–9).** 86 of 96 planned tickets.

| Phase | What shipped |
|-------|--------------|
| **0 – Foundation** | FastAPI skeleton, filesystem storage (atomic + locked), Ollama + embedding wrappers, **prompt versioning** |
| **1 – Core loop** | Learning spaces, document upload + ingest + FAISS, grounded **streaming chat** with citations |
| **2 – Concepts** | Per-section concept extraction + **coverage** (encountered ≠ mastered) |
| **3 – Knowledge Pipeline** | 11-stage structured ingestion + advanced retrieval (rerank, expansion, compression, confidence, query expansion) |
| **4 – Concept graph** | Canonicalisation, LLM-inferred prerequisites, graph API, "ready to learn" |
| **5 – Assessment & mastery** | Quiz generation, LLM-judge + MCQ grading, event log, **mastery projection**, **retention model**, learning dashboard |
| **9 – Setup & polish** | One-command setup, in-UI guidance, error toasts, structured logging, offline mode, **seeded demo space** |

**Next up — the flagship *Interview Readiness* mode:** pick a target topic, walk
its prerequisites over the concept graph, analyse gaps (strong / weak / missing),
generate an adaptive interview targeting the gaps, and compute a readiness score —
reusing the question generator and event store already built. Plus a retrieval
evaluation harness (Recall@K / MRR / NDCG) and multi-model benchmarking.

---

## Tech stack

| Layer | Choice |
|-------|--------|
| LLM | [Ollama](https://ollama.com) — local (`qwen3:8b` default, `llama3.2:3b` for CPU) |
| Embeddings | `BAAI/bge-small-en-v1.5` via `sentence-transformers` (local) |
| Vector search | FAISS (one index per space) |
| Backend | FastAPI (async), Pydantic |
| Frontend | React + TypeScript + Vite + TailwindCSS + shadcn/ui |
| Storage | Local filesystem — plain JSON, atomic writes + file locks |
| Tests | pytest (112) |

---

## Repo layout

```
backend/
  app/
    knowledge/     11-stage ingestion pipeline (plugin stages, pipeline.yaml)
    services/      retrieval, concepts, assessment, mastery, events, embeddings…
    routers/       22 REST endpoints
    prompts.py     versioned-prompt loader
  prompts/         9 versioned prompt files (chat, grading, question_gen, …)
  tests/           112 tests
frontend/src/      React app (components/, lib/)
scripts/           setup.sh · dev.sh · seed_demo.py
docs/              PLAN.md (architecture) · TICKETS.md (the plan)
```

---

## License

MIT — see [`LICENSE`](LICENSE).
