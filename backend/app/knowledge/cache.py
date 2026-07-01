"""Stage-level pipeline cache (SA-130).

Each stage's output is cached under the document, keyed by a signature that folds
in the document checksum, the chain of upstream stage names+versions, and the
stage config. Consequences:

* Re-ingesting identical content → every stage is a cache hit (fast).
* Bumping one stage's version (or its config) → that stage's key changes, and
  because the key includes the *upstream chain*, every downstream stage re-runs
  too — exactly the invalidation you want.

Cache lives at ``<doc>/.cache/<stage>.json`` as ``{"key": ..., "artifact": ...}``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .. import storage


def _cache_dir(space_id: str, doc_id: str) -> Path:
    return storage.space_layout(space_id)["documents"] / doc_id / ".cache"


def compute_key(checksum: str, chain_signature: str, config: dict) -> str:
    payload = json.dumps(
        {"checksum": checksum, "chain": chain_signature, "config": config},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def get(space_id: str, doc_id: str, stage_name: str, key: str) -> Any | None:
    path = _cache_dir(space_id, doc_id) / f"{stage_name}.json"
    entry = storage.read_json(path)
    if entry and entry.get("key") == key:
        return entry.get("artifact")
    return None


def put(space_id: str, doc_id: str, stage_name: str, key: str, artifact: Any) -> None:
    path = _cache_dir(space_id, doc_id) / f"{stage_name}.json"
    storage.write_json(path, {"key": key, "artifact": artifact})
