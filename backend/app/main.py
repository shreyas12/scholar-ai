"""FastAPI application entrypoint (SA-002).

Run with::

    uvicorn app.main:app --reload

Wires CORS for the frontend dev server and mounts the health router. The storage
root is created on startup; embedding warm-up is best-effort so a missing ML
dependency never blocks boot.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import health, spaces
from .storage import ensure_dir, spaces_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scholarai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    ensure_dir(spaces_dir())
    logger.info("ScholarAI storage root: %s", settings.data_dir)
    logger.info("Ollama: %s (%s)", settings.ollama_base_url, settings.ollama_model)
    logger.info("Embeddings: %s", settings.embed_model)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ScholarAI",
        description="Local-first, evidence-based learning platform.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(spaces.router)
    return app


app = create_app()
