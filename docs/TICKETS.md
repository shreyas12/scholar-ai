# ScholarAI — Tickets

Grouped by epic, ordered by the phasing in [`PLAN.md`](PLAN.md §8).
IDs are stable; check the box when done. `S/M/L` = rough size.

Legend: **[BE]** backend · **[FE]** frontend · **[INFRA]** tooling/setup ·
**[ML]** LLM/embeddings.

---

## EPIC 0 — Project skeleton (Phase 0)

- [ ] **SA-001** [INFRA] `S` Repo layout: `backend/`, `frontend/`, `scripts/`, `docs/`, `.gitignore`, LICENSE (MIT), root README.
- [ ] **SA-002** [BE] `S` FastAPI app boot + `/health` endpoint + CORS for localhost frontend.
- [ ] **SA-003** [FE] `S` Vite + React + TailwindCSS + shadcn/ui scaffold; hit `/health` from UI.
- [ ] **SA-004** [BE] `M` Storage layer: resolve data root (`~/scholar-ai-data`), space folder helpers, safe JSON read/write with locking.
- [ ] **SA-005** [ML] `S` Ollama client wrapper: config (base URL, model), `generate`/`chat`, graceful error if Ollama not running.
- [ ] **SA-006** [ML] `S` Embedding service: load `bge-small`, `embed(texts) -> vectors`, warm-up on startup.
- [ ] **SA-007** [INFRA] `S` `scripts/dev.sh` (run backend + frontend), pyproject/requirements, frontend package.json.
- [ ] **SA-008** [INFRA] `S` Config module + `.env.example` (data dir, ollama url, model, embed model, overlap %, top-k).

---

## EPIC 1 — Learning Spaces

- [ ] **SA-010** [BE] `M` Spaces CRUD API: create / list / rename / delete / open; writes `space.json`; enforces isolation.
- [ ] **SA-011** [BE] `S` Delete space = remove folder + FAISS index safely (confirm-guarded).
- [ ] **SA-012** [FE] `M` Spaces list + create/rename/delete UI (shadcn dialogs), empty state.
- [ ] **SA-013** [FE] `S` Space detail shell with tabs: Documents · Chat · Dashboard.

---

## EPIC 2 — Document management (basic, Phase 1)

- [ ] **SA-020** [BE] `M` Upload endpoint: accept PDF/MD/TXT/DOCX, store under `documents/<doc_id>/`, write checksum.
- [ ] **SA-021** [BE] `M` **Simple** ingest v0: extract text → fixed-size overlap chunks → embed → FAISS. (Unblocks chat before the full pipeline.)
- [ ] **SA-022** [BE] `S` FAISS per-space index: build/load/append, `id_map.json` (row→chunk_id), persist to `vectors/`.
- [ ] **SA-023** [BE] `S` Document list + delete API; deleting a doc removes its chunks from the index (rebuild).
- [ ] **SA-024** [BE] `M` Change detection: on re-upload compare sha256 → re-ingest + rebuild index automatically.
- [ ] **SA-025** [FE] `M` Documents tab: drag-drop upload, progress/status per doc, list with size/type, delete.

---

## EPIC 3 — AI Chat (Phase 1)

- [ ] **SA-030** [BE] `M` Retrieval service: embed query → FAISS top-k → assemble context + citations.
- [ ] **SA-031** [BE] `M` Chat endpoint (streaming): grounded prompt ("answer only from context, cite doc+page"), stream tokens.
- [ ] **SA-032** [BE] `S` Return structured sources (doc name, page, heading path) alongside the answer.
- [ ] **SA-033** [FE] `M` Chat UI: message list, streaming render, source chips, empty/error states (Ollama down).
- [ ] **SA-034** [BE] `S` Persist chat history per space (`chat.json`) — optional but cheap; feeds evidence later.

---

## EPIC 4 — Advanced ingestion pipeline (Phase 2)

*Replaces SA-021 simple ingest. Each stage independently testable.*

