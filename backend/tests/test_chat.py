"""Tests for chat retrieval + streaming (SA-030–034).

The happy path mocks Ollama's token stream so we can verify the full pipeline
(retrieve → grounded prompt → stream → persist history) without a running LLM.
The unmocked path asserts graceful degradation when Ollama is down.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import retrieval
from app.services.ollama_client import OllamaClient

ANN_TEXT = (
    "HNSW is a graph-based approximate nearest neighbor algorithm for vector "
    "search, offering high recall and low latency. " * 20
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


def _events(resp) -> list[dict]:
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


# --- unit -------------------------------------------------------------------

def test_build_context_numbers_and_cites():
    hits = [
        {"chunk_id": "d:0", "document": "ann.pdf", "page": 3, "text": "HNSW…", "score": 0.9},
        {"chunk_id": "d:1", "document": "notes.txt", "page": None, "text": "BM25…", "score": 0.5},
    ]
    context, sources = retrieval.build_context(hits)
    assert "[1] (ann.pdf, p.3)" in context
    assert "[2] (notes.txt)" in context
    assert sources[0]["document"] == "ann.pdf" and sources[0]["page"] == 3
    assert sources[1]["page"] is None


# --- integration ------------------------------------------------------------

def test_history_starts_empty(client):
    assert client.get("/api/spaces/ml/chat/history").json() == []


def test_chat_happy_path_streams_and_persists(client, monkeypatch):
    async def fake_stream(self, prompt, *, model=None):
        assert "HNSW" in prompt  # grounded context reached the prompt
        for tok in ["HNSW ", "is ", "a graph algorithm."]:
            yield tok

    monkeypatch.setattr(OllamaClient, "generate_stream", fake_stream)

    resp = client.post("/api/spaces/ml/chat", json={"question": "What is HNSW?"})
    assert resp.status_code == 200
    events = _events(resp)

    assert events[0]["type"] == "sources"
    assert len(events[0]["sources"]) >= 1
    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert "".join(tokens) == "HNSW is a graph algorithm."
    assert events[-1]["type"] == "done"

    history = client.get("/api/spaces/ml/chat/history").json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[1]["content"] == "HNSW is a graph algorithm."
    assert history[1]["prompt_version"] == "chat_v1"  # SA-009 stamp
    assert history[1]["sources"]


def test_chat_reports_error_when_ollama_down(client):
    # No Ollama running in the test env → expect a clean error event, not a crash.
    resp = client.post("/api/spaces/ml/chat", json={"question": "What is HNSW?"})
    assert resp.status_code == 200
    events = _events(resp)
    assert events[0]["type"] == "sources"
    assert any(e["type"] == "error" for e in events)
    # a failed generation must not write a partial turn to history
    assert client.get("/api/spaces/ml/chat/history").json() == []


def test_chat_missing_space_404(client):
    assert (
        client.post("/api/spaces/ghost/chat", json={"question": "hi"}).status_code == 404
    )
