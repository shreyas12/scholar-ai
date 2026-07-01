"""Chunking strategies (SA-043, SA-052, SA-054).

* Sliding-window over words within a section (overlap preserves context).
* Adaptive base size by detected document type (SA-054).
* Multi-level chunking (SA-052): each section is emitted at three sizes
  (large/medium/small) so retrieval can pick the right granularity — small chunks
  for pin-point questions, large chunks for synthesis.
"""

from __future__ import annotations

import re

DEFAULT_LEVELS = {"large": 350, "medium": 180, "small": 80}

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


def chunk_multi_level(
    sections: list[dict],
    levels: dict[str, int],
    overlap: float,
    multiplier: float = 1.0,
) -> list[dict]:
    """Emit chunks for every (level, section). Grouped by level so per-level
    ordering (and later prev/next linking) is contiguous."""
    chunks: list[dict] = []
    for level_name, base in levels.items():
        size = max(20, int(base * multiplier))
        for sec in sections:
            for window in sliding_windows(sec["text"].split(), size, overlap):
                text = " ".join(window).strip()
                if text:
                    chunks.append(
                        {
                            "text": text,
                            "page": sec.get("page"),
                            "heading_path": sec.get("heading_path", []),
                            "level": level_name,
                        }
                    )
    return chunks
