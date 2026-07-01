"""Document management + simple ingest (SA-020, SA-021, SA-023, SA-024).

Handles upload → store (with checksum) → extract → chunk → persist per-document
chunks → rebuild the space FAISS index. Embedding happens inside the index
rebuild (see :mod:`.vectorstore`), so this module owns everything up to chunks.

Change detection (SA-024): re-uploading an identical file (same sha256) is a
no-op; a changed file re-ingests and rebuilds the index automatically.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .. import storage
from ..knowledge import pipeline
from ..knowledge.processors import UnsupportedFormat, supported_extensions
from ..models import Document
from . import vectorstore
from .spaces import SpaceNotFound, get_space


class DocumentNotFound(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _docs_dir(space_id: str) -> Path:
    return storage.space_layout(space_id)["documents"]


def _doc_dir(space_id: str, doc_id: str) -> Path:
    return _docs_dir(space_id) / doc_id


def _meta_path(space_id: str, doc_id: str) -> Path:
    return _doc_dir(space_id, doc_id) / "meta.json"


def _doc_id_for(space_id: str, name: str) -> str:
    """Stable id from the filename; a given filename maps to one document."""
    stem = Path(name).stem
    base = storage.slugify(stem) if _sluggable(stem) else "document"
    return base


def _sluggable(text: str) -> bool:
    try:
        storage.slugify(text)
        return True
    except ValueError:
        return False


def list_documents(space_id: str) -> list[Document]:
    get_space(space_id)  # raises SpaceNotFound
    docs_dir = _docs_dir(space_id)
    out: list[Document] = []
    if docs_dir.is_dir():
        for d in sorted(docs_dir.iterdir()):
            meta = storage.read_json(d / "meta.json")
            if meta:
                out.append(Document(**meta))
    out.sort(key=lambda x: x.uploaded_at, reverse=True)
    return out


def _build_chunks(space_id: str, doc_id: str, name: str, ext: str, checksum: str, path: Path) -> int:
    """Run the Knowledge Processing Pipeline and persist chunks.json. Returns count."""
    chunks, _log = pipeline.run_document(space_id, doc_id, name, ext, checksum, path)
    storage.write_json(_doc_dir(space_id, doc_id) / "chunks.json", chunks)
    return len(chunks)


def save_and_ingest(space_id: str, filename: str, content: bytes) -> Document:
    """Store an uploaded file and (re)ingest it. Idempotent on identical content."""
    get_space(space_id)  # raises SpaceNotFound

    ext = Path(filename).suffix.lower()
    if ext not in supported_extensions():
        raise UnsupportedFormat(f"Unsupported file type: {ext}")

    doc_id = _doc_id_for(space_id, filename)
    checksum = hashlib.sha256(content).hexdigest()

    existing = storage.read_json(_meta_path(space_id, doc_id))
    if existing and existing.get("checksum") == checksum:
        # SA-024: identical re-upload → no work.
        return Document(**existing, reused=True)

    doc_dir = storage.ensure_dir(_doc_dir(space_id, doc_id))
    original = doc_dir / f"original{ext}"
    original.write_bytes(content)

    meta = {
        "doc_id": doc_id,
        "name": filename,
        "ext": ext,
        "size": len(content),
        "checksum": checksum,
        "uploaded_at": _now(),
        "chunk_count": 0,
        "status": "processing",
    }
    storage.write_json(_meta_path(space_id, doc_id), meta)

    try:
        count = _build_chunks(space_id, doc_id, filename, ext, checksum, original)
        vectorstore.rebuild_index(space_id)  # SA-024: auto rebuild
        meta.update(chunk_count=count, status="ready")
    except Exception:
        meta["status"] = "error"
        storage.write_json(_meta_path(space_id, doc_id), meta)
        raise
    storage.write_json(_meta_path(space_id, doc_id), meta)
    return Document(**meta)


def delete_document(space_id: str, doc_id: str) -> None:
    """Remove a document and rebuild the index without it (SA-023)."""
    import shutil

    get_space(space_id)
    target = _doc_dir(space_id, doc_id)
    if not target.is_dir():
        raise DocumentNotFound(doc_id)
    # guard: stay inside the space's documents dir
    root = _docs_dir(space_id).resolve()
    if root not in target.resolve().parents:
        raise ValueError("Refusing to delete path outside documents root")
    shutil.rmtree(target)
    vectorstore.rebuild_index(space_id)


__all__ = [
    "Document",
    "DocumentNotFound",
    "SpaceNotFound",
    "list_documents",
    "save_and_ingest",
    "delete_document",
]
