"""Simple sliding-window chunking (SA-021, v0).

Fixed word-count windows with configurable overlap. Deliberately basic — the
hierarchical/semantic/multi-level chunking (Epic 4) supersedes this later. Kept as
a pure function so it's trivially testable and swappable.
"""

from __future__ import annotations

DEFAULT_CHUNK_WORDS = 220


def chunk_segments(
    segments: list[dict],
    *,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    overlap: float = 0.2,
) -> list[dict]:
    """Turn extracted segments into overlapping chunks.

    Each returned chunk is ``{"text": str, "page": int | None}``. Overlap is a
    fraction in [0, 1); the window advances by ``chunk_words * (1 - overlap)``.
    """
    if not 0.0 <= overlap < 1.0:
        raise ValueError("overlap must be in [0.0, 1.0)")
    step = max(1, int(chunk_words * (1 - overlap)))

    chunks: list[dict] = []
    for segment in segments:
        words = segment["text"].split()
        if not words:
            continue
        start = 0
        while start < len(words):
            window = words[start : start + chunk_words]
            text = " ".join(window).strip()
            if text:
                chunks.append({"text": text, "page": segment.get("page")})
            if start + chunk_words >= len(words):
                break
            start += step
    return chunks
