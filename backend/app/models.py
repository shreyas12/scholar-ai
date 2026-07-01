"""Pydantic request/response schemas shared across routers."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Spaces ------------------------------------------------------------------

class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SpaceRename(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class Space(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    document_count: int = 0
