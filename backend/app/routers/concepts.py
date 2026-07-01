"""Concepts + coverage REST API (SA-035, SA-037)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import Concept, CoverageStats, ExtractResult
from ..services import concepts as svc
from ..services.ollama_client import OllamaUnavailable
from ..services.spaces import SpaceNotFound

router = APIRouter(prefix="/api/spaces/{space_id}/concepts", tags=["concepts"])


@router.get("", response_model=list[Concept])
def list_concepts(space_id: str) -> list[Concept]:
    try:
        return svc.list_concepts(space_id)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")


@router.get("/coverage", response_model=CoverageStats)
def coverage(space_id: str) -> CoverageStats:
    try:
        return svc.coverage(space_id)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")


@router.post("/extract", response_model=ExtractResult)
async def extract(space_id: str) -> ExtractResult:
    try:
        result = await svc.extract_concepts(space_id)
        return ExtractResult(**result)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")
    except OllamaUnavailable as exc:
        raise HTTPException(503, str(exc))
