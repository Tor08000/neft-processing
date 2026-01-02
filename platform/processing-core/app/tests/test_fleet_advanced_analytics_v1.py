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
from app.models.cases import Case, CaseEvent, CaseEventType
from app.models.decision_memory import DecisionMemoryRecord
from app.models.fleet import ClientEmployee, FuelCardGroupMember, FuelGroupAccess
from app.models.fuel import (
    FleetNotificationEventType,
    FleetNotificationOutbox,
    FleetNotificationPolicy,
    FleetNotificationPolicyScopeType,
    FleetNotificationSeverity,
    FuelAnomaly,
    FuelAnomalyStatus,
    FuelAnomalyType,
    FuelCard,
    FuelCardGroup,
    FuelCardStatus,
    FuelIngestJob,
    FuelLimit,
    FuelLimitBreach,
    FuelLimitBreachScopeType,
    FuelLimitBreachStatus,
    FuelLimitBreachType,
    FuelLimitEscalation,
    FuelLimitEscalationAction,
    FuelLimitEscalationStatus,
    FuelLimitPeriod,
    FuelLimitScopeType,
    FuelLimitType,
    FuelMerchant,
    FuelNetwork,
    FuelProvider,
    FuelStation,
    FuelTransaction,
)
from app.services.fleet_notification_dispatcher import enqueue_notification, sign_webhook_payload


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _StubExportStorage:
    def put_bytes(self, key: str, content: bytes, *, content_type: str) -> None:
        return None

    def delete(self, key: str) -> None:
        return None

    def presign_get(self, key: str, *, ttl_seconds: int) -> str:
        return f"https://exports.local/{key}"


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
    DecisionMemoryRecord.__table__.create(bind=engine)
    FuelNetwork.__table__.create(bind=engine)
    FuelProvider.__table__.create(bind=engine)
    FuelMerchant.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    FuelCardGroup.__table__.create(bind=engine)
    FuelCard.__table__.create(bind=engine)
    FuelCardGroupMember.__table__.create(bind=engine)
    ClientEmployee.__table__.create(bind=engine)
    FuelGroupAccess.__table__.create(bind=engine)
    FuelLimit.__table__.create(bind=engine)
    FuelIngestJob.__table__.create(bind=engine)
    FuelLimitBreach.__table__.create(bind=engine)
    FuelLimitEscalation.__table__.create(bind=engine)
    FuelAnomaly.__table__.create(bind=engine)
    FleetNotificationPolicy.__table__.create(bind=engine)
    FleetNotificationOutbox.__table__.create(bind=engine)
    FuelTransaction.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        FuelTransaction.__table__.drop(bind=engine)
        FleetNotificationOutbox.__table__.drop(bind=engine)
        FleetNotificationPolicy.__table__.drop(bind=engine)
        FuelAnomaly.__table__.drop(bind=engine)
        FuelLimitEscalation.__table__.drop(bind=engine)
        FuelLimitBreach.__table__.drop(bind=engine)
        FuelIngestJob.__table__.drop(bind=engine)
        FuelLimit.__table__.drop(bind=engine)
        FuelGroupAccess.__table__.drop(bind=engine)
        ClientEmployee.__table__.drop(bind=engine)
        FuelCardGroupMember.__table__.drop(bind=engine)
        FuelCard.__table__.drop(bind=engine)
        FuelCardGroup.__table__.drop(bind=engine)
        FuelStation.__table__.drop(bind=engine)
        FuelMerchant.__table__.drop(bind=engine)
        FuelProvider.__table__.drop(bind=engine)
        FuelNetwork.__table__.drop(bind=engine)
        DecisionMemoryRecord.__table__.drop(bind=engine)
        CaseEvent.__table__.drop(bind=engine)
        Case.__table__.drop(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    monkeypatch.setattr("app.services.case_export_service.ExportStorage", _StubExportStorage)
    monkeypatch.setattr("app.services.export_storage.ExportStorage", _StubExportStorage)
    monkeypatch.setattr("app.services.fleet_service.ExportStorage", _StubExportStorage)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _create_card(client: TestClient, make_jwt) -> tuple[str, str, str]:
    client_id = str(uuid4())
    admin_user_id = str(uuid4())
    admin_token = make_jwt(
        roles=("CLIENT_ADMIN",),
        client_id=client_id,
        sub=admin_user_id,
        extra={"user_id": admin_user_id, "email": "admin@fleet.test", "tenant_id": 1},
    )
    card_payload = {"card_alias": "NEFT-00001234", "masked_pan": "****1111", "currency": "RUB"}
    card_resp = client.post("/api/client/fleet/cards", json=card_payload, headers=_auth_headers(admin_token))
    assert card_resp.status_code == 201
    return client_id, admin_token, card_payload["card_alias"]


def _ingest_payload(card_alias: str, *, amount: str, merchant_name: str, occurred_at: datetime) -> dict:
    return {
        "provider_code": "bank_stub",
        "batch_ref": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "items": [
            {
                "provider_tx_id": str(uuid4()),
                "card_alias": card_alias,
                "occurred_at": occurred_at.isoformat(),
                "amount": amount,
                "currency": "RUB",
                "merchant_name": merchant_name,
            }
        ],
    }


def test_ingest_triggers_new_merchant_anomaly(make_jwt, client: TestClient, db_session: Session) -> None:
    _, _, card_alias = _create_card(client, make_jwt)
    internal_token = make_jwt(roles=("ADMIN",), sub=str(uuid4()), extra={"tenant_id": 1})
    baseline_payload = _ingest_payload(
        card_alias,
        amount="120.00",
        merchant_name="Fuel One",
        occurred_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    resp = client.post(
        "/api/internal/fleet/transactions/ingest",
        json=baseline_payload,
        headers=_auth_headers(internal_token),
    )
    assert resp.status_code == 200

    new_merchant_payload = _ingest_payload(
        card_alias,
        amount="130.00",
        merchant_name="Fuel Two",
        occurred_at=datetime.now(timezone.utc),
    )
    resp = client.post(
        "/api/internal/fleet/transactions/ingest",
        json=new_merchant_payload,
        headers=_auth_headers(internal_token),
    )
    assert resp.status_code == 200

    anomaly = db_session.query(FuelAnomaly).filter(FuelAnomaly.anomaly_type == FuelAnomalyType.NEW_MERCHANT).one()
    assert anomaly.status == FuelAnomalyStatus.OPEN


def test_spike_amount_anomaly_high(make_jwt, client: TestClient, db_session: Session) -> None:
    _, _, card_alias = _create_card(client, make_jwt)
    internal_token = make_jwt(roles=("ADMIN",), sub=str(uuid4()), extra={"tenant_id": 1})
    for days_ago in range(5, 0, -1):
        payload = _ingest_payload(
            card_alias,
            amount="100.00",
            merchant_name="Fuel One",
            occurred_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        )
        resp = client.post(
            "/api/internal/fleet/transactions/ingest",
            json=payload,
            headers=_auth_headers(internal_token),
        )
        assert resp.status_code == 200

    spike_payload = _ingest_payload(
        card_alias,
        amount="300.00",
        merchant_name="Fuel One",
        occurred_at=datetime.now(timezone.utc),
    )
    resp = client.post(
        "/api/internal/fleet/transactions/ingest",
        json=spike_payload,
        headers=_auth_headers(internal_token),
    )
    assert resp.status_code == 200

    anomaly = db_session.query(FuelAnomaly).filter(FuelAnomaly.anomaly_type == FuelAnomalyType.SPIKE_AMOUNT).one()
    assert anomaly.severity == FleetNotificationSeverity.HIGH


def test_hard_breach_auto_blocks_card(make_jwt, client: TestClient, db_session: Session) -> None:
    client_id, admin_token, card_alias = _create_card(client, make_jwt)
    card_id = db_session.query(FuelCard.id).filter(FuelCard.card_alias == card_alias).scalar()
    limit = FuelLimit(
        tenant_id=1,
        client_id=client_id,
        scope_type=FuelLimitScopeType.CARD,
        scope_id=str(card_id),
        fuel_type_code=None,
        station_id=None,
        station_network_id=None,
        limit_type=FuelLimitType.AMOUNT,
        period=FuelLimitPeriod.DAILY,
        value=0,
        currency="RUB",
        amount_limit=Decimal("50"),
        volume_limit_liters=None,
        categories=None,
        stations_allowlist=None,
        priority=1,
        meta=None,
        active=True,
        effective_from=None,
        audit_event_id=None,
    )
    db_session.add(limit)
    policy = FleetNotificationPolicy(
        client_id=client_id,
        scope_type=FleetNotificationPolicyScopeType.CLIENT,
        scope_id=None,
        event_type=FleetNotificationEventType.LIMIT_BREACH,
        severity_min=FleetNotificationSeverity.MEDIUM,
        channels=["WEBHOOK"],
        cooldown_seconds=300,
        active=True,
        action_on_critical=FuelLimitEscalationAction.AUTO_BLOCK_CARD,
        hard_breach_only=True,
    )
    db_session.add(policy)
    db_session.commit()

    internal_token = make_jwt(roles=("ADMIN",), sub=str(uuid4()), extra={"tenant_id": 1})
    breach_payload = _ingest_payload(
        card_alias,
        amount="100.00",
        merchant_name="Fuel One",
        occurred_at=datetime.now(timezone.utc),
    )
    resp = client.post(
        "/api/internal/fleet/transactions/ingest",
        json=breach_payload,
        headers=_auth_headers(internal_token),
    )
    assert resp.status_code == 200

    card = db_session.query(FuelCard).filter(FuelCard.id == card_id).one()
    assert card.status == FuelCardStatus.BLOCKED
    escalation = db_session.query(FuelLimitEscalation).one()
    assert escalation.status == FuelLimitEscalationStatus.APPLIED


def test_outbox_dedupe(db_session: Session) -> None:
    outbox = enqueue_notification(
        db_session,
        client_id="client-1",
        event_type=FleetNotificationEventType.ANOMALY,
        severity=FleetNotificationSeverity.HIGH,
        event_ref_type="anomaly",
        event_ref_id=str(uuid4()),
        payload={"client_id": "client-1", "event_type": "ANOMALY", "severity": "HIGH"},
        principal=None,
        request_id=None,
        trace_id=None,
    )
    outbox_again = enqueue_notification(
        db_session,
        client_id="client-1",
        event_type=FleetNotificationEventType.ANOMALY,
        severity=FleetNotificationSeverity.HIGH,
        event_ref_type="anomaly",
        event_ref_id=str(outbox.event_ref_id),
        payload={"client_id": "client-1", "event_type": "ANOMALY", "severity": "HIGH"},
        principal=None,
        request_id=None,
        trace_id=None,
    )
    assert outbox.id == outbox_again.id
    assert db_session.query(FleetNotificationOutbox).count() == 1


def test_webhook_signature() -> None:
    payload = {"client_id": "client-1", "event_type": "ANOMALY", "severity": "HIGH"}
    signature = sign_webhook_payload(payload, "secret")
    assert signature == "36cec63deb7d15c81f10c76a504136e754fca319a2ad69b49ff82689f86b7f41"


def test_ack_ignore_alerts_are_audited(make_jwt, client: TestClient, db_session: Session) -> None:
    client_id, admin_token, card_alias = _create_card(client, make_jwt)
    card_id = db_session.query(FuelCard.id).filter(FuelCard.card_alias == card_alias).scalar()
    anomaly = FuelAnomaly(
        client_id=client_id,
        card_id=card_id,
        group_id=None,
        tx_id=None,
        anomaly_type=FuelAnomalyType.NEW_MERCHANT,
        severity=FleetNotificationSeverity.MEDIUM,
        score=Decimal("0.5"),
        baseline=None,
        details=None,
        status=FuelAnomalyStatus.OPEN,
        occurred_at=datetime.now(timezone.utc),
        audit_event_id=None,
    )
    breach = FuelLimitBreach(
        client_id=client_id,
        scope_type=FuelLimitBreachScopeType.CARD,
        scope_id=str(card_id),
        period=FuelLimitPeriod.DAILY,
        limit_id=str(uuid4()),
        breach_type=FuelLimitBreachType.AMOUNT,
        threshold=Decimal("10"),
        observed=Decimal("20"),
        delta=Decimal("10"),
        occurred_at=datetime.now(timezone.utc),
        tx_id=None,
        status=FuelLimitBreachStatus.OPEN,
        audit_event_id=None,
    )
    db_session.add_all([anomaly, breach])
    db_session.commit()

    ack_resp = client.post(
        f"/api/client/fleet/alerts/{anomaly.id}/ack",
        headers=_auth_headers(admin_token),
    )
    assert ack_resp.status_code == 200
    ignore_resp = client.post(
        f"/api/client/fleet/alerts/{breach.id}/ignore",
        json={"reason": "known"},
        headers=_auth_headers(admin_token),
    )
    assert ignore_resp.status_code == 200

    events = db_session.query(CaseEvent).filter(CaseEvent.type == CaseEventType.FLEET_ALERT_STATUS_UPDATED).all()
    assert len(events) >= 2
