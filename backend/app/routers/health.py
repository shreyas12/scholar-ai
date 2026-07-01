"""Health & readiness endpoints (SA-002).

``/health`` is always cheap and never fails — it reports the status of each
subsystem (Ollama, embeddings, storage) so the frontend can guide setup
("Ollama not running", "model not pulled") without the API itself falling over.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings
from ..services.embeddings import get_embedding_service
from ..services.ollama_client import OllamaClient

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    ollama = OllamaClient()

    ollama_up = await ollama.is_up()
    models: list[str] = []
    if ollama_up:
        try:
            models = await ollama.list_models()
        except Exception:  # noqa: BLE001 — health must never raise
            models = []

    embed = get_embedding_service()
    model_pulled = any(m.startswith(settings.ollama_model.split(":")[0]) for m in models)

    return {
        "status": "ok",
        "service": "scholarai-backend",
        "version": "0.1.0",
        "data_dir": str(settings.data_dir),
        "ollama": {
            "base_url": settings.ollama_base_url,
            "reachable": ollama_up,
            "configured_model": settings.ollama_model,
            "model_pulled": model_pulled,
            "available_models": models,
        },
        "embeddings": {
            "model": settings.embed_model,
            "dependency_installed": embed.dependency_installed(),
            "loaded": embed.is_loaded,
        },
    }
