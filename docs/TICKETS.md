# ScholarAI — Tickets

Grouped by epic, ordered by the phasing in [`PLAN.md`](PLAN.md §8).
IDs are stable; check the box when done. `S/M/L` = rough size.

Legend: **[BE]** backend · **[FE]** frontend · **[INFRA]** tooling/setup ·
**[ML]** LLM/embeddings.

---

## EPIC 0 — Project skeleton (Phase 0) ✅ DONE

- [x] **SA-001** [INFRA] `S` Repo layout: `backend/`, `frontend/`, `scripts/`, `docs/`, `.gitignore`, LICENSE (MIT), root README.
- [x] **SA-002** [BE] `S` FastAPI app boot + `/health` endpoint + CORS for localhost frontend.
- [x] **SA-003** [FE] `S` Vite + React + TailwindCSS + shadcn/ui scaffold; hit `/health` from UI.
- [x] **SA-004** [BE] `M` Storage layer: resolve data root (`~/scholar-ai-data`), space folder helpers, safe JSON read/write with locking.
- [x] **SA-005** [ML] `S` Ollama client wrapper: config (base URL, model), `generate`/`chat`, graceful error if Ollama not running.
- [x] **SA-006** [ML] `S` Embedding service: load `bge-small`, `embed(texts) -> vectors`, warm-up on startup.
- [x] **SA-007** [INFRA] `S` `scripts/dev.sh` (run backend + frontend), pyproject/requirements, frontend package.json.
- [x] **SA-008** [INFRA] `S` Config module + `.env.example` (data dir, ollama url, model, embed model, overlap %, top-k).
- [x] **SA-009** [BE] `S` **Prompt versioning convention (adopt now):** all prompts as files under `prompts/*_vN.md` + a loader; every LLM call records the prompt version it used. Cheap now, avoids "why did scores change?" later.

---

## EPIC 1 — Learning Spaces ✅ DONE

- [x] **SA-010** [BE] `M` Spaces CRUD API: create / list / rename / delete / open; writes `space.json`; enforces isolation.
- [x] **SA-011** [BE] `S` Delete space = remove folder + FAISS index safely (confirm-guarded).
- [x] **SA-012** [FE] `M` Spaces list + create/rename/delete UI (shadcn dialogs), empty state.
- [x] **SA-013** [FE] `S` Space detail shell with tabs: Documents · Chat · Dashboard.

---

## EPIC 2 — Document management (basic, Phase 1) ✅ DONE

- [x] **SA-020** [BE] `M` Upload endpoint: accept PDF/MD/TXT/DOCX, store under `documents/<doc_id>/`, write checksum.
- [x] **SA-021** [BE] `M` **Simple** ingest v0: extract text → fixed-size overlap chunks → embed → FAISS. (Unblocks chat before the full pipeline.)
- [x] **SA-022** [BE] `S` FAISS per-space index: build/load/append, `id_map.json` (row→chunk_id), persist to `vectors/`.
- [x] **SA-023** [BE] `S` Document list + delete API; deleting a doc removes its chunks from the index (rebuild).
- [x] **SA-024** [BE] `M` Change detection: on re-upload compare sha256 → re-ingest + rebuild index automatically.
- [x] **SA-025** [FE] `M` Documents tab: drag-drop upload, progress/status per doc, list with size/type, delete.

---

## EPIC 3 — AI Chat (Phase 1) ✅ DONE

- [x] **SA-030** [BE] `M` Retrieval service: embed query → FAISS top-k → assemble context + citations.
- [x] **SA-031** [BE] `M` Chat endpoint (streaming): grounded prompt ("answer only from context, cite doc+page"), stream tokens.
- [x] **SA-032** [BE] `S` Return structured sources (doc name, page, heading path) alongside the answer.
- [x] **SA-033** [FE] `M` Chat UI: message list, streaming render, source chips, empty/error states (Ollama down).
- [x] **SA-034** [BE] `S` Persist chat history per space (`chat.json`) — optional but cheap; feeds evidence later.

---

## EPIC 3B — Basic concept extraction (Phase 2) ⭐ moved early ✅ DONE

*Runs on the simple chunks from Epic 2 — no graph, no advanced ingestion yet.
Purpose: unlock the mastery differentiator ASAP and start collecting evidence.*

- [x] **SA-035** [BE+ML] `M` Lightweight LLM concept extraction over simple chunks → space concept set (`concepts.json`, flat list, no edges yet).
- [x] **SA-036** [BE] `S` Tag retrieved chunks with their concepts during chat; expose "concepts touched" per turn.
- [x] **SA-037** [BE] `S` Basic coverage: mark concepts encountered, compute space coverage %; simple concept list API.

