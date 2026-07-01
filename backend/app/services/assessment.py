"""Assessment: question generation + grading (Epic 6, SA-070–077).

Turns a concept into *evidence*. Two halves:

* **Generation (SA-070)** — one LLM pass per concept produces a recall (explain),
  a recognition (MCQ), and an application (scenario) question, grounded strictly
  in that concept's source material. The quiz is persisted server-side with its
  answer keys; the client only ever sees the questions.
* **Grading** — recognition is graded **deterministically** (SA-072) against the
  stored key; recall/application go through the LLM-judge (SA-071) with the
  ``grading`` prompt. Every graded answer becomes an immutable event (SA-074/078)
  carrying the self-reported confidence (SA-073) and any misconception (SA-075).

Quizzes live in ``quizzes.json`` (``{quiz_id: record}``). The stored record keeps
``ideal_answer`` / ``answer_index`` / ``reference`` per question; those are
stripped before the quiz is returned to the client.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .. import storage
from ..prompts import load_prompt
from . import concepts as concepts_svc
from . import events as events_svc
from . import vectorstore
from .ollama_client import OllamaClient, OllamaUnavailable
from .spaces import get_space

# Cap the reference material fed to generation/grading so a huge concept doesn't
# blow the context window; the most relevant sections come first anyway.
MAX_REF_CHARS = 4000
VALID_TYPES = {"recall", "recognition", "application"}
FREE_TEXT_TYPES = {"recall", "application"}


class QuizNotFound(Exception):
    pass


class QuestionNotFound(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quizzes_path(space_id: str) -> Path:
    return storage.space_layout(space_id)["root"] / "quizzes.json"


def _load_quizzes(space_id: str) -> dict[str, dict]:
    return storage.read_json(_quizzes_path(space_id), default={})


def _concept_reference(space_id: str, concept_id: str) -> tuple[str, str]:
    """(label, reference text) for a concept, gathered from its source sections."""
    data = concepts_svc.load_concepts(space_id)
    node = data.get("concepts", {}).get(concept_id)
    if node is None:
        raise concepts_svc.ConceptNotFound(concept_id)
    sections = vectorstore.load_all_sections(space_id)
    texts = [
        sections[s]["text"]
        for s in node.get("source_sections", [])
        if s in sections and sections[s].get("text")
    ]
    reference = "\n\n".join(texts)[:MAX_REF_CHARS]
    return node["label"], reference


def parse_questions(raw: str) -> list[dict]:
    """Best-effort parse of the generator's JSON array into validated questions."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        arr = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(arr, list):
        return []

    out: list[dict] = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        qtype = str(item.get("type", "")).strip().lower()
        question = str(item.get("question", "")).strip()
        if qtype not in VALID_TYPES or not question:
            continue
        if qtype == "recognition":
            options = item.get("options")
            idx = item.get("answer_index")
            if (
                not isinstance(options, list)
                or len(options) < 2
                or not isinstance(idx, int)
                or not (0 <= idx < len(options))
            ):
                continue
            out.append(
                {
                    "type": qtype,
                    "question": question,
                    "options": [str(o).strip() for o in options],
                    "answer_index": idx,
                }
            )
        else:
            out.append(
                {
                    "type": qtype,
                    "question": question,
                    "ideal_answer": str(item.get("ideal_answer", "")).strip(),
                }
            )
    return out


async def generate_quiz(space_id: str, concept_id: str) -> dict:
    """Generate + persist a quiz for one concept. Returns the client-safe quiz.

    Raises ``SpaceNotFound`` / ``ConceptNotFound`` / ``OllamaUnavailable``.
    """
    get_space(space_id)
    label, reference = _concept_reference(space_id, concept_id)
    if not reference:
        raise concepts_svc.ConceptNotFound(
            f"{concept_id!r} has no source material to build a quiz from"
        )

    prompt = load_prompt("question_gen")
    client = OllamaClient()
    raw = await client.generate(prompt.render(concept=label, reference=reference))
    parsed = parse_questions(raw)
    if not parsed:
        raise OllamaUnavailable("The model did not return any usable questions.")

    questions: list[dict] = []
    for i, q in enumerate(parsed):
        stored = {"id": f"q{i}", "reference": reference, **q}
        questions.append(stored)

    quiz_id = uuid.uuid4().hex[:12]
    record = {
        "quiz_id": quiz_id,
        "concept_id": concept_id,
        "concept_label": label,
        "created_at": _now(),
        "prompt_version": prompt.version,
        "questions": questions,
    }
    quizzes = _load_quizzes(space_id)
    quizzes[quiz_id] = record
    storage.write_json(_quizzes_path(space_id), quizzes)
    return _client_quiz(record)


