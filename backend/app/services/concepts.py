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
from ..models import (
    Concept,
    ConceptDetail,
    ConceptGraph,
    CoverageStats,
    GraphEdge,
    GraphNode,
)
from ..prompts import load_prompt
from . import progress, vectorstore
from .embeddings import get_embedding_service
from .ollama_client import OllamaClient, OllamaUnavailable
from .spaces import SpaceNotFound, get_space

MAX_LABEL_LEN = 60
# Cosine similarity above which two concept labels are treated as the same
# concept and merged (SA-060). Empirically, label variants ("HNSW" vs "HNSW
# algorithm") sit at ~0.83–0.89 while distinct concepts sit at ~0.5, so 0.80
# separates them with margin.
CANON_THRESHOLD = 0.80


class ConceptNotFound(Exception):
    pass


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


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # normalized embeddings → dot = cosine


def canonicalize_concepts(
    concepts: dict[str, dict], section_concepts: dict[str, list[str]]
) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """Merge near-duplicate concepts by label embedding similarity (SA-060).

    "HNSW" / "HNSW algorithm" / "hnsw index" collapse to one node; the
    section→concept map is remapped to the surviving ids.
    """
    items = list(concepts.items())
    if len(items) <= 1:
        return concepts, section_concepts

    vectors = get_embedding_service().embed([node["label"] for _, node in items])
    reps: list[tuple[str, list[float]]] = []  # (canonical_id, vector)
    remap: dict[str, str] = {}
    merged: dict[str, dict] = {}

    for (cid, node), vec in zip(items, vectors):
        match = next((rcid for rcid, rvec in reps if _cosine(vec, rvec) > CANON_THRESHOLD), None)
        if match is not None:
            remap[cid] = match
            for s in node.get("source_sections", []):
                if s not in merged[match]["source_sections"]:
                    merged[match]["source_sections"].append(s)
        else:
            reps.append((cid, vec))
            merged[cid] = {**node, "source_sections": list(node.get("source_sections", []))}
            remap[cid] = cid

    new_section_concepts: dict[str, list[str]] = {}
    for sid, cids in section_concepts.items():
        seen: list[str] = []
        for c in cids:
            nc = remap.get(c, c)
            if nc in merged and nc not in seen:
                seen.append(nc)
        new_section_concepts[sid] = seen
    return merged, new_section_concepts


def _parse_prereq(raw: str) -> list[dict]:
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end > start:
        try:
            arr = json.loads(raw[start : end + 1])
            if isinstance(arr, list):
                return [x for x in arr if isinstance(x, dict) and "concept" in x]
        except json.JSONDecodeError:
            pass
    return []


async def infer_prerequisites(concepts: dict[str, dict], client: OllamaClient) -> None:
    """LLM pass to attach ``prerequisites`` (concept ids) to each node (SA-061)."""
    if len(concepts) < 2:
        return
    prompt = load_prompt("prereq")
    label_to_id = {node["label"].lower(): cid for cid, node in concepts.items()}
    listing = "\n".join(f"- {node['label']}" for node in concepts.values())
    raw = await client.generate(prompt.render(concepts=listing))

    for edge in _parse_prereq(raw):
        cid = label_to_id.get(str(edge["concept"]).lower())
        if not cid:
            continue
        prereqs: list[str] = []
        for p in edge.get("prerequisites", []):
            pid = label_to_id.get(str(p).lower())
            if pid and pid != cid and pid not in prereqs:
                prereqs.append(pid)
        if prereqs:
            concepts[cid]["prerequisites"] = prereqs


async def extract_concepts(space_id: str) -> dict:
    """Extract concepts per section, canonicalize, and infer the prerequisite graph.

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

    # SA-060 canonicalize (offline), then SA-061 prerequisite graph (LLM).
    concepts, section_concepts = canonicalize_concepts(concepts, section_concepts)
    await infer_prerequisites(concepts, client)

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
    """Coverage = fraction of the (canonical) concepts the learner has encountered."""
    get_space(space_id)
    data = load_concepts(space_id)
    concept_ids = set(data.get("concepts", {}).keys())
    encountered = len(concept_ids & progress.encountered_ids(space_id))
    total = len(concept_ids)
    pct = round(100 * encountered / total, 1) if total else 0.0
    return CoverageStats(total=total, encountered=encountered, coverage_pct=pct)


def get_graph(space_id: str) -> ConceptGraph:
    """Concept graph (SA-062): nodes with coverage/ready state + prerequisite edges."""
    get_space(space_id)
    data = load_concepts(space_id)
    concepts = data.get("concepts", {})
    encountered = progress.encountered_ids(space_id)

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for cid, node in concepts.items():
        prereqs = node.get("prerequisites", [])
        # SA-063: "ready to learn" = not yet encountered but all prereqs are.
        ready = cid not in encountered and bool(prereqs) and all(
            p in encountered for p in prereqs
        )
        nodes.append(
            GraphNode(id=cid, label=node["label"], encountered=cid in encountered, ready=ready)
        )
        for pid in prereqs:
            if pid in concepts:
                edges.append(GraphEdge(source=pid, target=cid))
    return ConceptGraph(nodes=nodes, edges=edges)


def get_concept_detail(space_id: str, concept_id: str) -> ConceptDetail:
    get_space(space_id)
    data = load_concepts(space_id)
    concepts = data.get("concepts", {})
    node = concepts.get(concept_id)
    if node is None:
        raise ConceptNotFound(concept_id)
    prereq_labels = [
        concepts[p]["label"] for p in node.get("prerequisites", []) if p in concepts
    ]
    return ConceptDetail(
        id=node["id"],
        label=node["label"],
        encountered=concept_id in progress.encountered_ids(space_id),
        prerequisites=prereq_labels,
        source_sections=node.get("source_sections", []),
    )
