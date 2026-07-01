"""Application configuration (SA-008).

Single source of truth for runtime settings. Values come from environment
variables (prefixed ``SCHOLARAI_``) or a local ``.env`` file. Every setting has a
sensible default so the app runs with zero configuration.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCHOLARAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Storage ---
    data_dir: Path = Field(default_factory=lambda: Path.home() / "scholar-ai-data")

    # --- LLM (Ollama) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_timeout: float = 120.0

    # --- Embeddings ---
    embed_model: str = "BAAI/bge-small-en-v1.5"

    # --- Chunking / retrieval ---
    chunk_overlap: float = 0.2
    top_k: int = 5
    # Neighbor expansion (SA-049): include N prev/next chunks around each hit for
    # context. 0 disables.
    retrieval_neighbors: int = 1
    # Over-fetch factor before rerank/dedup-by-section (SA-112).
    retrieval_fetch_multiplier: int = 4
    # Context compression budget in characters before the LLM (SA-113).
    max_context_chars: int = 6000

    # --- API ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Location of versioned prompt files (SA-009). Defaults to backend/prompts.
    prompts_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "prompts"
    )

    # Knowledge-pipeline stage config (SA-131). Defaults to backend/pipeline.yaml.
    pipeline_config: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "pipeline.yaml"
    )

    @field_validator("data_dir", "prompts_dir", "pipeline_config", mode="before")
    @classmethod
    def _expand(cls, v: object) -> object:
        if isinstance(v, str) and v:
            return Path(v).expanduser()
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("chunk_overlap")
    @classmethod
    def _validate_overlap(cls, v: float) -> float:
        if not 0.0 <= v < 1.0:
            raise ValueError("chunk_overlap must be in [0.0, 1.0)")
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
