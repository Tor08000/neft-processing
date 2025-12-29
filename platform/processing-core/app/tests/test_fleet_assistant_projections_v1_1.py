from __future__ import annotations

from app.services.fleet_assistant.projections import build_outcome_projection


def test_projection_applied_improved_label() -> None:
    projection = build_outcome_projection(
        confidence=0.72,
        sample_size=30,
        trend_label="DEGRADING",
        entity_type="DRIVER",
        sla_remaining_minutes=900,
        aging_days=2,
        insight_status="OPEN",
        half_life_days=30,
    )

    assert projection.if_applied.probability_improved_pct == 72
    assert projection.if_applied.expected_effect_label == "IMPROVED"


def test_projection_applied_no_change_label() -> None:
    projection = build_outcome_projection(
        confidence=0.40,
        sample_size=12,
        trend_label="STABLE",
        entity_type="DRIVER",
        sla_remaining_minutes=None,
        aging_days=None,
        insight_status=None,
        half_life_days=30,
    )

    assert projection.if_applied.expected_effect_label == "NO_CHANGE"


def test_projection_applied_worse_label() -> None:
    projection = build_outcome_projection(
        confidence=0.10,
        sample_size=5,
        trend_label="STABLE",
        entity_type="DRIVER",
        sla_remaining_minutes=None,
        aging_days=None,
        insight_status=None,
        half_life_days=30,
    )

    assert projection.if_applied.expected_effect_label == "WORSE"


def test_projection_ignored_degrading_escalation() -> None:
    projection = build_outcome_projection(
        confidence=0.50,
        sample_size=5,
        trend_label="DEGRADING",
        entity_type="DRIVER",
        sla_remaining_minutes=360,
        aging_days=9,
        insight_status="OPEN",
        half_life_days=30,
    )

    assert projection.if_ignored.probability_worse_pct > 40
    assert projection.if_ignored.escalation_risk.likely is True


def test_projection_ignored_improving_baseline() -> None:
    projection = build_outcome_projection(
        confidence=0.50,
        sample_size=5,
        trend_label="IMPROVING",
        entity_type="DRIVER",
        sla_remaining_minutes=None,
        aging_days=None,
        insight_status="OPEN",
        half_life_days=30,
    )

    assert projection.if_ignored.probability_worse_pct == 10


def test_projection_deterministic() -> None:
    params = dict(
        confidence=0.55,
        sample_size=8,
        trend_label="STABLE",
        entity_type="DRIVER",
        sla_remaining_minutes=300,
        aging_days=11,
        insight_status="OPEN",
        half_life_days=30,
    )
    first = build_outcome_projection(**params)
    second = build_outcome_projection(**params)

    assert first.model_dump() == second.model_dump()
