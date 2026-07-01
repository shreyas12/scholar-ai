"""Pipeline stages (Slice A).

These wrap the *existing* simple-ingest behavior in the staged shape:

* ``ExtractStage``  — format → text segments (via the processor registry)
* ``CleanStage``    — passthrough for now (Stage 2 cleaning arrives in Slice B)
* ``ChunkStage``    — sliding-window chunks + full chunk-record metadata

Later slices replace/extend these without changing the orchestrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..services import chunking
from . import processors
from .pipeline import PipelineContext, Stage


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExtractStage(Stage):
    name = "extract"
    version = "1"
    output_key = "segments"

    def run(self, ctx: PipelineContext) -> Any:
        return processors.get_processor(ctx.ext).extract(ctx.original_path)


class CleanStage(Stage):
    name = "clean"
    version = "1"
    output_key = "cleaned"

    def run(self, ctx: PipelineContext) -> Any:
        # Slice A: no-op cleaning — preserve segments verbatim.
        return ctx.artifacts["segments"]


class ChunkStage(Stage):
    name = "chunk"
    version = "1"
    output_key = "chunks"

    def run(self, ctx: PipelineContext) -> Any:
        cfg = self.stage_config(ctx)
        chunk_words = cfg.get("chunk_words", chunking.DEFAULT_CHUNK_WORDS)
        overlap = get_settings().chunk_overlap

        segments = ctx.artifacts["cleaned"]
        raw = chunking.chunk_segments(segments, chunk_words=chunk_words, overlap=overlap)

        total = len(raw)
        now = _now()
        records: list[dict] = []
        for i, ch in enumerate(raw):
            records.append(
                {
                    "chunk_id": f"{ctx.doc_id}:{i}",
                    "space": ctx.space_id,
                    "doc_id": ctx.doc_id,
                    "document": ctx.name,
                    "chunk_number": i,
                    "total_chunks": total,
                    "page": ch.get("page"),
                    "prev_chunk_id": f"{ctx.doc_id}:{i - 1}" if i > 0 else None,
                    "next_chunk_id": f"{ctx.doc_id}:{i + 1}" if i < total - 1 else None,
                    "text": ch["text"],
                    "created_at": now,
                }
            )
        return records
