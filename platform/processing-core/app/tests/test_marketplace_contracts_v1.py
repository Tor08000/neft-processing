import base64
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.cases import CaseEvent
from app.models.decision_memory import DecisionMemoryRecord
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerEntry,
    InternalLedgerTransaction,
    InternalLedgerTransactionType,
)
from app.models.marketplace_contracts import (
    Contract,
    ContractEvent,
    ContractImmutableError,
    ContractObligation,
    ContractVersion,
    SLAResult,
)
from app.routers.admin.marketplace_contracts import router as contracts_router
from app.services.audit_service import AuditService


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
def api_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        AuditLog.__table__,
        CaseEvent.__table__,
        DecisionMemoryRecord.__table__,
        Contract.__table__,
        ContractVersion.__table__,
        ContractObligation.__table__,
        ContractEvent.__table__,
        SLAResult.__table__,
        InternalLedgerAccount.__table__,
        InternalLedgerTransaction.__table__,
        InternalLedgerEntry.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    app = FastAPI()
    app.include_router(contracts_router, prefix="/api/v1/admin")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, SessionLocal

    for table in reversed(tables):
        table.drop(bind=engine)
    engine.dispose()


def _create_contract(client: TestClient) -> dict:
    payload = {
        "contract_number": "C-001",
        "contract_type": "service",
        "party_a_type": "system",
        "party_a_id": "11111111-1111-1111-1111-111111111111",
        "party_b_type": "client",
        "party_b_id": "22222222-2222-2222-2222-222222222222",
        "currency": "USD",
        "effective_from": datetime.now(timezone.utc).isoformat(),
        "effective_to": None,
        "terms": {"scope": "deliveries"},
        "obligations": [
            {
                "obligation_type": "delivery",
                "metric": "delivery_time",
                "threshold": "7200",
                "comparison": "<=",
                "window": "24h",
                "penalty_type": "fee",
                "penalty_value": "10",
            }
        ],
    }
    response = client.post("/api/v1/admin/contracts", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_contract_audited(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    response = _create_contract(client)

    with SessionLocal() as db:
        audit = db.query(AuditLog).filter(AuditLog.id == response["audit_event_id"]).one_or_none()
        assert audit is not None
        assert audit.event_type == "CONTRACT_CREATED"
        assert audit.hash is not None


def test_add_version_worm_enforced(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    contract = _create_contract(client)
    version_payload = {"terms": {"scope": "deliveries-v2"}, "obligations": []}
    version_resp = client.post(f"/api/v1/admin/contracts/{contract['id']}/versions", json=version_payload)
    assert version_resp.status_code == 201

    with SessionLocal() as db:
        record = db.query(Contract).filter(Contract.id == contract["id"]).one()
        record.status = "SUSPENDED"
        with pytest.raises(ContractImmutableError):
            db.flush()


def test_emit_contract_event_audited_and_signed(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    contract = _create_contract(client)
    event_payload = {
        "event_type": "ORDER_PLACED",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"order_id": "order-1"},
    }
    event_resp = client.post(f"/api/v1/admin/contracts/{contract['id']}/events", json=event_payload)
    assert event_resp.status_code == 201
    event_body = event_resp.json()
    assert event_body["signature"] is not None
    assert event_body["signature_alg"] == "ed25519"

    with SessionLocal() as db:
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.event_type == "CONTRACT_EVENT_RECORDED")
            .order_by(AuditLog.ts.desc())
            .first()
        )
        assert audit is not None


def test_evaluate_sla_ok(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    contract = _create_contract(client)
    now = datetime.now(timezone.utc)
    client.post(
        f"/api/v1/admin/contracts/{contract['id']}/events",
        json={
            "event_type": "ORDER_PLACED",
            "occurred_at": (now - timedelta(hours=2)).isoformat(),
            "payload": {"order_id": "order-1"},
        },
    )
    client.post(
        f"/api/v1/admin/contracts/{contract['id']}/events",
        json={
            "event_type": "DELIVERY_CONFIRMED",
            "occurred_at": (now - timedelta(hours=1)).isoformat(),
            "payload": {"order_id": "order-1"},
        },
    )
    eval_resp = client.post(
        f"/api/v1/admin/contracts/{contract['id']}/sla/evaluate",
        json={"period_start": (now - timedelta(days=1)).isoformat(), "period_end": now.isoformat()},
    )
    assert eval_resp.status_code == 200
    results = eval_resp.json()
    assert results[0]["status"] == "OK"


def test_sla_violation_creates_penalty(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    payload = {
        "contract_number": "C-002",
        "contract_type": "service",
        "party_a_type": "system",
        "party_a_id": "11111111-1111-1111-1111-111111111111",
        "party_b_type": "client",
        "party_b_id": "33333333-3333-3333-3333-333333333333",
        "currency": "USD",
        "effective_from": datetime.now(timezone.utc).isoformat(),
        "effective_to": None,
        "terms": {"scope": "response"},
        "obligations": [
            {
                "obligation_type": "response_time",
                "metric": "response_time",
                "threshold": "60",
                "comparison": "<=",
                "window": "24h",
                "penalty_type": "fee",
                "penalty_value": "5",
            }
        ],
    }
    contract_resp = client.post("/api/v1/admin/contracts", json=payload)
    contract = contract_resp.json()
    now = datetime.now(timezone.utc)
    client.post(
        f"/api/v1/admin/contracts/{contract['id']}/events",
        json={
            "event_type": "ORDER_PLACED",
            "occurred_at": (now - timedelta(hours=3)).isoformat(),
            "payload": {"order_id": "order-9"},
        },
    )
    client.post(
        f"/api/v1/admin/contracts/{contract['id']}/events",
        json={
            "event_type": "SERVICE_STARTED",
            "occurred_at": (now - timedelta(hours=1)).isoformat(),
            "payload": {"order_id": "order-9"},
        },
    )
    eval_resp = client.post(
        f"/api/v1/admin/contracts/{contract['id']}/sla/evaluate",
        json={"period_start": (now - timedelta(days=1)).isoformat(), "period_end": now.isoformat()},
    )
    assert eval_resp.status_code == 200
    results = eval_resp.json()
    assert results[0]["status"] == "VIOLATION"

    with SessionLocal() as db:
        penalty = (
            db.query(InternalLedgerTransaction)
            .filter(InternalLedgerTransaction.transaction_type == InternalLedgerTransactionType.ADJUSTMENT)
            .filter(InternalLedgerTransaction.external_ref_type == "SLA_PENALTY")
            .first()
        )
        assert penalty is not None
        audit_verify = AuditService(db).verify_chain(
            date_from=datetime(2000, 1, 1, tzinfo=timezone.utc),
            date_to=datetime.now(timezone.utc) + timedelta(days=1),
            tenant_id=None,
        )
        assert audit_verify["status"] == "OK"
