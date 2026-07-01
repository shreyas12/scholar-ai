"""Chat REST API (SA-031, SA-032, SA-034)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services import chat as svc
from ..services.spaces import SpaceNotFound

router = APIRouter(prefix="/api/spaces/{space_id}/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = None


@router.get("/history")
def history(space_id: str) -> list[dict]:
    try:
        return svc.load_history(space_id)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")


@router.post("")
async def ask(space_id: str, body: ChatRequest) -> StreamingResponse:
    try:
        svc.get_space(space_id)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")

    async def ndjson():
        async for event in svc.stream_answer(space_id, body.question, body.top_k):
            yield json.dumps(event) + "\n"

    return StreamingResponse(ndjson(), media_type="application/x-ndjson")
