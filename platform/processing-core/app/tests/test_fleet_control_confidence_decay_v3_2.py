from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.fleet_intelligence_actions import (
    FIActionCode,
    FIActionEffect,
    FIActionEffectLabel,
    FAppliedActionStatus,
    FIAppliedAction,
    FIInsight,
    FIInsightEntityType,
    FIInsightSeverity,
    FIInsightStatus,
    FIInsightType,
)
from app.models.unified_explain import PrimaryReason
from app.services.fleet_intelligence.control import confidence as control_confidence
from app.tests._fleet_intelligence_test_harness import FLEET_INTELLIGENCE_CONTROL_TEST_TABLES
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture()
def db_session() -> Session:
    with scoped_session_context(tables=FLEET_INTELLIGENCE_CONTROL_TEST_TABLES) as session:
        yield session


def _seed_effect(
    db: Session,
    *,
    insight: FIInsight,
    action_code: FIActionCode,
    measured_at: datetime,
    label: FIActionEffectLabel,
) -> None:
    applied = FIAppliedAction(
        insight_id=insight.id,
        action_code=action_code,
        applied_by="tester",
        applied_at=measured_at,
        reason_code="ACK",
        status=FAppliedActionStatus.SUCCESS,
    )
    db.add(applied)
    db.flush()
    effect = FIActionEffect(
        applied_action_id=applied.id,
        measured_at=measured_at,
        window_days=7,
        effect_label=label,
        summary="effect",
    )
    db.add(effect)


def test_confidence_decay_prefers_recent_improvements(db_session: Session):
    insight = FIInsight(
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id=str(uuid4()),
        window_days=7,
        severity=FIInsightSeverity.HIGH,
        status=FIInsightStatus.MONITORING,
        primary_reason=PrimaryReason.POLICY,
        summary="Driver risk",
    )
    db_session.add(insight)
    db_session.flush()
    now = datetime(2025, 1, 15, tzinfo=timezone.utc)
    _seed_effect(
        db_session,
        insight=insight,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        measured_at=now - timedelta(days=1),
        label=FIActionEffectLabel.IMPROVED,
    )
    _seed_effect(
        db_session,
        insight=insight,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        measured_at=now - timedelta(days=60),
        label=FIActionEffectLabel.WORSE,
    )
    _seed_effect(
        db_session,
        insight=insight,
        action_code=FIActionCode.SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL,
        measured_at=now - timedelta(days=60),
        label=FIActionEffectLabel.IMPROVED,
    )
    _seed_effect(
        db_session,
        insight=insight,
        action_code=FIActionCode.SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL,
        measured_at=now - timedelta(days=1),
        label=FIActionEffectLabel.WORSE,
    )
    db_session.commit()

    recent_improved = control_confidence.compute_action_confidence(
        db_session,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        now=now,
    )
    recent_worse = control_confidence.compute_action_confidence(
        db_session,
        action_code=FIActionCode.SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL,
        now=now,
    )
    assert recent_improved > recent_worse


def test_confidence_decay_drops_when_effects_outside_window(db_session: Session):
    insight = FIInsight(
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id=str(uuid4()),
        window_days=7,
        severity=FIInsightSeverity.HIGH,
        status=FIInsightStatus.MONITORING,
        primary_reason=PrimaryReason.POLICY,
        summary="Driver risk",
    )
    db_session.add(insight)
    db_session.flush()
    now = datetime(2025, 1, 15, tzinfo=timezone.utc)
    _seed_effect(
        db_session,
        insight=insight,
        action_code=FIActionCode.SUGGEST_EXCLUDE_STATION_FROM_ROUTES,
        measured_at=now - timedelta(days=120),
        label=FIActionEffectLabel.IMPROVED,
    )
    db_session.commit()

    confidence = control_confidence.compute_action_confidence(
        db_session,
        action_code=FIActionCode.SUGGEST_EXCLUDE_STATION_FROM_ROUTES,
        now=now,
    )
    assert confidence == 0.0


def test_confidence_decay_is_deterministic(db_session: Session):
    insight = FIInsight(
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id=str(uuid4()),
        window_days=7,
        severity=FIInsightSeverity.HIGH,
        status=FIInsightStatus.MONITORING,
        primary_reason=PrimaryReason.POLICY,
        summary="Driver risk",
    )
    db_session.add(insight)
    db_session.flush()
    now = datetime(2025, 1, 15, tzinfo=timezone.utc)
    _seed_effect(
        db_session,
        insight=insight,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        measured_at=now - timedelta(days=10),
        label=FIActionEffectLabel.IMPROVED,
    )
    db_session.commit()

    first = control_confidence.compute_action_confidence(
        db_session,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        now=now,
    )
    second = control_confidence.compute_action_confidence(
        db_session,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        now=now,
    )
    assert first == second
