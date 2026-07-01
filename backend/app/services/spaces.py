"""Learning Spaces service (SA-010, SA-011).

A space is a single subject, isolated in its own folder under
``<data_dir>/spaces/<id>/``. This service owns the CRUD over those folders and the
`space.json` metadata file. Ids are stable slugs; renaming changes only the display
name (so vectors, documents and progress keep pointing at the same folder).
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone

from .. import storage
from ..models import Space


class SpaceNotFound(Exception):
    pass


class SpaceExists(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unique_id(name: str) -> str:
    """Slugify ``name`` and disambiguate against existing spaces (foo, foo-2…)."""
    base = storage.slugify(name)
    candidate = base
    n = 2
    existing = {s.id for s in list_spaces()}
    while candidate in existing:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _count_documents(space_id: str) -> int:
    docs = storage.space_layout(space_id)["documents"]
    if not docs.is_dir():
        return 0
    return sum(1 for p in docs.iterdir() if p.is_dir())


def _load(space_id: str) -> Space:
    layout = storage.space_layout(space_id)
    data = storage.read_json(layout["space_json"])
    if data is None:
        raise SpaceNotFound(space_id)
    return Space(**data, document_count=_count_documents(space_id))


def list_spaces() -> list[Space]:
    root = storage.spaces_dir()
    if not root.is_dir():
        return []
    spaces: list[Space] = []
    for child in sorted(root.iterdir()):
        meta = child / "space.json"
        if child.is_dir() and meta.exists():
            data = storage.read_json(meta)
            spaces.append(Space(**data, document_count=_count_documents(child.name)))
    # newest first
    spaces.sort(key=lambda s: s.created_at, reverse=True)
    return spaces


def get_space(space_id: str) -> Space:
    return _load(space_id)


def create_space(name: str) -> Space:
    space_id = _unique_id(name)
    layout = storage.init_space_dirs(space_id)
    now = _now()
    meta = {"id": space_id, "name": name.strip(), "created_at": now, "updated_at": now}
    storage.write_json(layout["space_json"], meta)
    return Space(**meta, document_count=0)


def rename_space(space_id: str, new_name: str) -> Space:
    layout = storage.space_layout(space_id)
    data = storage.read_json(layout["space_json"])
    if data is None:
        raise SpaceNotFound(space_id)
    data["name"] = new_name.strip()
    data["updated_at"] = _now()
    storage.write_json(layout["space_json"], data)
    return Space(**data, document_count=_count_documents(space_id))


def delete_space(space_id: str) -> None:
    """Remove the space folder (documents + FAISS index + metadata) entirely.

    Guarded: only deletes paths that resolve strictly inside the spaces root, so a
    crafted id can't escape and rmtree something else.
    """
    root = storage.spaces_dir().resolve()
    target = storage.space_dir(space_id).resolve()
    if root not in target.parents:
        raise ValueError(f"Refusing to delete path outside spaces root: {target}")
    if not target.is_dir():
        raise SpaceNotFound(space_id)
    shutil.rmtree(target)
