"""Retrieval service (SA-030, SA-032).

Embeds a question, runs FAISS top-k over the space index, and assembles a grounded
context string plus structured citations. This is the seam where the advanced
retrieval pipeline (query expansion, multi-query, neighbor expansion, compression —
Epic 4B) will later slot in; for now it's a clean single-query retrieve.
"""

from __future__ import annotations

from typing import Protocol

from . import vectorstore


class Retriever(Protocol):
    """Retrieval strategy interface (SA-051, the Stage-11 hook).

    Alternative strategies (BM25, hybrid, reranked, multi-query) implement this
    and can be swapped in without touching callers or the ingestion pipeline.
    """

    def retrieve(self, space_id: str, query: str, top_k: int) -> list[dict]: ...


class DenseRetriever:
    """Default strategy: dense vector search over the space FAISS index."""

    def retrieve(self, space_id: str, query: str, top_k: int) -> list[dict]:
        return vectorstore.search(space_id, query, top_k=top_k)


_default_retriever: Retriever = DenseRetriever()


def retrieve(space_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Top-k chunk records for the query (each carries a ``score``)."""
    return _default_retriever.retrieve(space_id, query, top_k)


def _citation_label(rec: dict) -> str:
    doc = rec.get("document", "document")
    page = rec.get("page")
    section = rec.get("section_title")
    label = f"{doc}, p.{page}" if page else doc
    if section:
        label = f"{label} › {section}"
    return label


def build_context(hits: list[dict]) -> tuple[str, list[dict]]:
    """Turn retrieved chunks into (context_string, sources).

    The context string numbers each snippet with its citation so the model can
    reference sources; ``sources`` is the structured form for the UI (SA-032).
    """
    blocks: list[str] = []
    sources: list[dict] = []
    for i, rec in enumerate(hits, start=1):
        label = _citation_label(rec)
        blocks.append(f"[{i}] ({label})\n{rec['text']}")
        sources.append(
            {
                "index": i,
                "chunk_id": rec.get("chunk_id"),
                "document": rec.get("document"),
                "page": rec.get("page"),
                "section_title": rec.get("section_title"),
                "heading_path": rec.get("heading_path", []),
                "level": rec.get("level"),
                "score": round(rec.get("score", 0.0), 4),
            }
        )
    return "\n\n".join(blocks), sources
