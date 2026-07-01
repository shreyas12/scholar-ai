# ScholarAI — Architecture & Plan

This document captures *how* we intend to build the MVP and the reasoning behind
the major decisions. Tickets live in [`TICKETS.md`](TICKETS.md).

---

## 1. Defining idea

ScholarAI does **not** measure activity ("you read 80% of the docs"). It measures
**demonstrated mastery** of the *concepts* inside a learning space:

> "We have strong evidence that you have mastered 47 of the 63 concepts in this space."

Every architectural choice should serve that goal. The concept graph and the
mastery signals are the product; RAG chat is the vehicle that generates evidence.

---

## 2. Design constraints

- **Local-first** — everything runs on the user's machine.
- **Offline after setup** — no network calls once the model is pulled.
- **Zero cost / no keys** — Ollama + local embeddings by default.
- **Filesystem storage** — no Postgres, no auth. One folder per space.
- **< 5 min setup** — clone, install Ollama, pull a model, run.

---

## 3. High-level architecture

```
┌────────────────────────────────────────────────────────┐
│  React + Tailwind + shadcn/ui  (Vite dev server)        │
│  Spaces · Documents · Chat · Dashboard                  │
└───────────────┬────────────────────────────────────────┘
                │ HTTP (localhost)
┌───────────────▼────────────────────────────────────────┐
│  FastAPI                                                │
│  ├── spaces        (CRUD over folders)                  │
│  ├── documents     (upload → ingest pipeline)           │
│  ├── chat          (RAG over FAISS + Ollama)            │
│  ├── concepts      (graph, extraction)                  │
│  ├── assessment    (quiz/recall/application generation) │
│  └── mastery       (scoring + dashboard aggregation)    │
├─────────────────────────────────────────────────────────┤
│  Services: Ingestion · Embeddings · LLM(Ollama) ·       │
│            VectorStore(FAISS) · Concepts · Mastery       │
└───────────────┬────────────────────────────────────────┘
                │ reads/writes
┌───────────────▼────────────────────────────────────────┐
│  Filesystem  ~/scholar-ai-data/spaces/<space>/          │
│    documents/  vectors/  metadata.json  progress.json   │
└─────────────────────────────────────────────────────────┘
```

External processes: **Ollama** (chat + concept/quiz LLM calls) and a local
**embedding model** loaded in-process (sentence-transformers / bge-small).

---

## 4. On-disk data model

```
spaces/
  machine-learning/
    space.json              # id, name, created, model config
    documents/
      <doc_id>/
        original.pdf        # raw uploaded file
        extracted.json      # structured text + structure metadata (Stage 1)
        chunks.json         # enriched chunks (Stages 3–7)
        checksum            # sha256 of original → change detection
    vectors/
      index.faiss           # FAISS index for the whole space
      id_map.json           # faiss_row -> chunk_id
    concepts.json           # concept nodes + prerequisite edges (graph)
    progress.json           # per-concept evidence + mastery signals
```

Rationale: a **single FAISS index per space** keeps retrieval simple and matches
the "isolated space" requirement. Chunk text/metadata live in JSON alongside;
FAISS stores only vectors + row→chunk_id mapping.

### Chunk record (Stage 5 metadata)

```json
{
  "chunk_id": "ml/doc123/0042",
  "space": "machine-learning",
  "document": "ann-indexes.pdf",
  "section_title": "HNSW",
  "heading_path": ["Vector Search", "ANN", "HNSW"],
  "page": 12,
  "chunk_number": 42,
  "total_chunks": 88,
  "prev_chunk_id": "ml/doc123/0041",
  "next_chunk_id": "ml/doc123/0043",
  "text": "...",
  "summary": "Introduces HNSW graph structure ...",
  "concepts": ["HNSW", "ANN", "Vector Search"],
  "created_at": "2026-07-01T10:00:00Z"
}
```

### Concept node & progress record

```json
// concepts.json
{ "id": "hnsw", "label": "HNSW",
  "prerequisites": ["vector-search", "ann"], "source_chunks": ["ml/doc123/0042"] }

// progress.json  (per concept)
{ "concept_id": "hnsw",
  "coverage": true,
  "signals": { "recall": [...events], "recognition": [...], "application": [...] },
  "confidence_events": [ {"correct": true, "confidence": 4, "ts": "..."} ],
  "last_reviewed": "2026-07-01T...",
  "retention_estimate": 0.75,
  "next_review": "2026-07-08T..." }
```

---

## 5. Ingestion pipeline (the 11 stages)

Implemented as a linear, resumable pipeline. Each stage is a pure-ish function
`(input, meta) -> output` so stages are independently testable and swappable.

