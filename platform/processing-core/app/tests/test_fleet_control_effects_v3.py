from datetime import datetime, timedelta, timezone
from typing import Tuple
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.crm import CRMClient, CRMClientStatus
from app.models.fleet_intelligence import DriverBehaviorLevel, FIDriverScore
from app.models.fleet_intelligence_actions import (
    FIActionCode,
    FAppliedActionStatus,
    FIAppliedAction,
    FIInsight,
    FIInsightEntityType,
    FIInsightSeverity,
    FIInsightStatus,
    FIInsightType,
)
from app.models.unified_explain import PrimaryReason
from app.services.fleet_intelligence.control import effects, repository


@pytest.fixture()
def db_session() -> Tuple[Session, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session, SessionLocal
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed_client(db: Session) -> CRMClient:
    client = CRMClient(
        id="client-1",
        tenant_id=1,
        legal_name="Client",
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
    db.add(client)
    db.commit()
    return client


def test_effect_measurement_label(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    _seed_client(db)
    driver_id = str(uuid4())
    insight = FIInsight(
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id=driver_id,
        window_days=7,
        severity=FIInsightSeverity.HIGH,
        status=FIInsightStatus.MONITORING,
        primary_reason=PrimaryReason.POLICY,
    )
    db.add(insight)
    db.flush()
    applied = FIAppliedAction(
        insight_id=insight.id,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        applied_by="tester",
        applied_at=datetime.now(timezone.utc) - timedelta(days=8),
        reason_code="ACK_IN_REVIEW",
        reason_text="apply",
        before_state={"driver_score_7d": 80},
        status=FAppliedActionStatus.SUCCESS,
    )
    db.add(applied)
    db.add(
        FIDriverScore(
            tenant_id=1,
            client_id="client-1",
            driver_id=driver_id,
            computed_at=datetime.now(timezone.utc),
            window_days=7,
            score=55,
            level=DriverBehaviorLevel.MEDIUM,
        )
    )
    db.commit()

    results = effects.measure_action_effects(db, as_of=datetime.now(timezone.utc))
    db.commit()

    assert results
    effect = repository.list_action_effects(db, applied_action_id=str(applied.id))[0]
    assert effect.effect_label.value == "IMPROVED"
