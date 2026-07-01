"""Tests for assessment: question gen, grading, events, mastery projection.

A single mocked ``OllamaClient.generate`` routes by prompt content so the whole
flow (extract concepts → generate quiz → grade answers → project mastery) runs
without a live LLM.
"""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import assessment as svc
from app.services.ollama_client import OllamaClient

ANN_TEXT = (
    "HNSW is a graph-based approximate nearest neighbor algorithm for vector "
    "search with high recall and low latency. " * 20
)

QUESTIONS_JSON = """[
  {"type": "recall", "question": "Explain HNSW.", "ideal_answer": "A layered proximity graph for ANN search."},
  {"type": "recognition", "question": "HNSW is primarily used for?",
   "options": ["Sorting", "Approximate nearest neighbor search", "Hashing", "Compression"],
   "answer_index": 1},
  {"type": "application", "question": "You need low-latency vector search. Why HNSW?",
   "ideal_answer": "Its graph structure gives high recall at low latency."}
]"""


def _fake_generate(grade='{"correct": true, "score": 90, "reasoning": "solid", "misconception": null}'):
    async def fake_generate(self, prompt, *, model=None):
        if "grading a learner" in prompt:
            return grade
        if "quiz questions" in prompt:
            return QUESTIONS_JSON
        if "mapping prerequisite" in prompt:
            return "[]"
        # concept extraction
        return '["HNSW", "Vector Search"]'

    return fake_generate


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARAI_DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    monkeypatch.setattr(OllamaClient, "generate", _fake_generate())
    with TestClient(app) as c:
        c.post("/api/spaces", json={"name": "ML"})
        c.post(
            "/api/spaces/ml/documents",
            files={"file": ("ann.txt", ANN_TEXT.encode(), "text/plain")},
        )
        c.post("/api/spaces/ml/concepts/extract")
        yield c
    config.get_settings.cache_clear()


# --- parsing (pure) ---------------------------------------------------------

def test_parse_questions_validates_types():
    qs = svc.parse_questions(QUESTIONS_JSON)
    assert [q["type"] for q in qs] == ["recall", "recognition", "application"]
    assert qs[1]["answer_index"] == 1


def test_parse_questions_drops_bad_mcq():
    raw = '[{"type": "recognition", "question": "?", "options": ["a"], "answer_index": 5}]'
    assert svc.parse_questions(raw) == []


def test_parse_questions_extracts_from_prose():
    raw = 'Here you go: [{"type": "recall", "question": "What?", "ideal_answer": "X"}] done'
    assert svc.parse_questions(raw) == [
        {"type": "recall", "question": "What?", "ideal_answer": "X"}
    ]


def test_parse_grade_clamps_and_defaults():
    g = svc.parse_grade('{"score": 150, "correct": true}')
    assert g["score"] == 100
    g2 = svc.parse_grade("not json")
    assert g2["score"] == 0 and g2["correct"] is False


# --- generation -------------------------------------------------------------

def test_generate_quiz_hides_answer_keys(client):
    quiz = client.post("/api/spaces/ml/concepts/hnsw/quiz").json()
    assert quiz["concept_id"] == "hnsw"
    assert len(quiz["questions"]) == 3
    mcq = next(q for q in quiz["questions"] if q["type"] == "recognition")
    assert mcq["options"] and "answer_index" not in mcq
    free = next(q for q in quiz["questions"] if q["type"] == "recall")
    assert free["options"] is None and "ideal_answer" not in free


def test_generate_quiz_unknown_concept_404(client):
    assert client.post("/api/spaces/ml/concepts/nope/quiz").status_code == 404


# --- grading + events -------------------------------------------------------

def test_recognition_graded_deterministically(client, monkeypatch):
    quiz = client.post("/api/spaces/ml/concepts/hnsw/quiz").json()
    qid = next(q["id"] for q in quiz["questions"] if q["type"] == "recognition")

    ok = client.post(
        f"/api/spaces/ml/quiz/{quiz['quiz_id']}/answer",
        json={"question_id": qid, "selected_index": 1, "confidence": 4},
    ).json()
    assert ok["correct"] is True and ok["score"] == 100

    bad = client.post(
        f"/api/spaces/ml/quiz/{quiz['quiz_id']}/answer",
        json={"question_id": qid, "selected_index": 0, "confidence": 5},
    ).json()
    assert bad["correct"] is False and bad["score"] == 0
    # wrong + high confidence → misconception flag (SA-075)
    assert bad["misconception_flag"] is True
    assert bad["correct_answer"] == "Approximate nearest neighbor search"


