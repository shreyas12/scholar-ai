"""Basic concept extraction + concept set (SA-035, SA-036, SA-037).

A lightweight LLM pass over the *simple* chunks (Epic 2) that yields a flat set of
concepts per space — no prerequisite graph yet (that's Epic 5). This is what turns
ScholarAI from "chat over notes" into a mastery tracker: once chunks are tagged
with concepts, chat turns can mark concepts *encountered* (coverage) and, later,
accumulate real evidence.

``concepts.json`` shape::

    {
      "concepts": { concept_id: {id, label, source_chunks: [...]} },
      "chunk_concepts": { chunk_id: [concept_id, ...] },
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
        _path(space_id), default={"concepts": {}, "chunk_concepts": {}}
    )


def parse_concept_list(raw: str) -> list[str]:
    """Best-effort parse of an LLM response into a list of concept names.

    Handles a clean JSON array, an array embedded in prose, or a newline/comma
    fallback — small models don't always obey "JSON only".
    """
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end > start:
        try:
            arr = json.loads(raw[start : end + 1])
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except json.JSONDecodeError:
            pass
    # fallback: split lines, strip bullets/quotes
    out: list[str] = []
    for line in raw.replace(",", "\n").splitlines():
        item = line.strip().lstrip("-*•").strip().strip('"').strip()
        if item and len(item) <= MAX_LABEL_LEN:
            out.append(item)
    return out


def _canonical(label: str) -> tuple[str, str] | None:
    """(concept_id, clean_label) or None if the label isn't sluggable."""
    label = label.strip()[:MAX_LABEL_LEN].strip()
    try:
        return storage.slugify(label), label
    except ValueError:
        return None


async def extract_concepts(space_id: str, max_chunks: int | None = None) -> dict:
    """Run the LLM concept pass over the space's chunks and persist concepts.json.

    Returns ``{total_concepts, chunks_processed, prompt_version}``. Raises
    ``OllamaUnavailable`` if the model can't be reached (state is left untouched).
    """
    get_space(space_id)  # raises SpaceNotFound
    records = vectorstore.load_all_chunks(space_id)
    chunk_items = list(records.items())
    if max_chunks is not None:
        chunk_items = chunk_items[:max_chunks]

    prompt = load_prompt("concept_extraction")
    client = OllamaClient()

    concepts: dict[str, dict] = {}
    chunk_concepts: dict[str, list[str]] = {}

    for chunk_id, rec in chunk_items:
        raw = await client.generate(prompt.render(chunk=rec["text"]))
        ids_here: list[str] = []
        for name in parse_concept_list(raw):
            canon = _canonical(name)
            if canon is None:
                continue
            cid, clean = canon
            node = concepts.setdefault(
                cid, {"id": cid, "label": clean, "source_chunks": []}
            )
            if chunk_id not in node["source_chunks"]:
                node["source_chunks"].append(chunk_id)
            if cid not in ids_here:
                ids_here.append(cid)
        chunk_concepts[chunk_id] = ids_here

    payload = {
        "concepts": concepts,
        "chunk_concepts": chunk_concepts,
        "extracted_at": _now(),
        "prompt_version": prompt.version,
    }
    storage.write_json(_path(space_id), payload)
    return {
        "total_concepts": len(concepts),
        "chunks_processed": len(chunk_items),
        "prompt_version": prompt.version,
    }


def concepts_for_chunks(space_id: str, chunk_ids: list[str]) -> list[dict]:
    """The concept records touched by a set of retrieved chunks (SA-036)."""
    data = load_concepts(space_id)
    chunk_concepts = data.get("chunk_concepts", {})
    concepts = data.get("concepts", {})
    seen: list[str] = []
    for chunk_id in chunk_ids:
        for cid in chunk_concepts.get(chunk_id, []):
            if cid not in seen:
                seen.append(cid)
    return [
        {"id": cid, "label": concepts[cid]["label"]}
        for cid in seen
        if cid in concepts
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
            source_chunk_count=len(c.get("source_chunks", [])),
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
