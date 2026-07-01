"""Smoke test for the health endpoint (SA-002).

Runs against the app in-process; does not require Ollama or the ML deps — the
endpoint must report their absence, not crash.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok_without_ollama_or_ml():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "ollama" in body and "reachable" in body["ollama"]
    assert "embeddings" in body
