"""Chunking strategies (SA-043, SA-052, SA-054).

* Sliding-window over words within a section (overlap preserves context).
* Adaptive base size by detected document type (SA-054).
* Multi-level chunking (SA-052): each section is emitted at three sizes
  (large/medium/small) so retrieval can pick the right granularity — small chunks
  for pin-point questions, large chunks for synthesis.
"""

from __future__ import annotations

import re
from typing import Callable

DEFAULT_LEVELS = {"large": 350, "medium": 180, "small": 80}

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# doc-type -> size multiplier applied to the level targets (SA-054)
_TYPE_MULTIPLIER = {"code": 0.6, "paper": 1.0, "textbook": 1.3, "general": 1.0}

_CITATION_RE = re.compile(r"\[\d+\]")


def detect_doc_type(text: str) -> tuple[str, float]:
    """Heuristic (doc_type, size_multiplier) from a text sample."""
    sample = text[:5000]
    if not sample.strip():
        return "general", 1.0
    lower = sample.lower()

    symbol_ratio = sum(sample.count(c) for c in "{};=()") / max(1, len(sample))
    if "```" in sample or symbol_ratio > 0.03:
        return "code", _TYPE_MULTIPLIER["code"]
    if "abstract" in lower and (
        "references" in lower or "et al" in lower or _CITATION_RE.search(sample)
    ):
        return "paper", _TYPE_MULTIPLIER["paper"]
    if len(text) > 8000:
        return "textbook", _TYPE_MULTIPLIER["textbook"]
    return "general", _TYPE_MULTIPLIER["general"]


def sliding_windows(words: list[str], size: int, overlap: float) -> list[list[str]]:
    if not words:
        return []
    size = max(1, size)
    if len(words) <= size:
        return [words]
    step = max(1, int(size * (1 - overlap)))
    out: list[list[str]] = []
    start = 0
    while start < len(words):
        out.append(words[start : start + size])
        if start + size >= len(words):
            break
        start += step
    return out


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def semantic_windows(
    text: str,
    target_words: int,
    embed_fn: Callable[[list[str]], list[list[float]]],
    threshold: float = 0.5,
) -> list[list[str]]:
    """Split at *semantic* boundaries (SA-053).

    Embeds sentences and starts a new chunk when the similarity to the previous
    sentence drops below ``threshold`` — so a coherent discussion stays together —
    while still capping each chunk near ``target_words``.
    """
    sentences = split_sentences(text)
    if len(sentences) <= 1:
        words = text.split()
        return [words] if words else []

    vectors = embed_fn(sentences)
    chunks: list[list[str]] = []
    current: list[str] = []
    current_words = 0
    prev_vec: list[float] | None = None

    for sentence, vec in zip(sentences, vectors):
        w = len(sentence.split())
        drop = prev_vec is not None and _cosine(prev_vec, vec) < threshold
        if current and (current_words + w > target_words or drop):
            chunks.append(" ".join(current).split())
            current, current_words = [], 0
        current.append(sentence)
        current_words += w
        prev_vec = vec

    if current:
        chunks.append(" ".join(current).split())
    return chunks


def _cosine(a: list[float], b: list[float]) -> float:
    # embeddings are L2-normalized, so dot product is cosine similarity
    return sum(x * y for x, y in zip(a, b))


def chunk_multi_level(
    sections: list[dict],
    levels: dict[str, int],
    overlap: float,
    multiplier: float = 1.0,
    embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
) -> list[dict]:
    """Emit chunks for every (level, section). Grouped by level so per-level
    ordering (and later prev/next linking) is contiguous.

    When ``embed_fn`` is provided, boundaries are semantic (SA-053); otherwise a
    fixed sliding window is used.
    """
    chunks: list[dict] = []
    for level_name, base in levels.items():
        size = max(20, int(base * multiplier))
        for sec in sections:
            if embed_fn is not None:
                windows = semantic_windows(sec["text"], size, embed_fn)
            else:
                windows = sliding_windows(sec["text"].split(), size, overlap)
            for window in windows:
                text = " ".join(window).strip()
                if text:
                    chunks.append(
                        {
                            "text": text,
                            "page": sec.get("page"),
                            "heading_path": sec.get("heading_path", []),
                            "section_index": sec.get("section_index"),
                            "level": level_name,
                        }
                    )
    return chunks
