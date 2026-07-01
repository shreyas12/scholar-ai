"""FastAPI application entrypoint (SA-002).

Run with::

    uvicorn app.main:app --reload

Wires CORS for the frontend dev server and mounts the health router. The storage
root is created on startup; embedding warm-up is best-effort so a missing ML
dependency never blocks boot.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import assessment, chat, concepts, documents, health, spaces
from .storage import ensure_dir, spaces_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scholarai")
access_logger = logging.getLogger("scholarai.access")


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
    app.include_router(documents.router)
    app.include_router(chat.router)
    app.include_router(concepts.router)
    app.include_router(assessment.router)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Structured access log: one line per request with timing (SA-103).

        Fields are ``key=value`` so logs are greppable/parseable without pulling
        in a logging framework. Health checks are demoted to DEBUG to avoid noise.
        """
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        level = logging.DEBUG if request.url.path == "/health" else logging.INFO
        access_logger.log(
            level,
            "method=%s path=%s status=%d duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    return app


app = create_app()