def test_free_text_uses_llm_judge(client):
    quiz = client.post("/api/spaces/ml/concepts/hnsw/quiz").json()
    qid = next(q["id"] for q in quiz["questions"] if q["type"] == "recall")
    fb = client.post(
        f"/api/spaces/ml/quiz/{quiz['quiz_id']}/answer",
        json={"question_id": qid, "answer": "A proximity graph for ANN.", "confidence": 3},
    ).json()
    assert fb["score"] == 90 and fb["correct"] is True


def test_answer_records_event_and_projects_mastery(client):
    quiz = client.post("/api/spaces/ml/concepts/hnsw/quiz").json()
    for q in quiz["questions"]:
        payload = {"question_id": q["id"], "confidence": 4}
        if q["type"] == "recognition":
            payload["selected_index"] = 1
        else:
            payload["answer"] = "HNSW is a proximity graph for fast ANN search."
        r = client.post(f"/api/spaces/ml/quiz/{quiz['quiz_id']}/answer", json=payload)
        assert r.status_code == 200

    report = client.get("/api/spaces/ml/mastery").json()
    hnsw = next(c for c in report["concepts"] if c["concept_id"] == "hnsw")
    assert hnsw["evidence_count"] == 3
    assert hnsw["mastery"] is not None and hnsw["mastery"] > 0
    assert hnsw["bucket"] == "mastered"  # all correct, high score
    assert hnsw["recall"] == 90 and hnsw["recognition"] == 100
    assert report["summary"]["assessed"] == 1
    # the untouched concept stays unknown
    assert any(c["bucket"] == "unknown" for c in report["concepts"])


def test_misconception_lowers_mastery(client):
    quiz = client.post("/api/spaces/ml/concepts/hnsw/quiz").json()
    mcq = next(q["id"] for q in quiz["questions"] if q["type"] == "recognition")
    # wrong answer, high confidence → misconception recorded
    client.post(
        f"/api/spaces/ml/quiz/{quiz['quiz_id']}/answer",
        json={"question_id": mcq, "selected_index": 0, "confidence": 5},
    )
    m = client.get("/api/spaces/ml/concepts/hnsw/mastery").json()
    assert m["misconceptions"] == 1
    assert m["bucket"] in {"weak", "learning"}  # recognition=0 with a penalty


def test_chat_answer_grade_hook_records_evidence(client):
    fb = client.post(
        "/api/spaces/ml/concepts/hnsw/grade-answer",
        json={
            "question": "What is HNSW?",
            "answer": "A layered graph for approximate nearest neighbor search.",
            "confidence": 4,
            "retrieval_confidence": 0.9,
        },
    ).json()
    assert fb["score"] == 90
    m = client.get("/api/spaces/ml/concepts/hnsw/mastery").json()
    assert m["evidence_count"] == 1
    assert m["avg_retrieval_confidence"] == 0.9


def test_quiz_answer_ollama_down_503(client, monkeypatch):
    quiz = client.post("/api/spaces/ml/concepts/hnsw/quiz").json()
    qid = next(q["id"] for q in quiz["questions"] if q["type"] == "recall")

    from app.services.ollama_client import OllamaUnavailable

    async def down(self, prompt, *, model=None):
        raise OllamaUnavailable("down")

    monkeypatch.setattr(OllamaClient, "generate", down)
    r = client.post(
        f"/api/spaces/ml/quiz/{quiz['quiz_id']}/answer",
        json={"question_id": qid, "answer": "x", "confidence": 2},
    )
    assert r.status_code == 503


def test_generate_quiz_before_extraction_404(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARAI_DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    with TestClient(app) as c:
        c.post("/api/spaces", json={"name": "Empty"})
        assert c.post("/api/spaces/empty/concepts/hnsw/quiz").status_code == 404
    config.get_settings.cache_clear()