def _client_quiz(record: dict) -> dict:
    """Strip answer keys / reference before sending a quiz to the client."""
    return {
        "quiz_id": record["quiz_id"],
        "concept_id": record["concept_id"],
        "concept_label": record["concept_label"],
        "questions": [
            {
                "id": q["id"],
                "type": q["type"],
                "question": q["question"],
                "options": q.get("options"),
            }
            for q in record["questions"]
        ],
    }


def get_quiz(space_id: str, quiz_id: str) -> dict:
    record = _load_quizzes(space_id).get(quiz_id)
    if record is None:
        raise QuizNotFound(quiz_id)
    return _client_quiz(record)


def parse_grade(raw: str) -> dict:
    """Parse the LLM-judge JSON. Falls back to an ungraded-but-safe default."""
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            obj = {}
    else:
        obj = {}
    score = obj.get("score")
    if not isinstance(score, (int, float)):
        score = 0
    score = int(max(0, min(100, score)))
    misconception = obj.get("misconception")
    if not isinstance(misconception, str) or not misconception.strip():
        misconception = None
    return {
        "correct": bool(obj.get("correct", score >= 60)),
        "score": score,
        "reasoning": str(obj.get("reasoning", "")).strip() or "No explanation provided.",
        "misconception": misconception,
    }


async def grade_free_text(
    concept_label: str, question: str, reference: str, answer: str
) -> dict:
    """LLM-judge a free-text answer (SA-071). Raises ``OllamaUnavailable``."""
    prompt = load_prompt("grading")
    client = OllamaClient()
    raw = await client.generate(
        prompt.render(
            concept=concept_label, question=question, reference=reference, answer=answer
        )
    )
    result = parse_grade(raw)
    result["prompt_version"] = prompt.version
    return result


def _grade_recognition(question: dict, selected_index: int | None) -> dict:
    """Deterministic MCQ grade (SA-072)."""
    correct_index = question["answer_index"]
    options = question["options"]
    correct = selected_index == correct_index
    right = options[correct_index] if 0 <= correct_index < len(options) else "?"
    chosen = (
        options[selected_index]
        if isinstance(selected_index, int) and 0 <= selected_index < len(options)
        else "(no selection)"
    )
    return {
        "correct": correct,
        "score": 100 if correct else 0,
        "reasoning": (
            "Correct." if correct else f"You chose “{chosen}”; the answer is “{right}”."
        ),
        "misconception": None if correct else f"Believes the answer is “{chosen}”",
        "correct_answer": right,
        "prompt_version": "deterministic",
    }


async def submit_answer(
    space_id: str, quiz_id: str, question_id: str, answer: str, selected_index: int | None, confidence: int
) -> dict:
    """Grade one answer, record an event, and return feedback (SA-072/074/075)."""
    get_space(space_id)
    record = _load_quizzes(space_id).get(quiz_id)
    if record is None:
        raise QuizNotFound(quiz_id)
    question = next((q for q in record["questions"] if q["id"] == question_id), None)
    if question is None:
        raise QuestionNotFound(question_id)

    if question["type"] == "recognition":
        graded = _grade_recognition(question, selected_index)
        answer_text = (
            question["options"][selected_index]
            if isinstance(selected_index, int) and 0 <= selected_index < len(question["options"])
            else ""
        )
    else:
        reference = question.get("reference", "")
        if question.get("ideal_answer"):
            reference = f"Ideal answer: {question['ideal_answer']}\n\n{reference}"
        graded = await grade_free_text(
            record["concept_label"], question["question"], reference, answer
        )
        graded["correct_answer"] = question.get("ideal_answer") or None
        answer_text = answer

    event = events_svc.append(
        space_id,
        concept_id=record["concept_id"],
        type=question["type"],
        source="quiz",
        question=question["question"],
        answer=answer_text,
        correct=graded["correct"],
        score=graded["score"],
        confidence=confidence,
        misconception=graded.get("misconception"),
        prompt_version=graded["prompt_version"],
    )
    return {**graded, "misconception_flag": event["misconception_flag"]}


async def grade_chat_answer(
    space_id: str,
    concept_id: str,
    question: str,
    answer: str,
    confidence: int,
    retrieval_confidence: float | None = None,
) -> dict:
    """Chat-as-evidence hook (SA-077): grade a chat answer against a concept.

    Treated as recall evidence and recorded with ``source="chat"`` so it flows
    into the same event-driven mastery projection as quiz answers.
    """
    get_space(space_id)
    label, reference = _concept_reference(space_id, concept_id)
    graded = await grade_free_text(label, question, reference, answer)
    event = events_svc.append(
        space_id,
        concept_id=concept_id,
        type="recall",
        source="chat",
        question=question,
        answer=answer,
        correct=graded["correct"],
        score=graded["score"],
        confidence=confidence,
        misconception=graded.get("misconception"),
        retrieval_confidence=retrieval_confidence,
        prompt_version=graded["prompt_version"],
    )
    return {**graded, "misconception_flag": event["misconception_flag"]}
