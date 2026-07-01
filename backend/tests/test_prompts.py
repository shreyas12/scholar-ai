"""Tests for prompt versioning (SA-009)."""

import pytest

from app import config, prompts


@pytest.fixture()
def prompts_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARAI_PROMPTS_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    prompts.load_prompt.cache_clear()
    (tmp_path / "grading_v1.md").write_text("v1 {answer}", encoding="utf-8")
    (tmp_path / "grading_v2.md").write_text("v2 {answer}", encoding="utf-8")
    (tmp_path / "chat_v1.md").write_text("chat {question}", encoding="utf-8")
    yield tmp_path
    config.get_settings.cache_clear()
    prompts.load_prompt.cache_clear()


def test_loads_latest_version_by_default(prompts_dir):
    p = prompts.load_prompt("grading")
    assert p.version == "grading_v2"
    assert p.render(answer="x") == "v2 x"


def test_pin_specific_version(prompts_dir):
    p = prompts.load_prompt("grading", version=1)
    assert p.version == "grading_v1"


def test_missing_prompt_raises(prompts_dir):
    with pytest.raises(FileNotFoundError):
        prompts.load_prompt("does_not_exist")


def test_missing_version_raises(prompts_dir):
    with pytest.raises(FileNotFoundError):
        prompts.load_prompt("grading", version=99)


def test_list_prompts(prompts_dir):
    listing = prompts.list_prompts()
    assert listing["grading"] == [1, 2]
    assert listing["chat"] == [1]
