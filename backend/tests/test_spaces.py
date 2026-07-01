"""Tests for Learning Spaces (SA-010, SA-011)."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import spaces as svc


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Storage resolves settings lazily on every call, so clearing the cached
    # settings + pointing the data dir at a temp folder fully isolates each test.
    monkeypatch.setenv("SCHOLARAI_DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    config.get_settings.cache_clear()


def test_create_and_list(client):
    assert client.get("/api/spaces").json() == []

    resp = client.post("/api/spaces", json={"name": "Machine Learning"})
    assert resp.status_code == 201
    space = resp.json()
    assert space["id"] == "machine-learning"
    assert space["name"] == "Machine Learning"
    assert space["document_count"] == 0

    listing = client.get("/api/spaces").json()
    assert len(listing) == 1
    assert listing[0]["id"] == "machine-learning"


def test_duplicate_name_gets_unique_id(client):
    a = client.post("/api/spaces", json={"name": "Kubernetes"}).json()
    b = client.post("/api/spaces", json={"name": "Kubernetes"}).json()
    assert a["id"] == "kubernetes"
    assert b["id"] == "kubernetes-2"


def test_get_open(client):
    client.post("/api/spaces", json={"name": "System Design"})
    resp = client.get("/api/spaces/system-design")
    assert resp.status_code == 200
    assert resp.json()["name"] == "System Design"


def test_get_missing_404(client):
    assert client.get("/api/spaces/nope").status_code == 404


def test_rename_keeps_id(client):
    client.post("/api/spaces", json={"name": "Databricks"})
    resp = client.patch("/api/spaces/databricks", json={"name": "Databricks & Spark"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "databricks"  # id stays stable
    assert body["name"] == "Databricks & Spark"


def test_delete(client):
    client.post("/api/spaces", json={"name": "Temp"})
    assert client.delete("/api/spaces/temp").status_code == 204
    assert client.get("/api/spaces/temp").status_code == 404


def test_delete_missing_404(client):
    assert client.delete("/api/spaces/ghost").status_code == 404


def test_delete_rejects_path_traversal(client):
    # slugify neutralizes separators, but guard the service directly too.
    with pytest.raises(ValueError):
        svc.delete_space("../../etc")