1. **Extraction** — per-format extractors preserve structure (headings, lists,
   tables, page numbers, paragraph boundaries) → `extracted.json`.
2. **Cleaning** — strip repeated headers/footers, page numbers, OCR artifacts,
   fix broken line wraps. Never change meaning.
3. **Hierarchical chunking** — split by heading → subheading → paragraph →
   sentence (only if a section is too large). Keep sections intact.
4. **Sliding window** — overlap chunks (configurable 15–25%) to preserve context.
5. **Metadata enrichment** — attach the rich metadata above.
6. **Concept extraction** — LLM pass per chunk → concept list.
7. **Summarization** — LLM one-line summary per chunk.
8. **Embedding** — bge-small vector per chunk.
9. **Parent–child links** — document → section → chunk hierarchy retained.
10. **Neighbor expansion** — at *retrieval* time, optionally pull prev/next chunk.
11. **Hybrid retrieval (future)** — interface designed so BM25/rerank/etc. can be
    added without touching ingestion.

> **Cost note:** stages 6 & 7 are LLM calls per chunk and are the slow/expensive
> part. Make them batched, cached by chunk checksum, and toggleable (a "fast
> ingest" mode can skip them and backfill later).

**Change detection:** on re-upload, compare `sha256`. If changed → re-run the
pipeline for that document and rebuild the space index.

---

## 6. RAG chat flow

1. Embed the user question (bge-small).
2. FAISS top-k over the space index.
3. Neighbor expansion (Stage 10) → assemble context with citations.
4. Prompt Ollama: *answer only from provided context; cite doc + page.*
5. Stream answer to UI with source chips (doc name, page, heading path).
6. Chat turns can *optionally* be scored as recall/application evidence.

---

## 7. Mastery model

Each concept carries independent signals, combined into an overall score.

| Signal       | Source                              | Weight (initial) |
|--------------|-------------------------------------|------------------|
| Coverage     | concept encountered in space        | gate, not score  |
| Recall       | free explanation graded by LLM      | high             |
| Recognition  | MCQ / true-false / matching         | low              |
| Application  | scenario questions graded by LLM    | highest          |
| Confidence   | self-report 1–5 vs correctness      | modifier         |
| Retention    | decay since last correct recall     | modifier         |

**Confidence interpretation** (drives recommendations, not raw score):

- Correct + high confidence → strong mastery
- Correct + low confidence → reinforce
- Incorrect + high confidence → **misconception flag** (surface prominently)
- Incorrect + low confidence → expected beginner

**Overall mastery** = weighted blend of recall/recognition/application, modulated
by retention decay. Exact formula lives in the mastery service and is the one
place we tune — keep it isolated and unit-tested. Buckets for the dashboard:
Mastered / Learning / Weak / Unknown.

> Grading correctness of free-text answers is itself an LLM-judge call. Keep the
> rubric explicit and the judge prompt in one file so it can be calibrated.

---

## 8. Phasing (ship in thin vertical slices)

- **Phase 0 — Skeleton:** repo, backend/frontend scaffold, health check, storage
  layer, Ollama connectivity. *(Prove the plumbing.)*
- **Phase 1 — Spaces + Documents + basic chat:** the core loop with *simple*
  fixed chunking first, then swap in the real pipeline. Get end-to-end value.
- **Phase 2 — Advanced ingestion:** stages 1–10 properly.
- **Phase 3 — Concepts + graph:** extraction, concept graph, coverage.
- **Phase 4 — Assessment + mastery:** quiz/recall/application, confidence,
  scoring, retention.
- **Phase 5 — Dashboard:** concept-level mastery view, weak-concept surfacing.
- **Phase 6 — Polish:** offline check, one-command setup, docs.

Rationale: Phase 1 delivers a usable "chat with my notes" app quickly; the
mastery differentiator (Phases 3–5) is layered on the same evidence stream.

---

## 9. Key open decisions (resolve as we go)

1. **Embedding runtime** — sentence-transformers in-process vs Ollama embeddings.
   *Lean:* sentence-transformers (`bge-small`) for quality + control.
2. **Concept identity/dedup** — same concept phrased differently across chunks.
   Need canonicalization (LLM normalize + fuzzy match).
3. **Mastery formula** — start simple (evidence counts + recency), calibrate later.
4. **LLM-judge reliability** — free-text grading variance; may need few-shot rubric.
5. **Ingestion cost** — per-chunk LLM calls on `qwen3:8b` locally can be slow for
   big PDFs; need batching + a fast-ingest fallback.
