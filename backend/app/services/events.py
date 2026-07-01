"""Append-only interaction event log (SA-078).

Every graded interaction — a quiz answer, or a chat answer promoted to evidence —
is written here as an **immutable** record. Mastery is *never* stored; it is a
projection recomputed from this log (see :mod:`app.services.mastery`), so tuning
the mastery formula and replaying history never loses evidence (SA-079).

Stored as JSON-lines at ``events.json`` (one event per line, append-only) so a
crash mid-write can at worst drop the last line, never corrupt earlier history.

Event record::

    {
      "event_id": "a1b2c3d4e5f6",
      "ts": "2026-07-01T...",
      "concept_id": "hnsw",
      "type": "recall" | "recognition" | "application",
      "source": "quiz" | "chat",
      "question": "...",
      "answer": "...",
      "correct": true,
      "score": 85,                    # 0-100
      "confidence": 4,                # self-report 1-5
      "misconception": "..." | null,  # the specific wrong belief, if any
      "misconception_flag": false,    # incorrect AND high confidence (SA-075)
      "retrieval_confidence": 0.91 | null,
      "prompt_version": "grading_v1" | "deterministic"
    }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from .. import storage

# Self-reported confidence at/above which a wrong answer is a *misconception*
# rather than an expected beginner miss (PLAN §7).
HIGH_CONFIDENCE = 4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(space_id: str) -> Path:
    return storage.space_layout(space_id)["events"]


def append(
    space_id: str,
    *,
    concept_id: str,
    type: str,
    source: str,
    question: str,
    answer: str,
    correct: bool,
    score: int,
    confidence: int,
    misconception: str | None = None,
    retrieval_confidence: float | None = None,
    prompt_version: str = "deterministic",
) -> dict:
    """Append one graded interaction to the event log and return the record."""
    record = {
        "event_id": uuid.uuid4().hex[:12],
        "ts": _now(),
        "concept_id": concept_id,
        "type": type,
        "source": source,
        "question": question,
        "answer": answer,
        "correct": correct,
        "score": score,
        "confidence": confidence,
        "misconception": misconception,
        # SA-075: a wrong answer held with high confidence is a misconception to
        # surface prominently, not an expected beginner miss.
        "misconception_flag": (not correct) and confidence >= HIGH_CONFIDENCE,
        "retrieval_confidence": retrieval_confidence,
        "prompt_version": prompt_version,
    }
    storage.append_jsonl(_path(space_id), record)
    return record


def load(space_id: str) -> list[dict]:
    """All events for a space, in append order. Empty if none recorded yet."""
    path = _path(space_id)
    if not path.exists():
        return []
    import json

    with storage._lock_for(path):  # reuse the same lock as append (SA-004)
        lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # A torn final line (crash mid-append) is skipped, not fatal.
            continue
    return out


def load_for_concept(space_id: str, concept_id: str) -> list[dict]:
    return [e for e in load(space_id) if e.get("concept_id") == concept_id]
