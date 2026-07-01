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

from datetime import datetime, timedelta, timezone
from math import exp, log

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

# --- Retention (SA-081) ------------------------------------------------------
# A forgetting curve R = exp(-Δt / stability): memory of a correctly-recalled
# concept decays with time since the last correct recall, but *stability* grows
# with every successful review (spaced-repetition intuition) so well-practiced
# concepts decay slower. Per PLAN §7b, decay is computed on read from event
# timestamps — mastery is retention-aware without ever being mutated.
BASE_STABILITY_DAYS = 3.0  # a single correct recall keeps a concept "fresh" for days
REVIEW_THRESHOLD = 0.7  # once retention would fall below this, a review is due
# A decayed concept never drops below this fraction of its demonstrated score —
# forgetting dulls but doesn't erase evidence you once produced.
RETENTION_FLOOR = 0.6


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def stability_days(correct_count: int, demonstrated: float) -> float:
    """Days for retention to reach ~37% (1/e). Grows with practice + competence."""
    return BASE_STABILITY_DAYS * (1 + max(0, correct_count)) * (0.5 + demonstrated / 100)


def retention_estimate(last_correct: datetime | None, stability: float, now: datetime) -> float:
    """Fraction of a concept still retained now (0-1). 0 if never recalled correctly."""
    if last_correct is None:
        return 0.0
    dt_days = max(0.0, (now - last_correct).total_seconds() / 86400)
    return round(exp(-dt_days / stability), 3)


def next_review_date(last_correct: datetime | None, stability: float) -> str | None:
    """When retention would decay to REVIEW_THRESHOLD — the moment to review."""
    if last_correct is None:
        return None
    delta_days = -stability * log(REVIEW_THRESHOLD)
    return (last_correct + timedelta(days=delta_days)).isoformat()


def retention_factor(retention: float) -> float:
    """Map retention (0-1) to a mastery multiplier floored at RETENTION_FLOOR."""
    return RETENTION_FLOOR + (1 - RETENTION_FLOOR) * retention


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


def _project_concept(
    concept_id: str, label: str, coverage: bool, evs: list[dict], now: datetime
) -> ConceptMastery:
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
    # Demonstrated competence: what the evidence proves, independent of time.
    demonstrated = confidence_modifier(base, misconceptions)

    correct_ts = [_parse_ts(e.get("ts")) for e in evs if e.get("correct")]
    correct_ts = [t for t in correct_ts if t is not None]
    correct_count = len(correct_ts)
    last_correct = max(correct_ts) if correct_ts else None
    all_ts = [t for t in (_parse_ts(e.get("ts")) for e in evs) if t is not None]

    # SA-081: retention decays from the last correct recall; fold it into the
    # score on read (PLAN §7b) so a long-unpractised concept slips buckets.
    stability = stability_days(correct_count, demonstrated)
    retention = retention_estimate(last_correct, stability, now)
    mastery = round(demonstrated * retention_factor(retention), 1)
    next_review = next_review_date(last_correct, stability)
    review_due = last_correct is not None and retention < REVIEW_THRESHOLD

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
        last_correct=last_correct.isoformat() if last_correct else None,
        avg_confidence=round(_mean([float(c) for c in confidences]), 1) if confidences else None,
        avg_retrieval_confidence=round(_mean([float(r) for r in retr]), 2) if retr else None,
        demonstrated=demonstrated,
        retention=retention if last_correct else None,
        last_reviewed=max(all_ts).isoformat() if all_ts else None,
        next_review=next_review,
        review_due=review_due,
    )


def concept_records(space_id: str, now: datetime | None = None) -> list[ConceptMastery]:
    """Rich per-concept mastery records (SA-084), projected from the event log.

    ``now`` is injectable so retention is deterministic in tests; it defaults to
    the current UTC time and is shared across the whole report for consistency.
    """
    get_space(space_id)
    now = now or datetime.now(timezone.utc)
    data = concepts_svc.load_concepts(space_id)
    concepts = data.get("concepts", {})
    encountered = progress_svc.encountered_ids(space_id)

    all_events = events_svc.load(space_id)
    by_concept: dict[str, list[dict]] = {}
    for e in all_events:
        by_concept.setdefault(e.get("concept_id"), []).append(e)

    out = [
        _project_concept(cid, node["label"], cid in encountered, by_concept.get(cid, []), now)
        for cid, node in concepts.items()
    ]
    # Weakest evidence-bearing concepts first — that's what a learner should act on.
    order = {"weak": 0, "learning": 1, "mastered": 2, "unknown": 3}
    out.sort(key=lambda c: (order[c.bucket], c.mastery if c.mastery is not None else 0, c.label.lower()))
    return out


def summary(space_id: str, now: datetime | None = None) -> MasterySummary:
    """Space-level rollup (SA-083): overall mastery + bucket counts."""
    records = concept_records(space_id, now=now)
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
