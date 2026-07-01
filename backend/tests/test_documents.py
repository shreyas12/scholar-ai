"""Integration tests for document ingest + FAISS retrieval (SA-020–024).

These exercise the real embedding model + FAISS, so they're a touch slower than
the unit tests but prove the full simple-ingest path end to end.
"""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import vectorstore


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARAI_DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    with TestClient(app) as c:
        c.post("/api/spaces", json={"name": "ML"})
        yield c
    config.get_settings.cache_clear()


ANN_TEXT = (
    "HNSW is a graph-based approximate nearest neighbor algorithm. "
    "It builds a hierarchical navigable small world graph for fast vector search "
    "with high recall and low latency. " * 20
)
RANKING_TEXT = (
    "BM25 is a bag-of-words ranking function used in keyword search. "
    "NDCG and MRR are ranking metrics that evaluate ordered relevance. " * 20
)


def _upload(client, name, text):
    return client.post(
        "/api/spaces/ml/documents",
        files={"file": (name, text.encode(), "text/plain")},
    )


def test_upload_ingests_and_lists(client):
    resp = _upload(client, "ann.txt", ANN_TEXT)
    assert resp.status_code == 201
    doc = resp.json()
    assert doc["doc_id"] == "ann"
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1
    assert doc["reused"] is False

    listing = client.get("/api/spaces/ml/documents").json()
    assert len(listing) == 1


def test_identical_reupload_is_noop(client):
    _upload(client, "ann.txt", ANN_TEXT)
    again = _upload(client, "ann.txt", ANN_TEXT)
    assert again.json()["reused"] is True


def test_changed_file_reingests(client):
    first = _upload(client, "ann.txt", ANN_TEXT).json()
    changed = _upload(client, "ann.txt", ANN_TEXT + " Extra content here.").json()
    assert changed["reused"] is False
    assert changed["checksum"] != first["checksum"]


def test_unsupported_type_rejected(client):
    resp = client.post(
        "/api/spaces/ml/documents",
        files={"file": ("notes.pptx", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_retrieval_returns_relevant_chunk(client):
    _upload(client, "ann.txt", ANN_TEXT)
    _upload(client, "ranking.txt", RANKING_TEXT)

    hits = vectorstore.search("ml", "What is HNSW graph search?", top_k=3)
    assert hits, "expected retrieval results"
    # the top hit should come from the ANN document, not the ranking one
    assert hits[0]["doc_id"] == "ann"
    assert "score" in hits[0]


def test_delete_removes_doc_and_index(client):
    _upload(client, "ann.txt", ANN_TEXT)
    assert client.delete("/api/spaces/ml/documents/ann").status_code == 204
    assert client.get("/api/spaces/ml/documents").json() == []
    # index should be empty now → no results
    assert vectorstore.search("ml", "HNSW", top_k=3) == []
