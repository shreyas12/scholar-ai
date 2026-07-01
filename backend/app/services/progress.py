"""Per-concept progress / evidence store (SA-037 foundation).

For Phase 2 this only records **coverage** — whether the learner has *encountered*
a concept (which is not the same as understanding it). It's deliberately the seam
where the richer, event-driven mastery evidence (recall/recognition/application,
Epic 6–7) will accumulate later. Kept separate from ``concepts.json`` (derived
structure) so re-extracting concepts never wipes learning evidence.

``progress.json`` shape:: ``{ concept_id: {concept_id, coverage, encounter_count,
first_encountered, last_encountered} }``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .. import storage


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(space_id: str) -> Path:
    return storage.space_layout(space_id)["progress"]


def load(space_id: str) -> dict[str, dict]:
    return storage.read_json(_path(space_id), default={})


def mark_encountered(space_id: str, concept_ids: list[str]) -> None:
    """Record coverage evidence for the given concepts (idempotent per call)."""
    if not concept_ids:
        return
    data = load(space_id)
    now = _now()
    for cid in concept_ids:
        entry = data.get(cid)
        if entry is None:
            data[cid] = {
                "concept_id": cid,
                "coverage": True,
                "encounter_count": 1,
                "first_encountered": now,
                "last_encountered": now,
            }
        else:
            entry["coverage"] = True
            entry["encounter_count"] = entry.get("encounter_count", 0) + 1
            entry["last_encountered"] = now
    storage.write_json(_path(space_id), data)


def encountered_ids(space_id: str) -> set[str]:
    return {cid for cid, e in load(space_id).items() if e.get("coverage")}
