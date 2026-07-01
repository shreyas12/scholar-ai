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

## 5. Knowledge Processing Pipeline (the 11 stages)

> Formerly "Advanced Ingestion." Renamed because it does far more than ingest
> files — it parses, semantically chunks, extracts concepts, summarizes, enriches
> metadata, scores quality, and embeds. It builds a **knowledge representation**,
> not just an index. The code namespace is `knowledge/` (a.k.a. the Knowledge
> Ingestion Engine).

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

### 5b — Production-grade ingestion enhancements

Layered on top of the 11 canonical stages to make retrieval quality closer to a
real production system. All are **optional/toggleable** — the base pipeline works
without them.

- **Multi-level chunking** — emit three representations per section: large
  (~1200 tok), medium (~600 tok), small (~250 tok). Each chunk carries a `level`.
  Small chunks answer pin-point questions ("Explain HNSW"); large chunks answer
  synthesis questions ("evolution of ANN algorithms"). This is hierarchical
  retrieval — index all levels, let the retriever pick.
- **Semantic boundary detection** — instead of cutting at a fixed token count,
  embed paragraphs and cut where inter-paragraph similarity *drops*, so we never
  split in the middle of a coherent discussion. Falls back to fixed size.
- **Adaptive chunk size** — pick a base size by document type: code → small,
  research paper → medium, textbook → large. Detected heuristically.
- **Keyword extraction** — per chunk, store keywords (TF-IDF or KeyBERT) in
  metadata. Makes future hybrid (BM25 + dense) search trivial.
- **Named-entity extraction** — per chunk, pull algorithms, libraries, frameworks,
  companies, datasets, metrics, authors (e.g. HNSW, FAISS, NDCG, OpenAI). Sharper
  filtering and search.
- **Chunk quality scoring (0–100)** — score on length, structure, semantic
  cohesion, duplicate ratio, OCR quality; auto-rebuild low-quality chunks.
- **Duplicate detection** — before embedding, if a chunk's similarity to an
  existing one is > 0.97, reuse the existing chunk instead of re-indexing. Two
  overlapping PDFs shouldn't double the index.

**Change detection:** on re-upload, compare `sha256`. If changed → re-run the
pipeline for that document and rebuild the space index.

---

## 6. RAG chat flow (production retrieval pipeline)

Rather than `question → embed → FAISS → answer`, the retriever is a staged
pipeline where each stage is optional/toggleable:

```
Question
  ↓  Query expansion        (synonyms, acronym expansion: HNSW → "Hierarchical
  ↓                          Navigable Small World", "ANN", "graph index")
  ↓  Multi-query            (generate sub-questions, retrieve each)
  ↓  Embedding              (bge-small)
  ↓  FAISS retrieval        (top-k over the space index, across chunk levels)
  ↓  Merge + rerank         (dedupe across sub-queries, order by relevance)
  ↓  Neighbor expansion     (Stage 10: pull prev/next chunk)
  ↓  Context compression    (squeeze top-k to a token budget before the LLM)
  ↓  LLM (Ollama)           (answer only from context; cite doc + page)
  ↓  Grounded answer        (+ retrieval confidence, see below)
  ↓  Evidence collection    (emit an interaction event — see §7b)
```

- **Query expansion** improves recall for terse queries.
- **Multi-query retrieval**: "Explain Vector Search" → {what is vector search,
  how embeddings work, ANN algorithms, vector databases} → retrieve all, merge,
  rerank. Better coverage than a single query.
- **Context compression** keeps large learning spaces within the model's window.
- **Retrieval confidence** — surface *how well-grounded* the answer is, not just
  the answer:
  > Confidence 92% · retrieved 4 highly-relevant chunks · avg similarity 0.89

  Computed from average top-k similarity + count of chunks above a threshold.
  Shown in the UI so users know when to trust the answer.
- **Evidence collection** — every chat turn is emitted as an event and can be
  scored as recall/application evidence (see §7b), never silently mutating mastery.

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

## 7b. Event-driven mastery

Mastery is **never mutated directly**. Every interaction is appended as an
immutable **event**; mastery scores are a *projection* computed over the event log.

```
Question asked
  ↓  Retrieved concepts        (which concepts the retrieved chunks are tagged with)
  ↓  User answer
  ↓  Evaluation                (LLM-judge / deterministic grade + confidence)
  ↓  Event appended            (append-only log in progress.json / events.json)
  ↓  Concept mastery updated   (recompute projection for affected concepts)
```

Why event-sourced:

- **Auditable** — you can always show *why* a concept is at 82% (the evidence).
- **Recomputable** — tune the mastery formula and replay events; no lost history.
- **Retention-aware** — decay is a function of event timestamps, computed on read.

### Rich per-concept record (dashboard-facing)

Store more than a single number so the dashboard is genuinely informative:

```json
{
  "concept_id": "hnsw",
  "label": "HNSW",
  "mastery": 82,
  "evidence_count": 17,
  "last_correct": "2026-06-29T...",
  "misconceptions": 1,
  "avg_confidence": 4.2,
  "avg_retrieval_confidence": 0.91,
  "coverage": true,
  "retention_estimate": 0.75,
  "next_review": "2026-07-08T..."
}
```

---

## 8. Phasing (ship in thin vertical slices)

- **Phase 0 — Skeleton:** repo, backend/frontend scaffold, health check, storage
  layer, Ollama connectivity. *(Prove the plumbing.)*
