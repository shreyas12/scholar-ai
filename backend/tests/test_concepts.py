"""Tests for basic concept extraction + coverage (SA-035–037).

Extraction mocks Ollama's per-chunk response so the full pipeline (extract →
concepts.json → chunk tagging → coverage via chat) runs without a live LLM.
"""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import concepts as svc
from app.services.ollama_client import OllamaClient

ANN_TEXT = (
    "HNSW is a graph-based approximate nearest neighbor algorithm for vector "
    "search with high recall and low latency. " * 20
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARAI_DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    with TestClient(app) as c:
        c.post("/api/spaces", json={"name": "ML"})
        c.post(
            "/api/spaces/ml/documents",
            files={"file": ("ann.txt", ANN_TEXT.encode(), "text/plain")},
        )
        yield c
    config.get_settings.cache_clear()


def _mock_extract(monkeypatch, payload='["HNSW", "Vector Search"]'):
    async def fake_generate(self, prompt, *, model=None):
        return payload

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)


# --- unit -------------------------------------------------------------------

def test_parse_clean_json_array():
    assert svc.parse_concept_list('["HNSW", "ANN"]') == ["HNSW", "ANN"]


def test_parse_array_embedded_in_prose():
    raw = 'Sure! Here are the concepts: ["BM25", "NDCG"] hope that helps'
    assert svc.parse_concept_list(raw) == ["BM25", "NDCG"]


def test_parse_fallback_lines():
    raw = "- HNSW\n- Product Quantization\n- IVF"
    assert svc.parse_concept_list(raw) == ["HNSW", "Product Quantization", "IVF"]


# --- integration ------------------------------------------------------------

def test_extract_builds_concept_set(client, monkeypatch):
    _mock_extract(monkeypatch)
    resp = client.post("/api/spaces/ml/concepts/extract")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_concepts"] == 2
    assert body["sources_processed"] >= 1
    assert body["prompt_version"] == "concept_extraction_v1"

    concepts = client.get("/api/spaces/ml/concepts").json()
    labels = {c["label"] for c in concepts}
    assert labels == {"HNSW", "Vector Search"}
    assert all(c["encountered"] is False for c in concepts)


def test_coverage_starts_zero(client, monkeypatch):
    _mock_extract(monkeypatch)
    client.post("/api/spaces/ml/concepts/extract")
    cov = client.get("/api/spaces/ml/concepts/coverage").json()
    assert cov == {"total": 2, "encountered": 0, "coverage_pct": 0.0}


def test_chat_marks_concepts_encountered(client, monkeypatch):
    _mock_extract(monkeypatch)
    client.post("/api/spaces/ml/concepts/extract")

    async def fake_stream(self, prompt, *, model=None):
        yield "HNSW is a graph algorithm."

    monkeypatch.setattr(OllamaClient, "generate_stream", fake_stream)

    resp = client.post("/api/spaces/ml/chat", json={"question": "What is HNSW?"})
    import json

    events = [json.loads(l) for l in resp.text.splitlines() if l.strip()]
    concept_events = [e for e in events if e["type"] == "concepts"]
    assert concept_events, "expected a concepts-touched event"

    cov = client.get("/api/spaces/ml/concepts/coverage").json()
    assert cov["encountered"] >= 1
    assert cov["coverage_pct"] > 0

    # persisted assistant turn carries the touched concepts
    history = client.get("/api/spaces/ml/chat/history").json()
    assert history[1]["concepts"]


def test_extract_503_when_ollama_down(client):
    # no mock, real env has no Ollama
    assert client.post("/api/spaces/ml/concepts/extract").status_code == 503


def test_concepts_for_chunks_empty_before_extraction(client):
    assert svc.concepts_for_chunks("ml", ["ann:0"]) == []


# --- Concept graph (Epic 5) -------------------------------------------------

def test_canonicalize_merges_label_variants():
    concepts = {
        "hnsw": {"id": "hnsw", "label": "HNSW", "source_sections": ["s0"]},
        "hnsw-algorithm": {"id": "hnsw-algorithm", "label": "HNSW algorithm", "source_sections": ["s1"]},
        "bm25": {"id": "bm25", "label": "BM25", "source_sections": ["s0"]},
    }
    section_concepts = {"s0": ["hnsw", "bm25"], "s1": ["hnsw-algorithm"]}
    merged, sc = svc.canonicalize_concepts(concepts, section_concepts)
    assert len(merged) == 2  # the two HNSW variants collapse; BM25 stays
    hnsw = next(n for n in merged.values() if n["label"].startswith("HNSW"))
    assert set(hnsw["source_sections"]) == {"s0", "s1"}  # sections merged
    assert sc["s1"][0] in merged  # remapped to surviving id


async def test_infer_prerequisites_parses_edges(monkeypatch):
    from app.services.ollama_client import OllamaClient

    concepts = {
        "hnsw": {"id": "hnsw", "label": "HNSW"},
        "ann": {"id": "ann", "label": "ANN"},
        "vector-search": {"id": "vector-search", "label": "Vector Search"},
    }

    async def fake_gen(self, prompt, model=None):
        return '[{"concept": "HNSW", "prerequisites": ["ANN", "Vector Search"]}]'

    monkeypatch.setattr(OllamaClient, "generate", fake_gen)
    await svc.infer_prerequisites(concepts, OllamaClient())
    assert set(concepts["hnsw"]["prerequisites"]) == {"ann", "vector-search"}


def _mock_extract_with_graph(monkeypatch):
    """Concept extraction returns two concepts per section; prereq call links them."""
    from app.services.ollama_client import OllamaClient

    async def fake_gen(self, prompt, model=None):
        if "prerequisite" in prompt.lower():
            return '[{"concept": "HNSW", "prerequisites": ["Vector Search"]}]'
        return '["HNSW", "Vector Search"]'

    monkeypatch.setattr(OllamaClient, "generate", fake_gen)


def test_graph_endpoint(client, monkeypatch):
    _mock_extract_with_graph(monkeypatch)
    client.post("/api/spaces/ml/concepts/extract")

    graph = client.get("/api/spaces/ml/concepts/graph").json()
    labels = {n["label"] for n in graph["nodes"]}
    assert labels == {"HNSW", "Vector Search"}
    assert graph["edges"] == [{"source": "vector-search", "target": "hnsw"}]


def test_concept_detail_endpoint(client, monkeypatch):
    _mock_extract_with_graph(monkeypatch)
    client.post("/api/spaces/ml/concepts/extract")

    detail = client.get("/api/spaces/ml/concepts/hnsw").json()
    assert detail["label"] == "HNSW"
    assert detail["prerequisites"] == ["Vector Search"]
    assert client.get("/api/spaces/ml/concepts/nonexistent").status_code == 404


def test_ready_to_learn_flag(client, monkeypatch):
    _mock_extract_with_graph(monkeypatch)
    client.post("/api/spaces/ml/concepts/extract")

    # nothing encountered yet → HNSW not ready (prereq Vector Search not covered)
    g0 = client.get("/api/spaces/ml/concepts/graph").json()
    assert next(n for n in g0["nodes"] if n["id"] == "hnsw")["ready"] is False

    # encounter the prerequisite → HNSW becomes ready to learn
    from app.services import progress

    progress.mark_encountered("ml", ["vector-search"])
    g1 = client.get("/api/spaces/ml/concepts/graph").json()
    assert next(n for n in g1["nodes"] if n["id"] == "hnsw")["ready"] is True
