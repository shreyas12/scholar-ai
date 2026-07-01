"""Concepts + coverage REST API (SA-035, SA-037)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import (
    Concept,
    ConceptDetail,
    ConceptGraph,
    CoverageStats,
    ExtractResult,
)
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


@router.get("/graph", response_model=ConceptGraph)
def graph(space_id: str) -> ConceptGraph:
    try:
        return svc.get_graph(space_id)
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


# Dynamic route last so it doesn't shadow /coverage, /graph, /extract.
@router.get("/{concept_id}", response_model=ConceptDetail)
def concept_detail(space_id: str, concept_id: str) -> ConceptDetail:
    try:
        return svc.get_concept_detail(space_id, concept_id)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")
    except svc.ConceptNotFound:
        raise HTTPException(404, f"Concept {concept_id!r} not found")