- **Phase 1 — Spaces + Documents + basic chat:** the core loop with *simple*
  fixed chunking first. Get end-to-end value.
- **Phase 2 — Basic concept extraction:** lightweight LLM concept extraction over
  the simple chunks, tag retrieved chunks with concepts, start collecting evidence
  and coverage. *(Moved ahead of advanced ingestion — see rationale below.)*
- **Phase 3 — Knowledge Processing Pipeline + retrieval:** the 11 stages, the §5b
  enhancements, and the §6 production retrieval pipeline.
- **Phase 4 — Concept graph:** canonicalization/dedup + prerequisite edges.
- **Phase 5 — Assessment + mastery:** event-driven evidence, quiz/recall/
  application, confidence, scoring, retention.
- **Phase 6 — Dashboard:** concept-level mastery view, weak-concept surfacing.
- **Phase 7 — Polish:** offline check, one-command setup, docs.

**Cross-cutting (built alongside, not as a phase):** prompt versioning,
stage-level pipeline cache, configurable `pipeline.yaml`, plugin document
processors, and lightweight observability — see §10. These shape the code from
day one, so we adopt the *conventions* early even where the full feature lands later.

**Post-core, in priority order:** retrieval evaluation (§11) → Interview Readiness
mode (§12, the flagship) → versioned spaces + model benchmarking (§13).

**Rationale for moving concept extraction earlier:** concept extraction unlocks
the product's unique value — the moment you can tag retrieved chunks with concepts
you can start collecting evidence and building mastery scores, *while* the chunking
and retrieval pipeline keeps improving in later phases. It also de-risks the
differentiator early instead of gating it behind the whole ingestion rebuild.
Chunking quality and concept quality then improve independently.

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

---

## 10. Platform infrastructure (cross-cutting)

Foundational conventions adopted from day one — cheap to build in, expensive to
retrofit. These are what make it read as a *platform*, not a script.

- **Prompt versioning** — no hardcoded prompts. They live as files under
  `prompts/` (`chat_v1.md`, `concept_extraction_v1.md`, `grading_v1.md`,
  `summarization_v1.md`, `query_expansion_v1.md`). Every event/record stamps the
  **prompt version** it used, so when grading changes you can explain why scores
  moved. *(Adopt immediately — it's just a loader + a stamped field.)*
- **Stage-level pipeline cache** — beyond the whole-document checksum, each stage
  caches its own output keyed by (input hash + stage version + config). Editing a
  document re-runs only concept extraction, not extraction/cleaning/chunking.
  Turns a chunking tweak from "reprocess everything" into "reprocess one stage."
- **Configurable pipeline (`pipeline.yaml`)** — stages are declared in config, not
  wired in code. Users toggle extraction / cleaning / chunking / concept /
  summary / embedding on or off. The orchestrator (SA-050) reads this file.
- **Plugin document processors** — a `DocumentProcessor` interface with
  register-by-format. PDF/DOCX/MD/TXT ship; Arxiv/YouTube/HTML/GitHub drop in
  later with **no core changes**. This is how the roadmap ingestion sources land
  cleanly.
- **Observability** — every pipeline stage and retrieval step emits timing +
  counts (extraction 4s → 280 chunks → embedding 12s → LLM 81s → indexed).
  Persist a per-run metrics record. Lightweight now (structured logs + a JSON
  metrics file); a dashboard later.

## 11. Retrieval evaluation (MVP+)

We evaluate the *learner* — but not the *retrieval system*. An optional
`evaluation/` package closes that gap and is what production AI teams actually
monitor.

```
Question → Retrieved chunks → Expected concepts →
   Recall@K · Precision@K · MRR · NDCG · Coverage
```

Because chunks are already concept-tagged (Epic 3B), we can build a small
gold set of (question → expected concepts) and answer:

- Did semantic chunking improve NDCG?
- Does multi-query actually raise Recall@5?
- Did a chunking change *regress* retrieval?

Runs offline as a CLI/report against a fixture set; not in the request path.

## 12. Flagship: Interview Readiness Mode (post-core)

The feature that makes ScholarAI *memorable*. It requires **no architectural
change** — it's a new layer consuming the concept graph (§5/Epic 5) and the event
store (§7b).

Query: **"Can I pass an interview on Recommendation Systems?"** →

1. Walk the concept graph for the topic + its prerequisites.
2. Read mastery evidence per concept from the event store.
3. Identify weak / missing prerequisite concepts.
4. Generate an adaptive interview targeting the gaps.
5. Score answers (LLM-judge) → emit events → update mastery.
6. Report readiness:

```
Interview Readiness — Recommendation Systems      82%
Strong:  ✓ Embeddings  ✓ HNSW  ✓ ANN
Improve: ✗ Product Quantization  ✗ Counterfactual Eval  ✗ Online Learning
```

This is the narrative payoff: the concept graph + evidence store weren't
academic — they enable a genuinely useful, differentiated feature.

## 13. Further platform features (roadmap)

- **Versioned learning spaces** — snapshot the space on each material change
  ("v17: added Transformers.pdf → concepts updated → mastery recomputed"). Lets a
  learner see how their knowledge evolved. Natural fit with the event-sourced
  design; deferred for storage/complexity reasons.
- **Model benchmarking** — run the same question through Qwen / Gemma / Mistral,
  judge, and compare. Useful for research and for picking a default model. Builds
  on the LLM-judge already in the mastery layer.
