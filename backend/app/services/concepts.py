"""Concept extraction + concept set (SA-035, SA-045, SA-036, SA-037).

Extraction runs the LLM once **per section** (not per chunk): concepts belong to a
section's material, and a section maps to chunks at every level — so tagging by
section is both cheaper (no ×3 multi-level cost) and robust to which level was
retrieved. Still a flat set — the prerequisite graph is Epic 5.

``concepts.json`` shape::

    {
      "concepts": { concept_id: {id, label, source_sections: [...]} },
      "section_concepts": { section_id: [concept_id, ...] },
      "extracted_at": iso, "prompt_version": "concept_extraction_v1"
    }
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .. import storage
from ..models import Concept, CoverageStats
from ..prompts import load_prompt
from . import progress, vectorstore
from .ollama_client import OllamaClient
from .spaces import get_space

MAX_LABEL_LEN = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(space_id: str) -> Path:
    return storage.space_layout(space_id)["concepts"]


def load_concepts(space_id: str) -> dict:
    return storage.read_json(
        _path(space_id), default={"concepts": {}, "section_concepts": {}}
    )


def parse_concept_list(raw: str) -> list[str]:
    """Best-effort parse of an LLM response into a list of concept names."""
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end > start:
        try:
            arr = json.loads(raw[start : end + 1])
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except json.JSONDecodeError:
            pass
    out: list[str] = []
    for line in raw.replace(",", "\n").splitlines():
        item = line.strip().lstrip("-*•").strip().strip('"').strip()
        if item and len(item) <= MAX_LABEL_LEN:
            out.append(item)
    return out


def _canonical(label: str) -> tuple[str, str] | None:
    label = label.strip()[:MAX_LABEL_LEN].strip()
    try:
        return storage.slugify(label), label
    except ValueError:
        return None


async def extract_concepts(space_id: str) -> dict:
    """Run the LLM concept pass over each section and persist concepts.json.

    Returns ``{total_concepts, sources_processed, prompt_version}``. Raises
    ``OllamaUnavailable`` if the model can't be reached (state left untouched).
    """
    get_space(space_id)  # raises SpaceNotFound
    sections = vectorstore.load_all_sections(space_id)

    prompt = load_prompt("concept_extraction")
    client = OllamaClient()

    concepts: dict[str, dict] = {}
    section_concepts: dict[str, list[str]] = {}

    for section_id, sec in sections.items():
        raw = await client.generate(prompt.render(chunk=sec["text"]))
        ids_here: list[str] = []
        for name in parse_concept_list(raw):
            canon = _canonical(name)
            if canon is None:
                continue
            cid, clean = canon
            node = concepts.setdefault(
                cid, {"id": cid, "label": clean, "source_sections": []}
            )
            if section_id not in node["source_sections"]:
                node["source_sections"].append(section_id)
            if cid not in ids_here:
                ids_here.append(cid)
        section_concepts[section_id] = ids_here

    payload = {
        "concepts": concepts,
        "section_concepts": section_concepts,
        "extracted_at": _now(),
        "prompt_version": prompt.version,
    }
    storage.write_json(_path(space_id), payload)
    return {
        "total_concepts": len(concepts),
        "sources_processed": len(sections),
        "prompt_version": prompt.version,
    }


def concepts_for_chunks(space_id: str, chunk_ids: list[str]) -> list[dict]:
    """Concepts touched by retrieved chunks (SA-036), resolved via their section."""
    data = load_concepts(space_id)
    section_concepts = data.get("section_concepts", {})
    concepts = data.get("concepts", {})
    records = vectorstore.load_all_chunks(space_id)

    seen: list[str] = []
    for chunk_id in chunk_ids:
        section_id = records.get(chunk_id, {}).get("section_id")
        for cid in section_concepts.get(section_id, []):
            if cid not in seen:
                seen.append(cid)
    return [
        {"id": cid, "label": concepts[cid]["label"]} for cid in seen if cid in concepts
    ]


def list_concepts(space_id: str) -> list[Concept]:
    """All concepts in the space, joined with coverage from the progress store."""
    get_space(space_id)
    data = load_concepts(space_id)
    encountered = progress.encountered_ids(space_id)
    out = [
        Concept(
            id=c["id"],
            label=c["label"],
            source_chunk_count=len(c.get("source_sections", [])),
            encountered=c["id"] in encountered,
        )
        for c in data.get("concepts", {}).values()
    ]
    out.sort(key=lambda c: (not c.encountered, c.label.lower()))
    return out


def coverage(space_id: str) -> CoverageStats:
    """Coverage = fraction of the space's concepts the learner has encountered."""
    get_space(space_id)
    data = load_concepts(space_id)
    concept_ids = set(data.get("concepts", {}).keys())
    encountered = len(concept_ids & progress.encountered_ids(space_id))
    total = len(concept_ids)
    pct = round(100 * encountered / total, 1) if total else 0.0
    return CoverageStats(total=total, encountered=encountered, coverage_pct=pct)
