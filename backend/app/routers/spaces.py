"""Learning Spaces REST API (SA-010, SA-011)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import Space, SpaceCreate, SpaceRename
from ..services import spaces as svc

router = APIRouter(prefix="/api/spaces", tags=["spaces"])


@router.get("", response_model=list[Space])
def list_spaces() -> list[Space]:
    return svc.list_spaces()


@router.post("", response_model=Space, status_code=201)
def create_space(body: SpaceCreate) -> Space:
    return svc.create_space(body.name)


@router.get("/{space_id}", response_model=Space)
def get_space(space_id: str) -> Space:
    try:
        return svc.get_space(space_id)
    except svc.SpaceNotFound:
        raise HTTPException(status_code=404, detail=f"Space {space_id!r} not found")


@router.patch("/{space_id}", response_model=Space)
def rename_space(space_id: str, body: SpaceRename) -> Space:
    try:
        return svc.rename_space(space_id, body.name)
    except svc.SpaceNotFound:
        raise HTTPException(status_code=404, detail=f"Space {space_id!r} not found")


@router.delete("/{space_id}", status_code=204)
def delete_space(space_id: str) -> None:
    try:
        svc.delete_space(space_id)
    except svc.SpaceNotFound:
        raise HTTPException(status_code=404, detail=f"Space {space_id!r} not found")