> Also shipped (beyond ticket, BE-only tickets): a `progress.json` evidence store
> (coverage foundation for Epic 6–7) and a Dashboard tab surfacing coverage + the
> concept map with encountered badges.

---

## EPIC 4 — Knowledge Processing Pipeline (Phase 3)

*Formerly "Advanced Ingestion." Namespace `knowledge/`. Builds a knowledge
representation, not just an index.*

*Replaces SA-021 simple ingest. Each stage independently testable.*

- [x] **SA-040** [BE] `L` Stage 1 — structured extraction per format (PDF/DOCX/MD/TXT): headings, lists, tables, page numbers, paragraphs → `extracted.json`. *(Slice B; tables not yet)*
- [x] **SA-041** [BE] `M` Stage 2 — cleaning: repeated headers/footers, page numbers, whitespace, OCR artifacts, broken line-wrap. Meaning-preserving. *(Slice B)*
- [x] **SA-042** [BE] `M` Stage 3 — hierarchical chunking (heading→subheading→paragraph→sentence). *(Slice B)*
- [x] **SA-043** [BE] `S` Stage 4 — sliding-window overlap (configurable 15–25%). *(Slice B)*
- [x] **SA-044** [BE] `S` Stage 5 — metadata enrichment (heading path, page, chunk #, prev/next ids, timestamps). *(Slice B)*
- [ ] **SA-045** [BE+ML] `M` Stage 6 — LLM concept extraction per chunk (batched, cached by checksum, toggleable). *(Slice C)*
- [ ] **SA-046** [BE+ML] `M` Stage 7 — LLM chunk summarization (batched, cached, toggleable). *(Slice C)*
- [x] **SA-047** [BE] `S` Stage 8 — embeddings over final chunks (bge-small). *(via vectorstore rebuild)*
- [x] **SA-048** [BE] `S` Stage 9 — parent–child relationships (doc→section→chunk) persisted. *(Slice D; section_id/parent_id on chunks + sections.json)*
- [x] **SA-049** [BE] `M` Stage 10 — neighbor expansion at retrieval (include prev/next chunk). *(Slice D; configurable window, citations stay tied to hits)*
- [x] **SA-050** [BE] `S` Pipeline orchestrator: linear, resumable, per-stage logging + "fast ingest" mode (skip 6/7). *(Slice A)*
- [x] **SA-051** [BE] `S` Retrieval abstraction (Stage 11 hook) so BM25/rerank/hybrid can drop in later. Interface only. *(Slice A)*

### Production-grade enhancements (§5b) — all toggleable

- [x] **SA-052** [BE] `M` Multi-level chunking: emit large / medium / small reps with `level` metadata; index all levels. *(Slice B; word targets 350/180/80)*
- [x] **SA-053** [BE+ML] `M` Semantic boundary detection: cut where inter-sentence embedding similarity drops (fallback to fixed size). *(Slice B; opt-in via `chunk.semantic`)*
- [x] **SA-054** [BE] `S` Adaptive chunk size by document type (code→small, paper→medium, textbook→large), heuristic detection. *(Slice B)*
- [x] **SA-055** [BE+ML] `S` Keyword extraction per chunk (TF-IDF or KeyBERT) → metadata. *(Slice B; freq-based, dependency-light)*
- [ ] **SA-056** [BE+ML] `M` Named-entity extraction per chunk: algorithms, libraries, frameworks, companies, datasets, metrics, authors. *(Slice C)*
- [x] **SA-057** [BE] `M` Chunk quality score (0–100) from length/alpha/digit/non-ascii ratios. *(Slice B; auto-rebuild of low-quality chunks deferred)*
- [x] **SA-058** [BE] `S` Duplicate detection: if embedding similarity > 0.97 to an already-kept chunk, skip it at index time. *(Slice B)*

---

## EPIC 4B — Advanced retrieval pipeline (Phase 3)

*The §6 production retrieval flow. Each stage toggleable; degrades to plain
embed→FAISS if all are off.*

- [ ] **SA-110** [BE+ML] `M` Query expansion: synonyms + acronym expansion before retrieval (HNSW → "Hierarchical Navigable Small World", ANN, graph index). *(Slice E-llm)*
- [ ] **SA-111** [BE+ML] `M` Multi-query retrieval: generate sub-questions, retrieve each, merge + dedupe. *(Slice E-llm)*
- [x] **SA-112** [BE] `M` Merge + rerank across sub-queries and chunk levels. *(Slice E-det; diversity-by-section + score backfill)*
- [x] **SA-113** [BE] `M` Context compression: squeeze top-k context to a token budget before the LLM. *(Slice E-det; extractive/budget; LLM compression future)*
- [x] **SA-114** [BE] `S` Retrieval confidence: compute from avg similarity + #chunks above threshold; return `{confidence, reason, avg_similarity}`. *(Slice E-det)*
- [ ] **SA-115** [BE] `M` Retrieval orchestrator wiring the full §6 pipeline (expansion→multi-query→embed→FAISS→rerank→neighbor→compression→LLM→evidence). *(Slice E-llm)*
- [x] **SA-116** [FE] `S` Show retrieval confidence + grounding detail in the chat UI ("92% · 4 relevant chunks · avg sim 0.89"). *(Slice E-det)*

---

## EPIC 5 — Concept graph (Phase 4)

*Builds on the basic concepts from Epic 3B — adds canonicalization + prerequisite
graph over the (now richer) advanced chunks.*

- [ ] **SA-060** [BE+ML] `M` Canonicalize/dedup concepts across chunks (normalize + fuzzy match) into a clean concept set.
- [ ] **SA-061** [BE+ML] `M` Prerequisite edges: LLM pass to link concepts into a graph → `concepts.json`.
- [ ] **SA-062** [BE] `S` Concepts API: list concepts, get graph, get source chunks per concept.
- [ ] **SA-063** [BE] `S` Refine coverage from graph (supersedes SA-037 basic coverage).
- [ ] **SA-064** [FE] `S` (Optional MVP) simple concept list view with coverage badges. (Full graph viz is out of scope.)

---

## EPIC 6 — Assessment & evidence (Phase 5, event-driven)

- [ ] **SA-070** [BE+ML] `M` Question generator per concept: recall (explain), recognition (MCQ/T-F/matching), application (scenario).
- [ ] **SA-071** [BE+ML] `M` LLM-judge grader for free-text (recall/application) with explicit rubric in one file.
- [ ] **SA-072** [BE] `S` Recognition auto-grading (deterministic for MCQ/T-F/matching).
- [ ] **SA-073** [BE] `S` Confidence capture (1–5) attached to each answer event.
- [ ] **SA-074** [BE] `S` Evidence store: append events to `progress.json` per concept (recall/recognition/application/confidence).
- [ ] **SA-075** [BE] `S` Misconception flag when incorrect + high confidence.
- [ ] **SA-076** [FE] `M` Quiz UI: question card, answer input (free-text / MCQ), confidence slider, feedback + explanation.
- [ ] **SA-077** [BE] `S` Chat-as-evidence hook: optionally grade a chat answer and record it against a concept.

### Event-driven core (§7b)

- [ ] **SA-078** [BE] `M` Event store: append-only interaction events (question → retrieved concepts → answer → evaluation) to `events.json`. Mastery never mutated directly.
- [ ] **SA-079** [BE] `M` Mastery as a projection: recompute affected concepts from the event log (replayable when the formula changes).

---

## EPIC 7 — Mastery scoring & retention (Phase 5)

- [ ] **SA-080** [BE] `M` Mastery service: combine recall/recognition/application + confidence modifier → per-concept overall (isolated, unit-tested).
- [ ] **SA-081** [BE] `S` Retention model: last_reviewed, decay-based retention estimate, next_review date.
- [ ] **SA-082** [BE] `S` Bucketing: Mastered / Learning / Weak / Unknown thresholds.
- [ ] **SA-083** [BE] `S` Space-level rollup: overall mastery %, counts per bucket.
- [ ] **SA-084** [BE] `S` Rich per-concept record (§7b): mastery, evidence_count, last_correct, misconceptions, avg_confidence, avg_retrieval_confidence.

---

## EPIC 8 — Learning dashboard (Phase 5)

- [ ] **SA-090** [FE] `M` Dashboard: overall mastery, concept counts (mastered/learning/weak/unknown), per-concept scores.
- [ ] **SA-091** [FE] `S` Weak-concept surfacing: "next recommended study targets" list linking into quiz.
- [ ] **SA-092** [FE] `S` Concept detail: coverage/recall/recognition/application/confidence/retention breakdown (the HNSW example card).
- [ ] **SA-093** [FE] `S` Language check — copy says "mastered X of Y concepts", never "% of documents read".
- [ ] **SA-094** [FE] `S` Rich concept card (SA-084): evidence count, last correct, misconceptions, avg confidence, avg retrieval confidence.

---

## EPIC 9 — Setup, offline & polish (Phase 6)

- [ ] **SA-100** [INFRA] `M` One-command setup + clear "Ollama not found / model not pulled" guidance in UI.
- [ ] **SA-101** [INFRA] `S` Offline verification: no network calls after model pull (audit + note in README).
- [ ] **SA-102** [INFRA] `S` README quickstart validated on a clean machine (< 5 min).
- [ ] **SA-103** [INFRA] `S` Basic error handling + toasts across FE; backend structured logging.
- [ ] **SA-104** [INFRA] `S` Seed/demo space for first-run experience.

---

## EPIC P — Platform infrastructure (cross-cutting, §10)

*Conventions adopted early (prompt versioning is SA-009); the rest built alongside
the pipeline. Cheap early, expensive to retrofit.*

- [x] **SA-130** [BE] `M` Stage-level pipeline cache: each stage caches output keyed by (input hash + stage version + config); editing a doc re-runs only downstream stages. *(Slice A)*
- [x] **SA-131** [BE] `M` Configurable `pipeline.yaml`: orchestrator (SA-050) reads declared stages; toggle extraction/cleaning/chunking/concept/summary/embedding. *(Slice A)*
- [x] **SA-132** [BE] `M` Plugin `DocumentProcessor` interface with register-by-format; PDF/DOCX/MD/TXT ship; Arxiv/YouTube/HTML/GitHub drop in with no core changes. *(Slice A)*
- [~] **SA-133** [BE] `S` Observability: per-stage + per-retrieval timing/counts → structured logs + a per-run JSON metrics record. *(Slice A: per-stage timing/size/cache-hit in `stage_log` + logs; per-run JSON metrics file still TODO.)*

---

## EPIC R — Retrieval evaluation (MVP+, §11)

*Optional `evaluation/` package. Evaluates the retrieval system, not just the learner.*

- [ ] **SA-140** [BE] `M` Gold set format: (question → expected concepts) fixtures per space; small seed set.
- [ ] **SA-141** [BE] `M` Metrics: Recall@K, Precision@K, MRR, NDCG, concept coverage over retrieved chunks.
- [ ] **SA-142** [BE] `S` Eval CLI/report: run against fixtures, compare configs (e.g. multi-query on/off, semantic vs fixed chunking) → regression detection.

---

## EPIC I — Interview Readiness Mode (flagship stretch, §12)

*No architectural change — consumes the concept graph (Epic 5) + event store (SA-078).*

- [ ] **SA-150** [BE] `M` Topic → prerequisite walk over the concept graph; pull mastery evidence per concept.
- [ ] **SA-151** [BE] `M` Gap analysis: classify concepts strong / weak / missing for the topic.
- [ ] **SA-152** [BE+ML] `M` Adaptive interview generator targeting the gaps (reuses SA-070 question gen).
- [ ] **SA-153** [BE] `S` Score answers → emit events (SA-078) → update mastery; compute readiness %.
- [ ] **SA-154** [FE] `M` Interview Readiness view: overall %, strong areas ✓, needs-improvement ✗, start-interview flow.

---

## EPIC RM — Further platform (roadmap, §13)

- [ ] **SA-160** [BE] `L` Versioned learning spaces: snapshot on each material change; "how knowledge evolved" timeline. (Fits event-sourcing; deferred for storage/complexity.)
- [ ] **SA-161** [BE+ML] `M` Model benchmarking: same question through Qwen/Gemma/Mistral → LLM-judge → compare; pick default model.

---

## Explicitly OUT of scope (MVP)

Video/YouTube/website/paper ingestion · knowledge-graph visualization ·
adaptive quizzes · spaced repetition scheduler · personalized roadmap ·
multi-model (OpenAI/Anthropic/OpenRouter) · shared spaces · BM25 keyword index +
cross-encoder reranker.

*In scope but sequenced after the core:* retrieval evaluation (Epic R) ·
Interview Readiness (Epic I) · versioned spaces + model benchmarking (Epic RM).
Dense-side query expansion / multi-query *are* core (Epic 4B); full hybrid/BM25 is
stubbed via the Stage-11 interface.

---

## Suggested build order (critical path)

`SA-001→009` (skeleton + prompt-versioning convention) → `SA-010,012` (spaces) →
`SA-020,021,022` (upload+simple ingest) → `SA-030,031,033` (chat) → **usable app**
→ `SA-035…037` (basic concepts — differentiator online early) →
`SA-040…058` (knowledge pipeline) + `SA-130…133` (platform infra, alongside) →
`SA-110…116` (advanced retrieval) → `SA-060…064` (concept graph) →
`SA-070…079` (assessment + event store) → `SA-080…084` (mastery) →
`SA-090…094` (dashboard) → `SA-100…104` (polish) →
**then** `SA-140…142` (retrieval eval) → `SA-150…154` (Interview Readiness — flagship)
→ `SA-160,161` (roadmap).
