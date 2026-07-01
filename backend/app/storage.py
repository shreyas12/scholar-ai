"""Filesystem storage layer (SA-004).

Everything ScholarAI stores lives under a single data root as plain files — no
database. This module owns:

* resolving the data root and per-space folder layout,
* safe (atomic + locked) JSON reads/writes,
* space-id slugification.

Layout::

    <data_dir>/
      spaces/
        <space_id>/
          space.json
          documents/<doc_id>/
          vectors/
          concepts.json
          progress.json
          events.json
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from filelock import FileLock

from .config import get_settings

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Turn a human space name into a filesystem-safe id.

    ``"Machine Learning"`` -> ``"machine-learning"``. Raises if nothing usable
    remains (e.g. an all-symbol name).
    """
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError(f"Cannot derive a valid id from name: {name!r}")
    return slug


# --- Path helpers ------------------------------------------------------------

def data_root() -> Path:
    return get_settings().data_dir


def spaces_dir() -> Path:
    return data_root() / "spaces"


def space_dir(space_id: str) -> Path:
    return spaces_dir() / space_id


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def space_layout(space_id: str) -> dict[str, Path]:
    """Canonical sub-paths for a space (does not create anything)."""
    root = space_dir(space_id)
    return {
        "root": root,
        "space_json": root / "space.json",
        "documents": root / "documents",
        "vectors": root / "vectors",
        "concepts": root / "concepts.json",
        "progress": root / "progress.json",
        "events": root / "events.json",
    }


def init_space_dirs(space_id: str) -> dict[str, Path]:
    """Create the folder skeleton for a space and return its layout."""
    layout = space_layout(space_id)
    ensure_dir(layout["root"])
    ensure_dir(layout["documents"])
    ensure_dir(layout["vectors"])
    return layout


# --- Safe JSON I/O -----------------------------------------------------------

def _lock_for(path: Path) -> FileLock:
    return FileLock(str(path) + ".lock")


def read_json(path: Path, default: Any = None) -> Any:
    """Read JSON, returning ``default`` if the file does not exist."""
    if not path.exists():
        return default
    with _lock_for(path):
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    """Atomically write JSON under a file lock.

    Writes to a temp file in the same directory then ``os.replace`` — so a
    crash mid-write never leaves a partial/corrupt file.
    """
    ensure_dir(path.parent)
    with _lock_for(path):
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append one record to a JSON-lines file (used later by the event store)."""
    ensure_dir(path.parent)
    with _lock_for(path):
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
