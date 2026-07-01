"""Embedding service (SA-006).

Loads a local sentence-transformers model (default ``BAAI/bge-small-en-v1.5``) and
produces dense vectors for chunks and queries.

The heavy ML dependency is *optional* (``pip install -e ".[ml]"``) so the API can
boot and serve ``/health`` before anyone has downloaded a model. The model itself
is lazy-loaded on first use and cached as a process singleton.
"""

from __future__ import annotations

import os
import threading
from functools import lru_cache

from ..config import get_settings


class EmbeddingsUnavailable(RuntimeError):
    """Raised when sentence-transformers isn't installed or the model won't load."""


class EmbeddingService:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().embed_model
        self._model = None
        self._lock = threading.Lock()

    @staticmethod
    def dependency_installed() -> bool:
        try:
            import sentence_transformers  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            # SA-101: in offline mode, tell HF Hub / Transformers not to touch the
            # network. Set before the import so the libraries pick it up.
            if get_settings().offline:
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingsUnavailable(
                    "sentence-transformers is not installed. "
                    'Run: pip install -e ".[ml]"'
                ) from exc
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:  # noqa: BLE001 — surface a clean message
                raise EmbeddingsUnavailable(
                    f"Failed to load embedding model {self.model_name!r}: {exc}"
                ) from exc
            return self._model

    def warm_up(self) -> None:
        """Force model load (used at startup so the first request isn't slow)."""
        self._ensure_model()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. bge models recommend normalized embeddings."""
        model = self._ensure_model()
        vectors = model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        return vectors.tolist()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
