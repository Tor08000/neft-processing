from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.crm import CRMClient, CRMClientStatus
from app.models.fleet_intelligence import DriverBehaviorLevel, FIDriverScore
from app.models.fleet_intelligence_actions import (
    FIActionCode,
    FIActionTargetSystem,
    FAppliedActionStatus,
    FIInsight,
    FIInsightEntityType,
    FIInsightSeverity,
    FIInsightStatus,
    FIInsightType,
    FISuggestedAction,
    FISuggestedActionStatus,
)
from app.models.unified_explain import PrimaryReason
from app.services.fleet_intelligence.control import actions, policies, repository
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


def _seed_insight(db: Session) -> FIInsight:
    insight = FIInsight(
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id=str(uuid4()),
        window_days=7,
        severity=FIInsightSeverity.HIGH,
        status=FIInsightStatus.OPEN,
        primary_reason=PrimaryReason.POLICY,
        summary="Driver behavior degrading",
    )
    db.add(insight)
    db.commit()
    return insight


def test_policy_mapping_stable():
    insight = FIInsight(
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id=str(uuid4()),
        window_days=7,
        severity=FIInsightSeverity.HIGH,
        status=FIInsightStatus.OPEN,
        primary_reason=PrimaryReason.POLICY,
    )
    actions_list = policies.suggest_actions_for_insight(insight)
    assert actions_list
    assert actions_list[0].target_system == FIActionTargetSystem.CRM


def test_apply_requires_reason_code(db_session: Session):
    _seed_client(db_session)
    insight = _seed_insight(db_session)
    action = FISuggestedAction(
        insight_id=insight.id,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        target_system=FIActionTargetSystem.CRM,
        payload={"feature_flag": "RISK_BLOCKING_ENABLED", "enabled": True},
        status=FISuggestedActionStatus.APPROVED,
    )
    db_session.add(action)
    db_session.commit()

    with pytest.raises(ValueError):
        actions.apply_suggested_action(
            db_session,
            action=action,
            reason_code="",
            reason_text=None,
            actor="tester",
        )


def test_apply_records_before_state(db_session: Session):
    _seed_client(db_session)
    insight = _seed_insight(db_session)
    db_session.add(
        FIDriverScore(
            tenant_id=1,
            client_id="client-1",
            driver_id=str(insight.entity_id),
            computed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            window_days=7,
            score=70,
            level=DriverBehaviorLevel.HIGH,
        )
    )
    action = FISuggestedAction(
        insight_id=insight.id,
        action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        target_system=FIActionTargetSystem.CRM,
        payload={"feature_flag": "RISK_BLOCKING_ENABLED", "enabled": True},
        status=FISuggestedActionStatus.APPROVED,
    )
    db_session.add(action)
    db_session.commit()

    applied = actions.apply_suggested_action(
        db_session,
        action=action,
        reason_code="ACK_IN_REVIEW",
        reason_text="apply",
        actor="tester",
    )
    db_session.commit()

    assert applied.status in {FAppliedActionStatus.SUCCESS, FAppliedActionStatus.FAILED}
    assert applied.before_state
    assert "driver_score_7d" in applied.before_state
    assert repository.list_applied_actions(db_session, insight_id=str(insight.id))
