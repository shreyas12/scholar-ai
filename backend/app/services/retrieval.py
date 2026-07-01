"""Retrieval service (SA-030, SA-032).

Embeds a question, runs FAISS top-k over the space index, and assembles a grounded
context string plus structured citations. This is the seam where the advanced
retrieval pipeline (query expansion, multi-query, neighbor expansion, compression —
Epic 4B) will later slot in; for now it's a clean single-query retrieve.
"""

from __future__ import annotations

from typing import Protocol

from ..config import get_settings
from . import vectorstore

# Cosine similarity above which a retrieved chunk counts as "relevant" (SA-114).
RELEVANT_THRESHOLD = 0.5


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


def rerank(hits: list[dict], top_k: int) -> list[dict]:
    """Merge/rerank across levels (SA-112).

    Retrieval over multiple chunk levels tends to surface several chunks from the
    same section. Prefer *diversity*: take the best chunk per section first, then
    backfill by score if fewer than ``top_k`` distinct sections were found.
    """
    ordered = sorted(hits, key=lambda h: h.get("score", 0.0), reverse=True)
    out: list[dict] = []
    seen: set = set()
    for h in ordered:
        key = h.get("section_id") or h.get("chunk_id")
        if key not in seen:
            seen.add(key)
            out.append(h)
        if len(out) >= top_k:
            return out
    for h in ordered:  # backfill to reach top_k
        if h not in out:
            out.append(h)
            if len(out) >= top_k:
                break
    return out


def retrieve(space_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Top-k chunk records for the query (over-fetch → rerank by section)."""
    fetch = max(top_k, top_k * get_settings().retrieval_fetch_multiplier)
    raw = _default_retriever.retrieve(space_id, query, fetch)
    return rerank(raw, top_k)


def retrieval_confidence(hits: list[dict]) -> dict:
    """How well-grounded the answer is (SA-114): confidence %, reason, stats."""
    if not hits:
        return {
            "confidence": 0,
            "reason": "no relevant material found in this space",
            "avg_similarity": 0.0,
            "relevant_chunks": 0,
        }
    scores = [h.get("score", 0.0) for h in hits]
    top = scores[:3]
    avg = sum(top) / len(top)
    relevant = sum(1 for s in scores if s >= RELEVANT_THRESHOLD)
    # map avg cosine ~[0.3, 0.85] onto 0–100
    confidence = round(max(0.0, min(1.0, (avg - 0.3) / (0.85 - 0.3))) * 100)
    return {
        "confidence": confidence,
        "reason": f"retrieved {relevant} highly-relevant chunk(s); avg similarity {round(avg, 2)}",
        "avg_similarity": round(avg, 4),
        "relevant_chunks": relevant,
    }


def compress_context(hits: list[dict], budget_chars: int) -> list[dict]:
    """Squeeze context to a character budget before the LLM (SA-113).

    Deterministic extractive compression: include highest-priority hits until the
    budget is hit, truncating the final block. (LLM-based contextual compression
    is a future enhancement.)
    """
    out: list[dict] = []
    used = 0
    for h in hits:
        text = h["text"]
        if used + len(text) <= budget_chars:
            out.append(h)
            used += len(text)
        else:
            remaining = budget_chars - used
            if remaining > 200:
                out.append({**h, "text": text[:remaining].rstrip() + " …"})
            break
    return out


def expand_neighbors(space_id: str, hits: list[dict], window: int = 1) -> list[dict]:
    """Widen each hit with its prev/next chunks for context (SA-049).

    The hit's own metadata/score are preserved; only its ``text`` grows to include
    up to ``window`` neighbors on each side (same level, via prev/next links).
    Citations therefore stay tied to the actual hits, not the glue text.
    """
    if window <= 0:
        return hits
    records = vectorstore.load_all_chunks(space_id)

    def walk(rec: dict, link: str) -> list[str]:
        ids: list[str] = []
        cur = rec
        for _ in range(window):
            nxt = cur.get(link)
            if nxt and nxt in records:
                ids.append(nxt)
                cur = records[nxt]
            else:
                break
        return ids

    expanded: list[dict] = []
    for hit in hits:
        prev_ids = list(reversed(walk(hit, "prev_chunk_id")))
        next_ids = walk(hit, "next_chunk_id")
        texts = (
            [records[i]["text"] for i in prev_ids]
            + [hit["text"]]
            + [records[i]["text"] for i in next_ids]
        )
        expanded.append({**hit, "text": " ".join(texts), "neighbors": prev_ids + next_ids})
    return expanded


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
