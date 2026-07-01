"""Per-chunk analysis: keyword extraction (SA-055) + quality scoring (SA-057).

Both are dependency-light heuristics (no LLM, no sklearn):

* keywords — stopword-filtered term frequency (a stand-in for TF-IDF/KeyBERT;
  enough to enable future hybrid search without a heavy dependency),
* quality — a 0–100 score penalizing too-short text, low alphabetic ratio (OCR
  garbage), digit-heavy, and non-ASCII-heavy chunks.
"""

from __future__ import annotations

import re
from collections import Counter

_WORD_RE = re.compile(r"[a-z][a-z0-9+\-]{2,}")

_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "are", "was", "which", "from",
    "have", "has", "not", "but", "can", "will", "would", "there", "their", "they",
    "them", "then", "than", "when", "what", "who", "how", "why", "where", "into",
    "such", "also", "more", "most", "some", "any", "all", "each", "other", "these",
    "those", "its", "our", "your", "his", "her", "one", "two", "use", "used", "using",
}


def extract_keywords(text: str, k: int = 6) -> list[str]:
    counts: Counter[str] = Counter()
    for match in _WORD_RE.finditer(text.lower()):
        word = match.group(0)
        if word not in _STOPWORDS:
            counts[word] += 1
    return [word for word, _ in counts.most_common(k)]


def quality_score(text: str) -> int:
    if not text:
        return 0
    n = len(text)
    score = 100
    if n < 40:
        score -= 40
    alpha_ratio = sum(c.isalpha() for c in text) / n
    if alpha_ratio < 0.5:
        score -= int((0.5 - alpha_ratio) * 100)
    if sum(c.isdigit() for c in text) / n > 0.3:
        score -= 20
    if sum(ord(c) > 127 for c in text) / n > 0.2:
        score -= 20
    return max(0, min(100, score))
