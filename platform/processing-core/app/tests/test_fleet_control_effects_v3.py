from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

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
from app.tests._fleet_intelligence_test_harness import FLEET_INTELLIGENCE_CONTROL_TEST_TABLES
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture()
def db_session() -> Session:
    with scoped_session_context(tables=FLEET_INTELLIGENCE_CONTROL_TEST_TABLES) as session:
        yield session


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


def test_effect_measurement_label(db_session: Session):
    _seed_client(db_session)
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
    db_session.add(insight)
    db_session.flush()
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
    db_session.add(applied)
    db_session.add(
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
    db_session.commit()

    results = effects.measure_action_effects(db_session, as_of=datetime.now(timezone.utc))
    db_session.commit()

    assert results
    effect = repository.list_action_effects(db_session, applied_action_id=str(applied.id))[0]
    assert effect.effect_label.value == "IMPROVED"
