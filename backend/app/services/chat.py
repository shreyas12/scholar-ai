"""Chat service (SA-031, SA-034).

Orchestrates one grounded turn: retrieve context, render the versioned chat prompt,
stream tokens from Ollama, then persist the turn to the space's chat history.

Emits a sequence of event dicts the router serializes as NDJSON:
* ``{"type": "sources", "sources": [...]}``  — sent first, before any token
* ``{"type": "token", "text": "..."}``       — repeated
* ``{"type": "done"}``                        — success
* ``{"type": "error", "message": "..."}``     — e.g. Ollama unavailable
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

from .. import storage
from ..config import get_settings
from ..prompts import load_prompt
from . import concepts as concepts_svc
from . import progress, retrieval
from .ollama_client import OllamaClient, OllamaUnavailable
from .spaces import get_space


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _history_path(space_id: str) -> Path:
    return storage.space_layout(space_id)["root"] / "chat.json"


def load_history(space_id: str) -> list[dict]:
    get_space(space_id)  # raises SpaceNotFound
    return storage.read_json(_history_path(space_id), default=[])


def _append(space_id: str, message: dict) -> None:
    history = storage.read_json(_history_path(space_id), default=[])
    history.append(message)
    storage.write_json(_history_path(space_id), history)


async def stream_answer(
    space_id: str, question: str, top_k: int | None = None
) -> AsyncIterator[dict]:
    get_space(space_id)  # raises SpaceNotFound
    settings = get_settings()
    k = top_k or settings.top_k

    hits = retrieval.retrieve(space_id, question, top_k=k)

    # SA-036: tag the *actual* hits with concepts (before neighbor glue is added).
    touched = concepts_svc.concepts_for_chunks(space_id, [h["chunk_id"] for h in hits])

    # SA-049: widen each hit with neighboring chunks for context. Citations stay
    # tied to the hits themselves.
    context_hits = retrieval.expand_neighbors(space_id, hits, settings.retrieval_neighbors)
    context, sources = retrieval.build_context(context_hits)
    yield {"type": "sources", "sources": sources}

    # We only record coverage *after* a successful turn (below), so a failed
    # generation doesn't inflate coverage. No-op until concepts are extracted.
    if touched:
        yield {"type": "concepts", "concepts": touched}

    prompt = load_prompt("chat")
    rendered = prompt.render(context=context or "(no relevant material found)", question=question)

    client = OllamaClient()
    parts: list[str] = []
    try:
        async for delta in client.generate_stream(rendered):
            parts.append(delta)
            yield {"type": "token", "text": delta}
    except OllamaUnavailable as exc:
        yield {"type": "error", "message": str(exc)}
        return

    answer = "".join(parts)
    # SA-037: coverage evidence is recorded only now, on a completed turn.
    if touched:
        progress.mark_encountered(space_id, [c["id"] for c in touched])
    # Persist the turn (SA-034). Assistant message records the prompt version it
    # was generated with (SA-009) so future prompt changes are auditable.
    _append(space_id, {"role": "user", "content": question, "ts": _now()})
    _append(
        space_id,
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "concepts": touched,
            "prompt_version": prompt.version,
            "ts": _now(),
        },
    )
    yield {"type": "done"}
