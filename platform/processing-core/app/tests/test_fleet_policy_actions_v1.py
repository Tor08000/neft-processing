from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models.cases import Case, CaseComment, CaseEvent, CaseEventType, CaseSnapshot
from app.models.decision_memory import DecisionMemoryRecord
from app.models.fleet import FuelCardGroupMember
from app.models.fuel import (
    FleetActionBreachKind,
    FleetActionPolicy,
    FleetActionPolicyAction,
    FleetActionPolicyScopeType,
    FleetActionTriggerType,
    FleetNotificationOutbox,
    FleetNotificationOutboxStatus,
    FleetNotificationSeverity,
    FleetPolicyExecution,
    FleetPolicyExecutionStatus,
    FuelAnomaly,
    FuelAnomalyStatus,
    FuelAnomalyType,
    FuelCard,
    FuelCardStatus,
    FuelCardStatusEvent,
    FuelLimit,
    FuelLimitBreach,
    FuelLimitBreachScopeType,
    FuelLimitBreachStatus,
    FuelLimitBreachType,
    FuelLimitPeriod,
    FuelLimitScopeType,
    FuelLimitType,
)
from app.services.case_events_service import verify_case_event_signatures
from app.services.fleet_policy_engine import evaluate_policies_for_anomaly, evaluate_policies_for_breach


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def signing_key() -> bytes:
    private_key = Ed25519PrivateKey.generate()
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture(autouse=True)
def audit_signing_env(monkeypatch: pytest.MonkeyPatch, signing_key: bytes) -> None:
    monkeypatch.setenv("AUDIT_SIGNING_MODE", "local")
    monkeypatch.setenv("AUDIT_SIGNING_REQUIRED", "true")
    monkeypatch.setenv("AUDIT_SIGNING_ALG", "ed25519")
    monkeypatch.setenv("AUDIT_SIGNING_KEY_ID", "local-test-key")
    monkeypatch.setenv("AUDIT_SIGNING_PRIVATE_KEY_B64", base64.b64encode(signing_key).decode("utf-8"))


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Case.__table__.create(bind=engine)
    CaseEvent.__table__.create(bind=engine)
    CaseSnapshot.__table__.create(bind=engine)
    CaseComment.__table__.create(bind=engine)
    DecisionMemoryRecord.__table__.create(bind=engine)
    FuelCard.__table__.create(bind=engine)
    FuelCardGroupMember.__table__.create(bind=engine)
    FuelCardStatusEvent.__table__.create(bind=engine)
    FuelLimit.__table__.create(bind=engine)
    FuelLimitBreach.__table__.create(bind=engine)
    FuelAnomaly.__table__.create(bind=engine)
    FleetActionPolicy.__table__.create(bind=engine)
    FleetPolicyExecution.__table__.create(bind=engine)
    FleetNotificationOutbox.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        FleetNotificationOutbox.__table__.drop(bind=engine)
        FleetPolicyExecution.__table__.drop(bind=engine)
        FleetActionPolicy.__table__.drop(bind=engine)
        FuelAnomaly.__table__.drop(bind=engine)
        FuelLimitBreach.__table__.drop(bind=engine)
        FuelLimit.__table__.drop(bind=engine)
        FuelCardStatusEvent.__table__.drop(bind=engine)
        FuelCardGroupMember.__table__.drop(bind=engine)
        FuelCard.__table__.drop(bind=engine)
        DecisionMemoryRecord.__table__.drop(bind=engine)
        CaseComment.__table__.drop(bind=engine)
        CaseSnapshot.__table__.drop(bind=engine)
        CaseEvent.__table__.drop(bind=engine)
        Case.__table__.drop(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _make_client_admin_token(make_jwt, client_id: str) -> str:
    admin_user_id = str(uuid4())
    return make_jwt(
        roles=("CLIENT_ADMIN",),
        client_id=client_id,
        sub=admin_user_id,
        extra={"user_id": admin_user_id, "email": "admin@fleet.test", "tenant_id": 1},
    )


def _seed_card(db: Session, *, client_id: str) -> FuelCard:
    card = FuelCard(
        tenant_id=1,
        client_id=client_id,
        card_token="token",
        card_alias="NEFT-0001",
        status=FuelCardStatus.ACTIVE,
    )
    db.add(card)
    db.commit()
    return card


def _seed_breach(db: Session, *, client_id: str, card_id: str) -> FuelLimitBreach:
    limit = FuelLimit(
        tenant_id=1,
        client_id=client_id,
        scope_type=FuelLimitScopeType.CARD,
        scope_id=card_id,
        period=FuelLimitPeriod.DAILY,
        limit_type=FuelLimitType.AMOUNT,
        value=0,
        amount_limit=Decimal("100"),
        active=True,
    )
    db.add(limit)
    db.flush()
    breach = FuelLimitBreach(
        client_id=client_id,
        scope_type=FuelLimitBreachScopeType.CARD,
        scope_id=card_id,
        period=FuelLimitPeriod.DAILY,
        limit_id=limit.id,
        breach_type=FuelLimitBreachType.AMOUNT,
        threshold=Decimal("100"),
        observed=Decimal("180"),
        delta=Decimal("80"),
        occurred_at=datetime.now(timezone.utc),
        status=FuelLimitBreachStatus.OPEN,
    )
    db.add(breach)
    db.commit()
    return breach


def test_hard_breach_auto_block_idempotent(db_session: Session) -> None:
    client_id = str(uuid4())
    card = _seed_card(db_session, client_id=client_id)
    breach = _seed_breach(db_session, client_id=client_id, card_id=str(card.id))
    policy = FleetActionPolicy(
        client_id=client_id,
        scope_type=FleetActionPolicyScopeType.CLIENT,
        trigger_type=FleetActionTriggerType.LIMIT_BREACH,
        trigger_severity_min=FleetNotificationSeverity.LOW,
        breach_kind=FleetActionBreachKind.HARD,
        action=FleetActionPolicyAction.AUTO_BLOCK_CARD,
        cooldown_seconds=300,
        active=True,
    )
    db_session.add(policy)
    db_session.commit()

    evaluate_policies_for_breach(db_session, str(breach.id))
    db_session.refresh(card)
    assert card.status == FuelCardStatus.BLOCKED

    executions = db_session.query(FleetPolicyExecution).all()
    assert len(executions) == 1
    assert executions[0].status == FleetPolicyExecutionStatus.APPLIED

    events = db_session.query(CaseEvent).filter(CaseEvent.type == CaseEventType.FUEL_CARD_AUTO_BLOCKED).all()
    assert events
    signature_check = verify_case_event_signatures(db_session, case_id=str(events[0].case_id))
    assert signature_check.verified is True

    evaluate_policies_for_breach(db_session, str(breach.id))
    executions_again = db_session.query(FleetPolicyExecution).all()
    assert len(executions_again) == 1


def test_anomaly_escalation_creates_case(db_session: Session) -> None:
    client_id = str(uuid4())
    card = _seed_card(db_session, client_id=client_id)
    anomaly = FuelAnomaly(
        client_id=client_id,
        card_id=card.id,
        group_id=None,
        tx_id=None,
        anomaly_type=FuelAnomalyType.SPIKE_AMOUNT,
        severity=FleetNotificationSeverity.HIGH,
        score=Decimal("0.7"),
        baseline=None,
        details=None,
        status=FuelAnomalyStatus.OPEN,
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(anomaly)
    policy = FleetActionPolicy(
        client_id=client_id,
        scope_type=FleetActionPolicyScopeType.CLIENT,
        trigger_type=FleetActionTriggerType.ANOMALY,
        trigger_severity_min=FleetNotificationSeverity.HIGH,
        breach_kind=None,
        action=FleetActionPolicyAction.ESCALATE_CASE,
        cooldown_seconds=300,
        active=True,
    )
    db_session.add(policy)
    db_session.commit()

    evaluate_policies_for_anomaly(db_session, str(anomaly.id))
    case = db_session.query(Case).filter(Case.case_source_ref_id == anomaly.id).one()
    assert case.kind.value == "fleet"

    event = (
        db_session.query(CaseEvent)
        .filter(CaseEvent.case_id == case.id)
        .filter(CaseEvent.type == CaseEventType.FLEET_ESCALATION_CASE_CREATED)
        .one()
    )
    assert event is not None
    decision = (
        db_session.query(DecisionMemoryRecord)
        .filter(DecisionMemoryRecord.case_id == case.id)
        .filter(DecisionMemoryRecord.decision_type == "escalation")
        .one()
    )
    assert decision.decision_type == "escalation"


def test_policy_cooldown_skips_second_execution(db_session: Session) -> None:
    client_id = str(uuid4())
    card = _seed_card(db_session, client_id=client_id)
    breach = _seed_breach(db_session, client_id=client_id, card_id=str(card.id))
    later_breach = FuelLimitBreach(
        client_id=client_id,
        scope_type=FuelLimitBreachScopeType.CARD,
        scope_id=card.id,
        period=FuelLimitPeriod.DAILY,
        limit_id=breach.limit_id,
        breach_type=FuelLimitBreachType.AMOUNT,
        threshold=Decimal("100"),
        observed=Decimal("130"),
        delta=Decimal("30"),
        occurred_at=breach.occurred_at + timedelta(minutes=10),
        status=FuelLimitBreachStatus.OPEN,
    )
    db_session.add(later_breach)
    policy = FleetActionPolicy(
        client_id=client_id,
        scope_type=FleetActionPolicyScopeType.CLIENT,
        trigger_type=FleetActionTriggerType.LIMIT_BREACH,
        trigger_severity_min=FleetNotificationSeverity.LOW,
        breach_kind=FleetActionBreachKind.HARD,
        action=FleetActionPolicyAction.NOTIFY_ONLY,
        cooldown_seconds=3600,
        active=True,
    )
    db_session.add(policy)
    db_session.commit()

    evaluate_policies_for_breach(db_session, str(breach.id))
    evaluate_policies_for_breach(db_session, str(later_breach.id))

    executions = db_session.query(FleetPolicyExecution).order_by(FleetPolicyExecution.created_at.asc()).all()
    assert len(executions) == 2
    assert executions[0].status == FleetPolicyExecutionStatus.APPLIED
    assert executions[1].status == FleetPolicyExecutionStatus.SKIPPED


def test_manual_unblock_requires_reason(make_jwt, client: TestClient, db_session: Session) -> None:
    client_id = str(uuid4())
    token = _make_client_admin_token(make_jwt, client_id)
    card = FuelCard(
        tenant_id=1,
        client_id=client_id,
        card_token="token",
        card_alias="NEFT-0002",
        status=FuelCardStatus.BLOCKED,
    )
    db_session.add(card)
    db_session.commit()

    resp = client.post(f"/api/client/fleet/cards/{card.id}/unblock", headers=_auth_headers(token))
    assert resp.status_code == 422

    ok_resp = client.post(
        f"/api/client/fleet/cards/{card.id}/unblock",
        json={"reason": "verified"},
        headers=_auth_headers(token),
    )
    assert ok_resp.status_code == 200
    events = db_session.query(CaseEvent).filter(CaseEvent.type == CaseEventType.FUEL_CARD_UNBLOCKED).all()
    assert events
    decisions = db_session.query(DecisionMemoryRecord).filter(DecisionMemoryRecord.decision_type == "manual_unblock").all()
    assert decisions


def test_policy_action_notification_deduped(db_session: Session) -> None:
    client_id = str(uuid4())
    card = _seed_card(db_session, client_id=client_id)
    breach = _seed_breach(db_session, client_id=client_id, card_id=str(card.id))
    policy = FleetActionPolicy(
        client_id=client_id,
        scope_type=FleetActionPolicyScopeType.CLIENT,
        trigger_type=FleetActionTriggerType.LIMIT_BREACH,
        trigger_severity_min=FleetNotificationSeverity.LOW,
        breach_kind=FleetActionBreachKind.HARD,
        action=FleetActionPolicyAction.NOTIFY_ONLY,
        cooldown_seconds=300,
        active=True,
    )
    db_session.add(policy)
    db_session.commit()

    evaluate_policies_for_breach(db_session, str(breach.id))
    evaluate_policies_for_breach(db_session, str(breach.id))

    outbox = db_session.query(FleetNotificationOutbox).all()
    assert len(outbox) == 1
    assert outbox[0].status == FleetNotificationOutboxStatus.PENDING
