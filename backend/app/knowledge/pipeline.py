"""Knowledge Processing Pipeline orchestrator (SA-050, SA-131).

Runs an ordered list of stages over a single document. Each stage is a small,
pure-ish unit that reads/writes named artifacts on a :class:`PipelineContext`.
The orchestrator provides, once, for every stage:

* **config-driven enable/disable** from ``pipeline.yaml`` (fast-ingest = disable
  the expensive LLM stages),
* **stage-level caching** (see :mod:`.cache`) so unchanged stages are skipped,
* **per-stage observability** (timing + output size + cache-hit) via ``stage_log``.

Slice A wires the *existing* extract → clean → chunk behavior into this shape with
no functional change; later slices add/replace stages without touching this file.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..config import get_settings
from . import cache

logger = logging.getLogger("scholarai.pipeline")

# Built-in default if pipeline.yaml is absent. Order matters.
DEFAULT_CONFIG: dict[str, Any] = {
    "stages": {
        "extract": {"enabled": True},
        "clean": {"enabled": True},
        "section": {"enabled": True},
        "chunk": {
            "enabled": True,
            "adaptive": True,
            "overlap": 0.2,
            "levels": {"large": 350, "medium": 180, "small": 80},
        },
        "enrich": {"enabled": True},
    }
}


@dataclass
class PipelineContext:
    space_id: str
    doc_id: str
    name: str
    ext: str
    checksum: str
    original_path: Path
    config: dict
    artifacts: dict[str, Any] = field(default_factory=dict)
    stage_log: list[dict] = field(default_factory=list)


class Stage:
    """Base class for pipeline stages.

    Subclasses set ``name``/``version``/``output_key`` and implement
    :meth:`run`, returning the artifact to store under ``output_key``.
    """

    name: str = ""
    version: str = "1"
    output_key: str = ""

    def run(self, ctx: PipelineContext) -> Any:  # pragma: no cover - abstract
        raise NotImplementedError

    def stage_config(self, ctx: PipelineContext) -> dict:
        return ctx.config.get("stages", {}).get(self.name, {})

    def is_enabled(self, ctx: PipelineContext) -> bool:
        return self.stage_config(ctx).get("enabled", True)


def load_config() -> dict:
    path = get_settings().pipeline_config
    if path and Path(path).exists():
        loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if loaded:
            return loaded
    return DEFAULT_CONFIG


class Pipeline:
    def __init__(self, stages: list[Stage]):
        self.stages = stages

    def run(self, ctx: PipelineContext) -> Any:
        chain_sig = ""
        for stage in self.stages:
            if not stage.is_enabled(ctx):
                ctx.stage_log.append({"stage": stage.name, "skipped": True})
                continue

            chain_sig += f"{stage.name}@{stage.version};"
            key = cache.compute_key(ctx.checksum, chain_sig, stage.stage_config(ctx))

            started = time.perf_counter()
            cached = cache.get(ctx.space_id, ctx.doc_id, stage.name, key)
            if cached is not None:
                ctx.artifacts[stage.output_key] = cached
                hit = True
            else:
                artifact = stage.run(ctx)
                ctx.artifacts[stage.output_key] = artifact
                cache.put(ctx.space_id, ctx.doc_id, stage.name, key, artifact)
                hit = False

            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            out = ctx.artifacts.get(stage.output_key)
            size = len(out) if isinstance(out, (list, dict)) else None
            entry = {"stage": stage.name, "ms": elapsed_ms, "cached": hit, "size": size}
            ctx.stage_log.append(entry)
            logger.info("pipeline %s: %s", ctx.name, entry)
        return ctx.artifacts.get("chunks", [])


def default_pipeline() -> Pipeline:
    # Imported here to avoid a circular import (stages import from this module).
    from .stages import ChunkStage, CleanStage, EnrichStage, ExtractStage, SectionStage

    return Pipeline(
        [ExtractStage(), CleanStage(), SectionStage(), ChunkStage(), EnrichStage()]
    )


def run_document(
    space_id: str,
    doc_id: str,
    name: str,
    ext: str,
    checksum: str,
    original_path: Path,
) -> tuple[list[dict], list[dict]]:
    """Run the default pipeline for one document. Returns (chunks, stage_log)."""
    ctx = PipelineContext(
        space_id=space_id,
        doc_id=doc_id,
        name=name,
        ext=ext,
        checksum=checksum,
        original_path=original_path,
        config=load_config(),
    )
    chunks = default_pipeline().run(ctx)
    return chunks, ctx.stage_log
