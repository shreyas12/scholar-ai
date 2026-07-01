"""Document management REST API (SA-020, SA-023)."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models import Document
from ..services import documents as svc
from ..services.embeddings import EmbeddingsUnavailable
from ..services.extraction import UnsupportedFormat
from ..services.spaces import SpaceNotFound

router = APIRouter(prefix="/api/spaces/{space_id}/documents", tags=["documents"])


@router.get("", response_model=list[Document])
def list_documents(space_id: str) -> list[Document]:
    try:
        return svc.list_documents(space_id)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")


@router.post("", response_model=Document, status_code=201)
async def upload_document(space_id: str, file: UploadFile = File(...)) -> Document:
    content = await file.read()
    try:
        return svc.save_and_ingest(space_id, file.filename or "document", content)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")
    except UnsupportedFormat as exc:
        raise HTTPException(415, str(exc))
    except EmbeddingsUnavailable as exc:
        raise HTTPException(503, str(exc))


@router.delete("/{doc_id}", status_code=204)
def delete_document(space_id: str, doc_id: str) -> None:
    try:
        svc.delete_document(space_id, doc_id)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")
    except svc.DocumentNotFound:
        raise HTTPException(404, f"Document {doc_id!r} not found")
