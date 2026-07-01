"""Intelligent cleaning (SA-041).

Removes noise while preserving meaning:

* repeated running headers/footers (text that recurs across many pages),
* standalone page numbers ("12", "Page 12", "- 12 -"),
* excessive whitespace.

Operates on the block list from :mod:`.structure`. For single-page / page-less
documents (md, txt, docx) the header/footer pass is a no-op.
"""

from __future__ import annotations

import re
from collections import Counter

_PAGE_NUM_RE = re.compile(r"^\s*(page\s+)?[-–]?\s*\d+\s*[-–]?\s*$", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _is_page_number(text: str) -> bool:
    return bool(_PAGE_NUM_RE.match(text.strip()))


def _repeated_header_footer(blocks: list[dict]) -> set[str]:
    """Normalized texts that recur as the first/last block across multiple pages."""
    per_page: dict[int, list[dict]] = {}
    for b in blocks:
        if b["page"] is not None:
            per_page.setdefault(b["page"], []).append(b)
    if len(per_page) < 2:
        return set()

    edge_counts: Counter[str] = Counter()
    for page_blocks in per_page.values():
        edges = {page_blocks[0]["text"], page_blocks[-1]["text"]}
        for text in edges:
            edge_counts[_norm(text)] += 1

    threshold = max(2, int(0.4 * len(per_page)))
    return {text for text, n in edge_counts.items() if n >= threshold and text}


def clean_blocks(blocks: list[dict]) -> list[dict]:
    repeated = _repeated_header_footer(blocks)
    cleaned: list[dict] = []
    for b in blocks:
        text = _norm(b["text"])
        if not text:
            continue
        if _is_page_number(text):
            continue
        if _norm(text) in repeated:
            continue
        cleaned.append({**b, "text": text})
    return cleaned
