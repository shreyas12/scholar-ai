"""Unit tests for the mastery projection formula (SA-079).

The formula is the one place we tune, so its pieces are pinned here as pure,
deterministic functions — no I/O, no clock. Full event→projection flow is
exercised in test_assessment.py.
"""

import pytest

from app.services import mastery


def test_blend_weights_application_highest():
    # Same score everywhere → blend is that score regardless of weights.
    assert mastery.blend({"recall": 80, "recognition": 80, "application": 80}) == pytest.approx(80)


def test_blend_renormalizes_over_present_signals():
    # Only recall present → blend is just the recall average (no penalty for the
    # signals that were never tested).
    assert mastery.blend({"recall": 60}) == pytest.approx(60)


def test_blend_application_dominates():
    # Strong application, weak recognition → weighted toward application (0.50 vs 0.15).
    score = mastery.blend({"recognition": 0, "application": 100})
    assert score > 70  # 0.50/(0.50+0.15) * 100 ≈ 76.9


def test_blend_empty_is_zero():
    assert mastery.blend({}) == 0.0


def test_confidence_modifier_penalizes_misconceptions():
    assert mastery.confidence_modifier(80, 0) == 80.0
    assert mastery.confidence_modifier(80, 1) == 76.0  # -5%
    assert mastery.confidence_modifier(80, 10) == 64.0  # capped at -20%


def test_confidence_modifier_floors_at_zero():
    assert mastery.confidence_modifier(0, 5) == 0.0


def test_buckets():
    assert mastery.bucket(None) == "unknown"
    assert mastery.bucket(10) == "weak"
    assert mastery.bucket(40) == "learning"
    assert mastery.bucket(74) == "learning"
    assert mastery.bucket(75) == "mastered"
    assert mastery.bucket(100) == "mastered"
