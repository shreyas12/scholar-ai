"""Pipeline stages (Slice B).

The deterministic knowledge-processing pipeline:

* ``ExtractStage``  — format → structured blocks (headings/paragraphs/lists)
* ``CleanStage``    — strip repeated headers/footers, page numbers, whitespace
* ``SectionStage``  — group blocks into sections under their heading path
* ``ChunkStage``    — adaptive + multi-level (large/medium/small) sliding chunks
* ``EnrichStage``   — final chunk records: metadata, quality score, keywords

LLM stages (concept extraction, summarization) slot in after ``ChunkStage`` in
Slice C; semantic boundaries + dedup arrive in Slice B-embed.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..prompts import load_prompt
from . import analysis, chunkers, cleaning, processors, structure
from .pipeline import PipelineContext, Stage


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExtractStage(Stage):
    name = "extract"
    version = "2"
    output_key = "blocks"

    def run(self, ctx: PipelineContext) -> Any:
        return processors.get_processor(ctx.ext).extract(ctx.original_path)


class CleanStage(Stage):
    name = "clean"
    version = "2"
    output_key = "cleaned_blocks"

    def run(self, ctx: PipelineContext) -> Any:
        return cleaning.clean_blocks(ctx.artifacts["blocks"])


class SectionStage(Stage):
    name = "section"
    version = "1"
    output_key = "sections"

    def run(self, ctx: PipelineContext) -> Any:
        return structure.build_sections(ctx.artifacts["cleaned_blocks"])


class ChunkStage(Stage):
    name = "chunk"
    version = "2"
    output_key = "raw_chunks"

    def run(self, ctx: PipelineContext) -> Any:
        cfg = self.stage_config(ctx)
        levels = cfg.get("levels", chunkers.DEFAULT_LEVELS)
        overlap = cfg.get("overlap", get_settings().chunk_overlap)
        sections = ctx.artifacts["sections"]

        multiplier = 1.0
        if cfg.get("adaptive", True):
            full_text = " ".join(s["text"] for s in sections)
            doc_type, multiplier = chunkers.detect_doc_type(full_text)
            ctx.artifacts["doc_type"] = doc_type

        # Semantic boundaries (SA-053) are opt-in — they need embeddings and are
        # slower, so default ingest stays deterministic + offline-capable.
        embed_fn = None
        if cfg.get("semantic", False):
            from ..services.embeddings import get_embedding_service

            embed_fn = get_embedding_service().embed

        return chunkers.chunk_multi_level(
            sections, levels, overlap, multiplier, embed_fn=embed_fn
        )


class EnrichStage(Stage):
    name = "enrich"
    version = "1"
    output_key = "chunks"

    def run(self, ctx: PipelineContext) -> Any:
        raw = ctx.artifacts["raw_chunks"]
        now = _now()
        level_totals = Counter(c["level"] for c in raw)
        level_idx: dict[str, int] = {}

        records: list[dict] = []
        for c in raw:
            lv = c["level"]
            i = level_idx.get(lv, 0)
            level_idx[lv] = i + 1
            total = level_totals[lv]
            hp = c.get("heading_path") or []
            sec_idx = c.get("section_index")
            section_id = f"{ctx.doc_id}:sec:{sec_idx}" if sec_idx is not None else None
            records.append(
                {
                    "chunk_id": f"{ctx.doc_id}:{lv}:{i}",
                    "space": ctx.space_id,
                    "doc_id": ctx.doc_id,
                    "document": ctx.name,
                    # parent-child hierarchy (SA-048): doc -> section -> chunk
                    "section_id": section_id,
                    "parent_id": section_id,
                    "level": lv,
                    "chunk_number": i,
                    "total_chunks": total,
                    "page": c.get("page"),
                    "heading_path": hp,
                    "section_title": hp[-1] if hp else None,
                    "prev_chunk_id": f"{ctx.doc_id}:{lv}:{i - 1}" if i > 0 else None,
                    "next_chunk_id": f"{ctx.doc_id}:{lv}:{i + 1}" if i < total - 1 else None,
                    "quality": analysis.quality_score(c["text"]),
                    "keywords": analysis.extract_keywords(c["text"]),
                    "text": c["text"],
                    "created_at": now,
                }
            )
        return records


# --- LLM stages (Slice C) — toggleable, default OFF, medium-level only --------
# They mutate the enriched chunk records, so both output to "chunks".

class SummaryStage(Stage):
    """Stage 7 (SA-046): one-line LLM summary per medium chunk."""

    name = "summary"
    version = "1"
    output_key = "chunks"

    def run(self, ctx: PipelineContext) -> Any:
        from ..services.ollama_client import OllamaClient

        prompt = load_prompt("summarization")
        client = OllamaClient()
        for c in ctx.artifacts["chunks"]:
            if c.get("level") == "medium":
                c["summary"] = client.generate_sync(prompt.render(chunk=c["text"])).strip()
        return ctx.artifacts["chunks"]


class NerStage(Stage):
    """Stage (SA-056): named-entity extraction per medium chunk."""

    name = "ner"
    version = "1"
    output_key = "chunks"

    def run(self, ctx: PipelineContext) -> Any:
        from ..services.ollama_client import OllamaClient

        prompt = load_prompt("ner")
        client = OllamaClient()
        for c in ctx.artifacts["chunks"]:
            if c.get("level") == "medium":
                c["entities"] = _parse_entities(client.generate_sync(prompt.render(chunk=c["text"])))
        return ctx.artifacts["chunks"]


def _parse_entities(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            if isinstance(obj, dict):
                return {k: v for k, v in obj.items() if v}
        except json.JSONDecodeError:
            pass
    return {}
