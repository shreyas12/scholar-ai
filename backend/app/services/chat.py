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
from . import retrieval
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
    context, sources = retrieval.build_context(hits)
    yield {"type": "sources", "sources": sources}

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
    # Persist the turn (SA-034). Assistant message records the prompt version it
    # was generated with (SA-009) so future prompt changes are auditable.
    _append(space_id, {"role": "user", "content": question, "ts": _now()})
    _append(
        space_id,
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "prompt_version": prompt.version,
            "ts": _now(),
        },
    )
    yield {"type": "done"}