- [ ] **SA-040** [BE] `L` Stage 1 — structured extraction per format (PDF/DOCX/MD/TXT): headings, lists, tables, page numbers, paragraphs → `extracted.json`.
- [ ] **SA-041** [BE] `M` Stage 2 — cleaning: repeated headers/footers, page numbers, whitespace, OCR artifacts, broken line-wrap. Meaning-preserving.
- [ ] **SA-042** [BE] `M` Stage 3 — hierarchical chunking (heading→subheading→paragraph→sentence).
- [ ] **SA-043** [BE] `S` Stage 4 — sliding-window overlap (configurable 15–25%).
- [ ] **SA-044** [BE] `S` Stage 5 — metadata enrichment (heading path, page, chunk #, prev/next ids, timestamps).
- [ ] **SA-045** [BE+ML] `M` Stage 6 — LLM concept extraction per chunk (batched, cached by checksum, toggleable).
- [ ] **SA-046** [BE+ML] `M` Stage 7 — LLM chunk summarization (batched, cached, toggleable).
- [ ] **SA-047** [BE] `S` Stage 8 — embeddings over final chunks (bge-small).
- [ ] **SA-048** [BE] `S` Stage 9 — parent–child relationships (doc→section→chunk) persisted.
- [ ] **SA-049** [BE] `M` Stage 10 — neighbor expansion at retrieval (include prev/next chunk).
- [ ] **SA-050** [BE] `S` Pipeline orchestrator: linear, resumable, per-stage logging + "fast ingest" mode (skip 6/7).
- [ ] **SA-051** [BE] `S` Retrieval abstraction (Stage 11 hook) so BM25/rerank/hybrid can drop in later. Interface only.

---

## EPIC 5 — Concepts & concept graph (Phase 3)

- [ ] **SA-060** [BE+ML] `M` Aggregate chunk-level concepts → space concept set; canonicalize/dedup (normalize + fuzzy match).
- [ ] **SA-061** [BE+ML] `M` Prerequisite edges: LLM pass to link concepts into a graph → `concepts.json`.
- [ ] **SA-062** [BE] `S` Concepts API: list concepts, get graph, get source chunks per concept.
- [ ] **SA-063** [BE] `S` Coverage signal: mark concept "encountered"; compute space coverage %.
- [ ] **SA-064** [FE] `S` (Optional MVP) simple concept list view with coverage badges. (Full graph viz is out of scope.)

---

## EPIC 6 — Assessment & evidence (Phase 4)

- [ ] **SA-070** [BE+ML] `M` Question generator per concept: recall (explain), recognition (MCQ/T-F/matching), application (scenario).
- [ ] **SA-071** [BE+ML] `M` LLM-judge grader for free-text (recall/application) with explicit rubric in one file.
- [ ] **SA-072** [BE] `S` Recognition auto-grading (deterministic for MCQ/T-F/matching).
- [ ] **SA-073** [BE] `S` Confidence capture (1–5) attached to each answer event.
- [ ] **SA-074** [BE] `S` Evidence store: append events to `progress.json` per concept (recall/recognition/application/confidence).
- [ ] **SA-075** [BE] `S` Misconception flag when incorrect + high confidence.
- [ ] **SA-076** [FE] `M` Quiz UI: question card, answer input (free-text / MCQ), confidence slider, feedback + explanation.
- [ ] **SA-077** [BE] `S` Chat-as-evidence hook: optionally grade a chat answer and record it against a concept.

---

## EPIC 7 — Mastery scoring & retention (Phase 4)

- [ ] **SA-080** [BE] `M` Mastery service: combine recall/recognition/application + confidence modifier → per-concept overall (isolated, unit-tested).
- [ ] **SA-081** [BE] `S` Retention model: last_reviewed, decay-based retention estimate, next_review date.
- [ ] **SA-082** [BE] `S` Bucketing: Mastered / Learning / Weak / Unknown thresholds.
- [ ] **SA-083** [BE] `S` Space-level rollup: overall mastery %, counts per bucket.

---

## EPIC 8 — Learning dashboard (Phase 5)

- [ ] **SA-090** [FE] `M` Dashboard: overall mastery, concept counts (mastered/learning/weak/unknown), per-concept scores.
- [ ] **SA-091** [FE] `S` Weak-concept surfacing: "next recommended study targets" list linking into quiz.
- [ ] **SA-092** [FE] `S` Concept detail: coverage/recall/recognition/application/confidence/retention breakdown (the HNSW example card).
- [ ] **SA-093** [FE] `S` Language check — copy says "mastered X of Y concepts", never "% of documents read".

---

## EPIC 9 — Setup, offline & polish (Phase 6)

- [ ] **SA-100** [INFRA] `M` One-command setup + clear "Ollama not found / model not pulled" guidance in UI.
- [ ] **SA-101** [INFRA] `S` Offline verification: no network calls after model pull (audit + note in README).
- [ ] **SA-102** [INFRA] `S` README quickstart validated on a clean machine (< 5 min).
- [ ] **SA-103** [INFRA] `S` Basic error handling + toasts across FE; backend structured logging.
- [ ] **SA-104** [INFRA] `S` Seed/demo space for first-run experience.

---

## Explicitly OUT of scope (MVP)

Video/YouTube/website/paper ingestion · knowledge-graph visualization ·
adaptive quizzes · interview mode · spaced repetition scheduler ·
personalized roadmap · multi-model (OpenAI/Anthropic/OpenRouter) · shared spaces ·
BM25/hybrid/rerank retrieval (interface stubbed only).

---

## Suggested build order (critical path)

`SA-001→008` (skeleton) → `SA-010,012` (spaces) → `SA-020,021,022` (upload+simple
ingest) → `SA-030,031,033` (chat) → **usable app** → `SA-040…050` (real pipeline)
→ `SA-060…063` (concepts) → `SA-070…077` (assessment) → `SA-080…083` (mastery) →
`SA-090…093` (dashboard) → `SA-100…104` (polish).
