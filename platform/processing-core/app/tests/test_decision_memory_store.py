from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db import Base
from app.db.types import new_uuid_str
from app.models.fleet_intelligence_actions import (
    FAppliedActionStatus,
    FIActionCode,
    FIActionEffect,
    FIActionEffectLabel,
    FIAppliedAction,
    FIInsight,
    FIInsightEntityType,
    FIInsightSeverity,
    FIInsightStatus,
    FIInsightType,
)
from app.models.unified_explain import PrimaryReason
from app.services.decision_memory import repository as memory_repository
from app.services.decision_memory import store as memory_store


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_outcome_recorded_once(db_session: Session) -> None:
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    insight = FIInsight(
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id=new_uuid_str(),
        window_days=7,
        severity=FIInsightSeverity.MEDIUM,
        status=FIInsightStatus.ACTION_APPLIED,
        primary_reason=PrimaryReason.LOGISTICS,
    )
    db_session.add(insight)
    db_session.commit()

    action = FIAppliedAction(
        insight_id=insight.id,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        applied_at=now,
        reason_code="MANUAL",
        status=FAppliedActionStatus.SUCCESS,
    )
    db_session.add(action)
    db_session.commit()

    effect = FIActionEffect(
        applied_action_id=action.id,
        measured_at=now,
        window_days=7,
        effect_label=FIActionEffectLabel.NO_CHANGE,
        summary="No material change detected.",
    )

    first = memory_store.record_outcome_from_effect(db_session, action=action, insight=insight, effect=effect)
    second = memory_store.record_outcome_from_effect(db_session, action=action, insight=insight, effect=effect)
    db_session.commit()

    assert first.id == second.id
    outcomes = memory_repository.list_outcomes_for_entity(
        db_session,
        entity_type=first.entity_type,
        entity_id=first.entity_id,
        limit=10,
    )
    assert len(outcomes) == 1
