"""Tests for the storage layer (SA-004)."""

import importlib

import pytest

from app import config, storage


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARAI_DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    importlib.reload(storage)
    yield tmp_path
    config.get_settings.cache_clear()


def test_slugify():
    assert storage.slugify("Machine Learning") == "machine-learning"
    assert storage.slugify("  System   Design!! ") == "system-design"
    with pytest.raises(ValueError):
        storage.slugify("***")


def test_init_space_dirs_creates_layout(data_dir):
    layout = storage.init_space_dirs("machine-learning")
    assert layout["root"].is_dir()
    assert layout["documents"].is_dir()
    assert layout["vectors"].is_dir()


def test_write_then_read_json_roundtrip(data_dir):
    layout = storage.init_space_dirs("ml")
    payload = {"id": "ml", "name": "ML", "concepts": ["HNSW", "BM25"]}
    storage.write_json(layout["space_json"], payload)
    assert storage.read_json(layout["space_json"]) == payload


def test_read_json_missing_returns_default(data_dir):
    missing = storage.space_dir("nope") / "progress.json"
    assert storage.read_json(missing, default={}) == {}


def test_write_json_is_atomic_no_tmp_left(data_dir):
    layout = storage.init_space_dirs("ml")
    storage.write_json(layout["concepts"], {"a": 1})
    leftovers = list(layout["root"].glob("*.tmp"))
    assert leftovers == []


def test_append_jsonl(data_dir):
    layout = storage.init_space_dirs("ml")
    storage.append_jsonl(layout["events"], {"kind": "q", "n": 1})
    storage.append_jsonl(layout["events"], {"kind": "a", "n": 2})
    lines = layout["events"].read_text().strip().splitlines()
    assert len(lines) == 2
