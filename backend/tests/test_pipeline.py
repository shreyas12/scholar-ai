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
    "chunk_id", "space", "doc_id", "document", "section_id", "parent_id", "level",
    "chunk_number", "total_chunks", "page", "heading_path", "section_title",
    "prev_chunk_id", "next_chunk_id", "quality", "keywords", "text", "created_at",
}


def test_pipeline_produces_chunk_records(env):
    path = _make_doc("ml", "ann", "HNSW graph search " * 500)
    chunks, sections, log = pipeline.run_document("ml", "ann", "ann.txt", ".txt", "abc123", path)
    assert len(chunks) >= 3  # at least one chunk per level
    assert chunks[0]["chunk_id"].startswith("ann:")
    assert chunks[0]["document"] == "ann.txt"
    assert CHUNK_FIELDS <= set(chunks[0])
    # multi-level: all three representations present
    assert {c["level"] for c in chunks} == {"large", "medium", "small"}
    # stage log records every stage
    assert {e["stage"] for e in log if "stage" in e} == {
        "extract", "clean", "section", "chunk", "enrich"
    }


def test_parent_child_sections(env):
    path = _make_doc("ml", "ann", "HNSW graph search " * 500)
    chunks, sections, _ = pipeline.run_document("ml", "ann", "ann.txt", ".txt", "abc", path)
    # every chunk points at a section that exists in the returned section map
    sec_id = chunks[0]["section_id"]
    assert sec_id in sections
    assert chunks[0]["parent_id"] == sec_id
    assert "text" in sections[sec_id]


def test_stage_cache_hit_on_reingest(env):
    path = _make_doc("ml", "ann", "HNSW graph search " * 500)
    _, _, log1 = pipeline.run_document("ml", "ann", "ann.txt", ".txt", "abc123", path)
    assert all(e["cached"] is False for e in log1 if "cached" in e)

    _, _, log2 = pipeline.run_document("ml", "ann", "ann.txt", ".txt", "abc123", path)
    assert all(e["cached"] is True for e in log2 if "cached" in e)


def test_cache_invalidated_on_checksum_change(env):
    path = _make_doc("ml", "ann", "HNSW graph search " * 500)
    pipeline.run_document("ml", "ann", "ann.txt", ".txt", "sum-A", path)
    _, _, log = pipeline.run_document("ml", "ann", "ann.txt", ".txt", "sum-B", path)
    assert all(e["cached"] is False for e in log if "cached" in e)


def test_expand_neighbors(env, monkeypatch):
    from app.services import retrieval, vectorstore

    records = {
        "d:m:0": {"chunk_id": "d:m:0", "text": "A", "next_chunk_id": "d:m:1", "prev_chunk_id": None},
        "d:m:1": {"chunk_id": "d:m:1", "text": "B", "next_chunk_id": "d:m:2", "prev_chunk_id": "d:m:0"},
        "d:m:2": {"chunk_id": "d:m:2", "text": "C", "next_chunk_id": None, "prev_chunk_id": "d:m:1"},
    }
    monkeypatch.setattr(vectorstore, "load_all_chunks", lambda space_id: records)

    hit = dict(records["d:m:1"], score=0.9)
    out = retrieval.expand_neighbors("ml", [hit], window=1)
    assert out[0]["text"] == "A B C"        # prev + hit + next
    assert out[0]["chunk_id"] == "d:m:1"    # citation stays the hit
    assert out[0]["score"] == 0.9
    assert set(out[0]["neighbors"]) == {"d:m:0", "d:m:2"}


def test_expand_neighbors_disabled(env):
    from app.services import retrieval

    hits = [{"chunk_id": "x", "text": "only"}]
    assert retrieval.expand_neighbors("ml", hits, window=0) is hits


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
