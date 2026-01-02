from __future__ import annotations

import base64
from datetime import datetime, timezone
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
from app.models.case_exports import CaseExport
from app.models.cases import Case, CaseEvent, CaseEventType
from app.models.decision_memory import DecisionMemoryRecord
from app.models.fleet import ClientEmployee, FuelCardGroupMember, FuelGroupAccess
from app.models.fuel import (
    FuelCard,
    FuelCardGroup,
    FuelIngestJob,
    FuelLimit,
    FuelLimitBreach,
    FuelLimitBreachStatus,
    FuelLimitScopeType,
    FuelLimitType,
    FuelLimitPeriod,
    FuelNetwork,
    FuelProvider,
    FuelStation,
    FuelTransaction,
)
from app.services.case_events_service import verify_case_event_signatures


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _StubExportStorage:
    def put_bytes(self, key: str, content: bytes, *, content_type: str, retain_until=None) -> None:
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
    CaseExport.__table__.create(bind=engine)
    FuelNetwork.__table__.create(bind=engine)
    FuelProvider.__table__.create(bind=engine)
    FuelStation.__table__.create(bind=engine)
    FuelCardGroup.__table__.create(bind=engine)
    FuelCard.__table__.create(bind=engine)
    FuelCardGroupMember.__table__.create(bind=engine)
    ClientEmployee.__table__.create(bind=engine)
    FuelGroupAccess.__table__.create(bind=engine)
    FuelLimit.__table__.create(bind=engine)
    FuelIngestJob.__table__.create(bind=engine)
    FuelLimitBreach.__table__.create(bind=engine)
    FuelTransaction.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        FuelTransaction.__table__.drop(bind=engine)
        FuelLimitBreach.__table__.drop(bind=engine)
        FuelIngestJob.__table__.drop(bind=engine)
        FuelLimit.__table__.drop(bind=engine)
        FuelGroupAccess.__table__.drop(bind=engine)
        ClientEmployee.__table__.drop(bind=engine)
        FuelCardGroupMember.__table__.drop(bind=engine)
        FuelCard.__table__.drop(bind=engine)
        FuelCardGroup.__table__.drop(bind=engine)
        FuelStation.__table__.drop(bind=engine)
        FuelProvider.__table__.drop(bind=engine)
        FuelNetwork.__table__.drop(bind=engine)
        CaseExport.__table__.drop(bind=engine)
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


def test_ingest_batch_idempotent(make_jwt, client: TestClient, db_session: Session) -> None:
    _, admin_token, card_alias = _create_card(client, make_jwt)
    internal_token = make_jwt(roles=("ADMIN",), sub=str(uuid4()), extra={"tenant_id": 1})
    payload = {
        "provider_code": "bank_stub",
        "batch_ref": "BATCH-1",
        "idempotency_key": str(uuid4()),
        "items": [
            {
                "provider_tx_id": "TX-1",
                "card_alias": card_alias,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "amount": "250.00",
                "currency": "RUB",
            }
        ],
    }
    ingest_resp = client.post("/api/internal/fleet/transactions/ingest", json=payload, headers=_auth_headers(internal_token))
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["inserted_count"] == 1

    ingest_again = client.post(
        "/api/internal/fleet/transactions/ingest",
        json=payload,
        headers=_auth_headers(internal_token),
    )
    assert ingest_again.status_code == 200
    assert ingest_again.json()["id"] == ingest_resp.json()["id"]


def test_dedupe_by_provider_tx_id(make_jwt, client: TestClient, db_session: Session) -> None:
    _, _, card_alias = _create_card(client, make_jwt)
    internal_token = make_jwt(roles=("ADMIN",), sub=str(uuid4()), extra={"tenant_id": 1})
    payload = {
        "provider_code": "bank_stub",
        "batch_ref": "BATCH-2",
        "idempotency_key": str(uuid4()),
        "items": [
            {
                "provider_tx_id": "TX-dup",
                "card_alias": card_alias,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "amount": "100.00",
                "currency": "RUB",
            },
            {
                "provider_tx_id": "TX-dup",
                "card_alias": card_alias,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "amount": "100.00",
                "currency": "RUB",
            },
        ],
    }
    resp = client.post("/api/internal/fleet/transactions/ingest", json=payload, headers=_auth_headers(internal_token))
    assert resp.status_code == 200
    assert resp.json()["inserted_count"] == 1
    assert resp.json()["deduped_count"] == 1


def test_limit_breach_and_audit(make_jwt, client: TestClient, db_session: Session) -> None:
    client_id, admin_token, card_alias = _create_card(client, make_jwt)
    card = db_session.query(FuelCard).filter(FuelCard.card_alias == card_alias).one()
    limit = FuelLimit(
        tenant_id=1,
        client_id=client_id,
        scope_type=FuelLimitScopeType.CARD,
        scope_id=str(card.id),
        period=FuelLimitPeriod.DAILY,
        limit_type=FuelLimitType.AMOUNT,
        value=0,
        amount_limit=Decimal("100.00"),
        volume_limit_liters=None,
        categories=None,
        stations_allowlist=None,
        active=True,
    )
    db_session.add(limit)
    db_session.commit()

    internal_token = make_jwt(roles=("ADMIN",), sub=str(uuid4()), extra={"tenant_id": 1})
    payload = {
        "provider_code": "bank_stub",
        "batch_ref": "BATCH-3",
        "idempotency_key": str(uuid4()),
        "items": [
            {
                "provider_tx_id": "TX-2",
                "card_alias": card_alias,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "amount": "150.00",
                "currency": "RUB",
            }
        ],
    }
    resp = client.post("/api/internal/fleet/transactions/ingest", json=payload, headers=_auth_headers(internal_token))
    assert resp.status_code == 200

    breaches = db_session.query(FuelLimitBreach).all()
    assert len(breaches) == 1
    assert breaches[0].status == FuelLimitBreachStatus.OPEN
    events = db_session.query(CaseEvent).filter(CaseEvent.type == CaseEventType.FUEL_LIMIT_BREACH_DETECTED).all()
    assert events
    signature_check = verify_case_event_signatures(db_session, case_id=str(events[0].case_id))
    assert signature_check.verified is True

    export_resp = client.get(
        "/api/client/fleet/transactions/export",
        headers=_auth_headers(admin_token),
    )
    assert export_resp.status_code == 200
    payload = export_resp.json()
    assert payload["url"].startswith("https://exports.local/")
    assert payload["content_sha256"] is not None
