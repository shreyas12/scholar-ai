"""Pydantic request/response schemas shared across routers."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Spaces ------------------------------------------------------------------

class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SpaceRename(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class Space(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    document_count: int = 0


# --- Documents ---------------------------------------------------------------

class Document(BaseModel):
    doc_id: str
    name: str
    ext: str
    size: int
    checksum: str
    uploaded_at: str
    chunk_count: int = 0
    status: str = "ready"  # ready | processing | error
    reused: bool = False  # true when an identical upload was a no-op


# --- Concepts / coverage -----------------------------------------------------

class Concept(BaseModel):
    id: str
    label: str
    source_chunk_count: int
    encountered: bool = False


class CoverageStats(BaseModel):
    total: int
    encountered: int
    coverage_pct: float


class ExtractResult(BaseModel):
    total_concepts: int
    sources_processed: int
    prompt_version: str


# --- Concept graph (Epic 5) --------------------------------------------------

class GraphNode(BaseModel):
    id: str
    label: str
    encountered: bool = False
    ready: bool = False  # all prerequisites encountered (SA-063)


class GraphEdge(BaseModel):
    source: str  # prerequisite concept id
    target: str  # concept that depends on it


class ConceptGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ConceptDetail(BaseModel):
    id: str
    label: str
    encountered: bool
    prerequisites: list[str]  # labels
    source_sections: list[str]


# --- Assessment (Epic 6) -----------------------------------------------------

class QuizQuestion(BaseModel):
    """A single question as sent to the client — no answer key leaked."""

    id: str
    type: str  # recall | recognition | application
    question: str
    options: list[str] | None = None  # present for recognition (MCQ) only


class Quiz(BaseModel):
    quiz_id: str
    concept_id: str
    concept_label: str
    questions: list[QuizQuestion]


class AnswerSubmit(BaseModel):
    question_id: str
    answer: str = ""  # free-text answer (recall / application)
    selected_index: int | None = None  # chosen option (recognition)
    confidence: int = Field(ge=1, le=5)  # self-report (SA-073)


class AnswerFeedback(BaseModel):
    correct: bool
    score: int  # 0-100
    reasoning: str
    misconception: str | None = None
    misconception_flag: bool = False  # incorrect + high confidence (SA-075)
    correct_answer: str | None = None


class ChatAnswerGrade(BaseModel):
    """Grade a chat answer against a concept as evidence (SA-077)."""

    question: str
    answer: str
    confidence: int = Field(ge=1, le=5)
    retrieval_confidence: float | None = None


# --- Mastery projection (Epic 6/7) -------------------------------------------

class ConceptMastery(BaseModel):
    concept_id: str
    label: str
    mastery: float | None = None  # 0-100, None = no evidence yet
    bucket: str  # mastered | learning | weak | unknown
    evidence_count: int = 0
    coverage: bool = False
    recall: float | None = None
    recognition: float | None = None
    application: float | None = None
    misconceptions: int = 0
    last_correct: str | None = None
    avg_confidence: float | None = None
    avg_retrieval_confidence: float | None = None
    # Retention (SA-081): decay-based estimate + scheduling, computed on read.
    demonstrated: float | None = None  # mastery before retention decay
    retention: float | None = None  # 0-1, fraction retained since last correct recall
    last_reviewed: str | None = None
    next_review: str | None = None
    review_due: bool = False


class MasterySummary(BaseModel):
    total_concepts: int
    assessed: int
    overall_mastery: float | None = None
    mastered: int = 0
    learning: int = 0
    weak: int = 0
    unknown: int = 0


class MasteryReport(BaseModel):
    summary: MasterySummary
    concepts: list[ConceptMastery]
