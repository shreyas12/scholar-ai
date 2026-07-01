"""Mastery as a projection over the event log (SA-079, PLAN §7 / §7b).

Mastery is **never mutated directly**. This module recomputes each concept's
mastery from the immutable event log (:mod:`app.services.events`) on read, so the
formula lives in exactly one place and can be tuned + replayed without losing
evidence. Epic 7 will refine the weights / add retention decay; the *shape* — a
weighted blend of recall/recognition/application, modulated by confidence — is
fixed here and unit-tested.

Per PLAN §7:

| Signal      | Source                          | Weight |
|-------------|---------------------------------|--------|
| Recall      | free explanation, LLM-graded    | high   |
| Recognition | MCQ / true-false                | low    |
| Application | scenario, LLM-graded            | highest|
| Confidence  | self-report 1-5 vs correctness  | modifier |

Coverage (encountered) gates but does not score. Buckets for the dashboard:
Mastered / Learning / Weak / Unknown.
"""

from __future__ import annotations

from ..models import ConceptMastery, MasterySummary
from . import concepts as concepts_svc
from . import events as events_svc
from . import progress as progress_svc
from .spaces import get_space

# Signal weights (PLAN §7). Application demonstrates transfer, so it counts most;
# recognition is the weakest evidence of real understanding. Renormalized over
# whichever signals actually have evidence, so a concept with only recall isn't
# penalized for the missing signals.
SIGNAL_WEIGHTS = {"recall": 0.35, "recognition": 0.15, "application": 0.50}

# Bucket thresholds on the 0-100 mastery score.
MASTERED_AT = 75
LEARNING_AT = 40


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def blend(signal_scores: dict[str, float]) -> float:
    """Weighted blend of present signal averages → 0-100. Pure + testable.

    ``signal_scores`` maps signal name → mean score (0-100) for signals that have
    at least one event. Weights are renormalized over the present signals.
    """
    present = {k: v for k, v in signal_scores.items() if k in SIGNAL_WEIGHTS}
    if not present:
        return 0.0
    total_w = sum(SIGNAL_WEIGHTS[k] for k in present)
    return sum(SIGNAL_WEIGHTS[k] * v for k, v in present.items()) / total_w


def confidence_modifier(base: float, misconception_count: int) -> float:
    """Nudge the blended score by calibration evidence (PLAN §7).

    A confidently-wrong answer (misconception) signals a belief that will resist
    correction, so each one shaves a little off the score — bounded and floored
    at 0. Correct answers already raise the blend, so no upward nudge is needed.
    """
    penalty = min(0.20, 0.05 * misconception_count)  # cap at 20%
    return round(max(0.0, base * (1 - penalty)), 1)


def bucket(mastery: float | None) -> str:
    if mastery is None:
        return "unknown"
    if mastery >= MASTERED_AT:
        return "mastered"
    if mastery >= LEARNING_AT:
        return "learning"
    return "weak"


def _project_concept(concept_id: str, label: str, coverage: bool, evs: list[dict]) -> ConceptMastery:
    if not evs:
        return ConceptMastery(
            concept_id=concept_id,
            label=label,
            mastery=None,
            bucket="unknown",
            evidence_count=0,
            coverage=coverage,
            recall=None,
            recognition=None,
            application=None,
            misconceptions=0,
            last_correct=None,
            avg_confidence=None,
            avg_retrieval_confidence=None,
        )

    by_signal: dict[str, list[float]] = {"recall": [], "recognition": [], "application": []}
    for e in evs:
        if e.get("type") in by_signal:
            by_signal[e["type"]].append(float(e.get("score", 0)))

    signal_scores = {k: _mean(v) for k, v in by_signal.items() if v}
    misconceptions = sum(1 for e in evs if e.get("misconception_flag"))
    base = blend(signal_scores)
    mastery = confidence_modifier(base, misconceptions)

    correct_ts = [e["ts"] for e in evs if e.get("correct") and e.get("ts")]
    confidences = [e["confidence"] for e in evs if isinstance(e.get("confidence"), int)]
    retr = [e["retrieval_confidence"] for e in evs if isinstance(e.get("retrieval_confidence"), (int, float))]

    return ConceptMastery(
        concept_id=concept_id,
        label=label,
        mastery=mastery,
        bucket=bucket(mastery),
        evidence_count=len(evs),
        coverage=coverage,
        recall=round(signal_scores["recall"], 1) if "recall" in signal_scores else None,
        recognition=round(signal_scores["recognition"], 1) if "recognition" in signal_scores else None,
        application=round(signal_scores["application"], 1) if "application" in signal_scores else None,
        misconceptions=misconceptions,
        last_correct=max(correct_ts) if correct_ts else None,
        avg_confidence=round(_mean([float(c) for c in confidences]), 1) if confidences else None,
        avg_retrieval_confidence=round(_mean([float(r) for r in retr]), 2) if retr else None,
    )


def concept_records(space_id: str) -> list[ConceptMastery]:
    """Rich per-concept mastery records (SA-084), projected from the event log."""
    get_space(space_id)
    data = concepts_svc.load_concepts(space_id)
    concepts = data.get("concepts", {})
    encountered = progress_svc.encountered_ids(space_id)

    all_events = events_svc.load(space_id)
    by_concept: dict[str, list[dict]] = {}
    for e in all_events:
        by_concept.setdefault(e.get("concept_id"), []).append(e)

    out = [
        _project_concept(cid, node["label"], cid in encountered, by_concept.get(cid, []))
        for cid, node in concepts.items()
    ]
    # Weakest evidence-bearing concepts first — that's what a learner should act on.
    order = {"weak": 0, "learning": 1, "mastered": 2, "unknown": 3}
    out.sort(key=lambda c: (order[c.bucket], c.mastery if c.mastery is not None else 0, c.label.lower()))
    return out


def summary(space_id: str) -> MasterySummary:
    """Space-level rollup (SA-083): overall mastery + bucket counts."""
    records = concept_records(space_id)
    scored = [r.mastery for r in records if r.mastery is not None]
    counts = {"mastered": 0, "learning": 0, "weak": 0, "unknown": 0}
    for r in records:
        counts[r.bucket] += 1
    return MasterySummary(
        total_concepts=len(records),
        assessed=len(scored),
        overall_mastery=round(_mean(scored), 1) if scored else None,
        mastered=counts["mastered"],
        learning=counts["learning"],
        weak=counts["weak"],
        unknown=counts["unknown"],
    )
