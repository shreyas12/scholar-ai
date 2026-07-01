"""Tests for the Knowledge Processing Pipeline seam (Slice A)."""

import pytest

from app import config, storage
from app.knowledge import pipeline, processors
from app.knowledge.stages import ChunkStage, ExtractStage


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARAI_DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    yield tmp_path
    config.get_settings.cache_clear()


def _make_doc(space_id: str, doc_id: str, text: str):
    layout = storage.init_space_dirs(space_id)
    doc_dir = storage.ensure_dir(layout["documents"] / doc_id)
    path = doc_dir / "original.txt"
    path.write_text(text, encoding="utf-8")
    return path


CHUNK_FIELDS = {
    "chunk_id", "space", "doc_id", "document", "chunk_number", "total_chunks",
    "page", "prev_chunk_id", "next_chunk_id", "text", "created_at",
}


def test_pipeline_produces_chunk_records(env):
    path = _make_doc("ml", "ann", "HNSW graph search " * 500)
    chunks, log = pipeline.run_document("ml", "ann", "ann.txt", ".txt", "abc123", path)
    assert len(chunks) >= 2
    assert chunks[0]["chunk_id"] == "ann:0"
    assert chunks[0]["document"] == "ann.txt"
    assert CHUNK_FIELDS <= set(chunks[0])
    # stage log records every stage
    assert {e["stage"] for e in log if "stage" in e} == {"extract", "clean", "chunk"}


def test_stage_cache_hit_on_reingest(env):
    path = _make_doc("ml", "ann", "HNSW graph search " * 500)
    _, log1 = pipeline.run_document("ml", "ann", "ann.txt", ".txt", "abc123", path)
    assert all(e["cached"] is False for e in log1 if "cached" in e)

    _, log2 = pipeline.run_document("ml", "ann", "ann.txt", ".txt", "abc123", path)
    assert all(e["cached"] is True for e in log2 if "cached" in e)


def test_cache_invalidated_on_checksum_change(env):
    path = _make_doc("ml", "ann", "HNSW graph search " * 500)
    pipeline.run_document("ml", "ann", "ann.txt", ".txt", "sum-A", path)
    _, log = pipeline.run_document("ml", "ann", "ann.txt", ".txt", "sum-B", path)
    assert all(e["cached"] is False for e in log if "cached" in e)


def test_processor_registry(env):
    exts = processors.supported_extensions()
    assert {".pdf", ".docx", ".txt", ".md"} <= exts
    assert isinstance(processors.get_processor(".txt"), processors.TextProcessor)
    with pytest.raises(processors.UnsupportedFormat):
        processors.get_processor(".xyz")


def test_default_config_used_when_file_missing(env, monkeypatch):
    monkeypatch.setenv("SCHOLARAI_PIPELINE_CONFIG", str(env / "does-not-exist.yaml"))
    config.get_settings.cache_clear()
    cfg = pipeline.load_config()
    assert "chunk" in cfg["stages"]


def test_stage_enable_toggle(env):
    ctx = pipeline.PipelineContext(
        space_id="ml", doc_id="d", name="n", ext=".txt", checksum="x",
        original_path=env, config={"stages": {"chunk": {"enabled": False}}},
    )
    assert ChunkStage().is_enabled(ctx) is False
    assert ExtractStage().is_enabled(ctx) is True  # unspecified → default on


def test_dense_retriever_empty_space(env):
    from app.services.retrieval import DenseRetriever

    storage.init_space_dirs("ml")
    assert DenseRetriever().retrieve("ml", "anything", 3) == []
