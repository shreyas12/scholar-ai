"""Assessment + mastery REST API (Epic 6, SA-070–079).

Quiz lifecycle: generate a quiz for a concept → answer each question → each answer
is graded and appended to the event log. Mastery is read as a projection over
that log; it is never written directly.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import (
    AnswerFeedback,
    AnswerSubmit,
    ChatAnswerGrade,
    ConceptMastery,
    MasteryReport,
    Quiz,
)
from ..services import assessment as svc
from ..services import concepts as concepts_svc
from ..services import mastery as mastery_svc
from ..services.ollama_client import OllamaUnavailable
from ..services.spaces import SpaceNotFound

router = APIRouter(prefix="/api/spaces/{space_id}", tags=["assessment"])


@router.post("/concepts/{concept_id}/quiz", response_model=Quiz)
async def generate_quiz(space_id: str, concept_id: str) -> Quiz:
    try:
        return Quiz(**await svc.generate_quiz(space_id, concept_id))
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")
    except concepts_svc.ConceptNotFound as exc:
        raise HTTPException(404, str(exc) or f"Concept {concept_id!r} not found")
    except OllamaUnavailable as exc:
        raise HTTPException(503, str(exc))


@router.get("/quiz/{quiz_id}", response_model=Quiz)
def get_quiz(space_id: str, quiz_id: str) -> Quiz:
    try:
        return Quiz(**svc.get_quiz(space_id, quiz_id))
    except svc.QuizNotFound:
        raise HTTPException(404, f"Quiz {quiz_id!r} not found")


@router.post("/quiz/{quiz_id}/answer", response_model=AnswerFeedback)
async def submit_answer(space_id: str, quiz_id: str, body: AnswerSubmit) -> AnswerFeedback:
    try:
        result = await svc.submit_answer(
            space_id,
            quiz_id,
            body.question_id,
            body.answer,
            body.selected_index,
            body.confidence,
        )
        return AnswerFeedback(**result)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")
    except svc.QuizNotFound:
        raise HTTPException(404, f"Quiz {quiz_id!r} not found")
    except svc.QuestionNotFound:
        raise HTTPException(404, f"Question {body.question_id!r} not found")
    except OllamaUnavailable as exc:
        raise HTTPException(503, str(exc))


@router.post("/concepts/{concept_id}/grade-answer", response_model=AnswerFeedback)
async def grade_chat_answer(
    space_id: str, concept_id: str, body: ChatAnswerGrade
) -> AnswerFeedback:
    try:
        result = await svc.grade_chat_answer(
            space_id,
            concept_id,
            body.question,
            body.answer,
            body.confidence,
            body.retrieval_confidence,
        )
        return AnswerFeedback(**result)
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")
    except concepts_svc.ConceptNotFound:
        raise HTTPException(404, f"Concept {concept_id!r} not found")
    except OllamaUnavailable as exc:
        raise HTTPException(503, str(exc))


@router.get("/mastery", response_model=MasteryReport)
def mastery_report(space_id: str) -> MasteryReport:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)  # one clock for the whole report
    try:
        return MasteryReport(
            summary=mastery_svc.summary(space_id, now=now),
            concepts=mastery_svc.concept_records(space_id, now=now),
        )
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")


@router.get("/concepts/{concept_id}/mastery", response_model=ConceptMastery)
def concept_mastery(space_id: str, concept_id: str) -> ConceptMastery:
    try:
        records = {r.concept_id: r for r in mastery_svc.concept_records(space_id)}
    except SpaceNotFound:
        raise HTTPException(404, f"Space {space_id!r} not found")
    if concept_id not in records:
        raise HTTPException(404, f"Concept {concept_id!r} not found")
    return records[concept_id]
