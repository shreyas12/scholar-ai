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


# --- Documents ---------------------------------------------------------------

class Document(BaseModel):
    doc_id: str
    name: str
    ext: str
    size: int
    checksum: str
    uploaded_at: str
    chunk_count: int = 0
    status: str = "ready"  # ready | processing | error
    reused: bool = False  # true when an identical upload was a no-op


# --- Concepts / coverage -----------------------------------------------------

class Concept(BaseModel):
    id: str
    label: str
    source_chunk_count: int
    encountered: bool = False


class CoverageStats(BaseModel):
    total: int
    encountered: int
    coverage_pct: float


class ExtractResult(BaseModel):
    total_concepts: int
    sources_processed: int
    prompt_version: str


# --- Concept graph (Epic 5) --------------------------------------------------

class GraphNode(BaseModel):
    id: str
    label: str
    encountered: bool = False
    ready: bool = False  # all prerequisites encountered (SA-063)


class GraphEdge(BaseModel):
    source: str  # prerequisite concept id
    target: str  # concept that depends on it


class ConceptGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ConceptDetail(BaseModel):
    id: str
    label: str
    encountered: bool
    prerequisites: list[str]  # labels
    source_sections: list[str]
