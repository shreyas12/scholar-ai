"""Per-space FAISS vector store (SA-022).

One flat inner-product index per space (cosine similarity, since embeddings are
L2-normalized). Chunk records are the source of truth per document; the index is a
derived artifact that we rebuild wholesale whenever a document is added, changed or
removed (SA-023/024) — simple and correct for MVP data sizes.

Files under ``<space>/vectors/``:
* ``index.faiss`` — the FAISS index
* ``id_map.json`` — row number -> chunk_id (parallel to index rows)
"""

from __future__ import annotations

from pathlib import Path

from .. import storage
from .embeddings import get_embedding_service

# Chunks whose cosine similarity to an already-kept chunk exceeds this are treated
# as duplicates and skipped at index time (SA-058) — e.g. identical short sections
# emitted at multiple levels, or overlapping content across documents.
DEDUP_THRESHOLD = 0.97


def _index_path(space_id: str) -> Path:
    return storage.space_layout(space_id)["vectors"] / "index.faiss"


def _id_map_path(space_id: str) -> Path:
    return storage.space_layout(space_id)["vectors"] / "id_map.json"


def _doc_chunks_path(space_id: str, doc_id: str) -> Path:
    return storage.space_layout(space_id)["documents"] / doc_id / "chunks.json"


def load_all_chunks(space_id: str) -> dict[str, dict]:
    """chunk_id -> chunk record, across every document in the space."""
    docs_dir = storage.space_layout(space_id)["documents"]
    records: dict[str, dict] = {}
    if not docs_dir.is_dir():
        return records
    for doc_dir in sorted(docs_dir.iterdir()):
        chunks = storage.read_json(doc_dir / "chunks.json", default=[])
        for rec in chunks:
            records[rec["chunk_id"]] = rec
    return records


def load_all_sections(space_id: str) -> dict[str, dict]:
    """section_id -> section record (SA-048), across every document."""
    docs_dir = storage.space_layout(space_id)["documents"]
    sections: dict[str, dict] = {}
    if not docs_dir.is_dir():
        return sections
    for doc_dir in sorted(docs_dir.iterdir()):
        for sid, rec in storage.read_json(doc_dir / "sections.json", default={}).items():
            sections[sid] = rec
    return sections


def rebuild_index(space_id: str) -> int:
    """Rebuild the space index from all document chunks. Returns chunk count."""
    import faiss
    import numpy as np

    records = load_all_chunks(space_id)
    index_path = _index_path(space_id)
    id_map_path = _id_map_path(space_id)

    if not records:
        # No content left — drop stale index artifacts.
        for p in (index_path, id_map_path):
            if p.exists():
                p.unlink()
        return 0

    chunk_ids = list(records.keys())
    texts = [records[cid]["text"] for cid in chunk_ids]

    vectors = get_embedding_service().embed(texts)
    matrix = np.asarray(vectors, dtype="float32")

    keep = _dedupe_indices(matrix, DEDUP_THRESHOLD)
    kept_ids = [chunk_ids[i] for i in keep]
    kept_matrix = matrix[keep]

    index = faiss.IndexFlatIP(kept_matrix.shape[1])
    index.add(kept_matrix)

    storage.ensure_dir(index_path.parent)
    faiss.write_index(index, str(index_path))
    storage.write_json(id_map_path, kept_ids)
    return len(kept_ids)


def _dedupe_indices(matrix, threshold: float) -> list[int]:
    """Greedily keep rows, skipping any near-duplicate of an already-kept row.

    Vectors are L2-normalized, so an inner product > threshold ≈ cosine > threshold.
    Returns kept row indices in original order.
    """
    import numpy as np

    keep: list[int] = []
    kept_vecs = None
    for i in range(matrix.shape[0]):
        vec = matrix[i]
        if kept_vecs is not None:
            if float(np.max(kept_vecs @ vec)) > threshold:
                continue
        keep.append(i)
        kept_vecs = matrix[keep]
    return keep


def search(space_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Return the top-k chunk records for a query, each with a ``score`` field.

    Empty list if the space has no index yet.
    """
    import faiss
    import numpy as np

    index_path = _index_path(space_id)
    id_map = storage.read_json(_id_map_path(space_id), default=None)
    if not index_path.exists() or not id_map:
        return []

    index = faiss.read_index(str(index_path))
    records = load_all_chunks(space_id)

    qvec = np.asarray(get_embedding_service().embed([query]), dtype="float32")
    k = min(top_k, index.ntotal)
    scores, rows = index.search(qvec, k)

    results: list[dict] = []
    for score, row in zip(scores[0], rows[0]):
        if row < 0:
            continue
        chunk_id = id_map[row]
        rec = records.get(chunk_id)
        if rec:
            results.append({**rec, "score": float(score)})
    return results
