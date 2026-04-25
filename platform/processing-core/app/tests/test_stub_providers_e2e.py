from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.bank_stub import BankStubPayment, BankStubStatement, BankStubStatementLine
from app.models.billing_flow import BillingInvoice, BillingPayment, BillingRefund
from app.models.cases import Case, CaseComment, CaseEvent, CaseSnapshot
from app.models.client import Client
from app.models.decision_memory import DecisionMemoryRecord
from app.models.erp_stub import ErpStubExport, ErpStubExportItem
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.notifications import NotificationMessage
from app.models.reconciliation import ExternalStatement, ReconciliationDiscrepancy, ReconciliationLink, ReconciliationRun
from app.models.settlement_v1 import SettlementAccount, SettlementItem, SettlementPayout, SettlementPeriod
from app.routers.admin.bank_stub import router as bank_stub_router
from app.routers.admin.billing_flows import router as billing_flows_router
from app.routers.admin.erp_stub import router as erp_stub_router
from app.routers.admin.reconciliation import router as admin_reconciliation_router
from app.routers.admin.settlement_v1 import router as settlement_v1_router
from app.security.rbac.principal import Principal, get_principal
from app.tests._money_router_harness import money_session_context


_REFLECTED_METADATA = MetaData()

FLEET_OFFLINE_PROFILES_REFLECTED = Table(
    "fleet_offline_profiles",
    _REFLECTED_METADATA,
    Column("id", String(36), primary_key=True),
)

STUB_PROVIDER_E2E_TEST_TABLES = (
    FLEET_OFFLINE_PROFILES_REFLECTED,
    AuditLog.__table__,
    Client.__table__,
    Case.__table__,
    CaseSnapshot.__table__,
    CaseComment.__table__,
    CaseEvent.__table__,
    DecisionMemoryRecord.__table__,
    NotificationMessage.__table__,
    BillingInvoice.__table__,
    BillingPayment.__table__,
    BillingRefund.__table__,
    InternalLedgerAccount.__table__,
    InternalLedgerTransaction.__table__,
    InternalLedgerEntry.__table__,
    ReconciliationRun.__table__,
    ExternalStatement.__table__,
    ReconciliationDiscrepancy.__table__,
    ReconciliationLink.__table__,
    BankStubPayment.__table__,
    BankStubStatement.__table__,
    BankStubStatementLine.__table__,
    SettlementAccount.__table__,
    SettlementPeriod.__table__,
    SettlementItem.__table__,
    SettlementPayout.__table__,
    ErpStubExport.__table__,
    ErpStubExportItem.__table__,
)

_ADMIN_PRINCIPAL = Principal(
    user_id=UUID("00000000-0000-0000-0000-000000000211"),
    roles={"admin"},
    scopes=set(),
    client_id=None,
    partner_id=None,
    is_admin=True,
    raw_claims={
        "sub": "00000000-0000-0000-0000-000000000211",
        "user_id": "00000000-0000-0000-0000-000000000211",
        "email": "admin@neft.local",
        "roles": ["ADMIN"],
        "tenant_id": "1",
    },
)


def _admin_principal_override() -> Principal:
    return _ADMIN_PRINCIPAL


def _admin_token_override() -> dict[str, object]:
    return dict(_ADMIN_PRINCIPAL.raw_claims)


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


@pytest.fixture
def db_session():
    with money_session_context(tables=STUB_PROVIDER_E2E_TEST_TABLES) as session:
        yield session


@pytest.fixture
def api_client(db_session):
    app = FastAPI()
    app.include_router(billing_flows_router, prefix="/api/v1/admin")
    app.include_router(bank_stub_router, prefix="/api/v1/admin")
    app.include_router(settlement_v1_router, prefix="/api/v1/admin")
    app.include_router(admin_reconciliation_router, prefix="/api/core/v1/admin")
    app.include_router(erp_stub_router, prefix="/api/v1/admin")

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_principal] = _admin_principal_override
    app.dependency_overrides[require_admin_user] = _admin_token_override

    with TestClient(app) as client:
        client.headers.update({"Authorization": "Bearer test-admin"})
        yield client


def test_stubbed_finance_cycle(api_client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.bank_stub_service.settings.BANK_STUB_ENABLED", True)
    monkeypatch.setattr("app.services.bank_stub_service.settings.BANK_STUB_IMMEDIATE_SETTLE", True)
    monkeypatch.setattr("app.routers.admin.bank_stub.settings.BANK_STUB_ENABLED", True)
    monkeypatch.setattr("app.services.erp_stub_service.settings.ERP_STUB_ENABLED", True)
    monkeypatch.setattr("app.services.erp_stub_service.settings.ERP_STUB_AUTO_ACK", True)
    monkeypatch.setattr("app.routers.admin.erp_stub.settings.ERP_STUB_ENABLED", True)
    monkeypatch.setattr("app.routers.admin.reconciliation.settings.BANK_STUB_ENABLED", True)

    client_id = str(uuid4())
    now = datetime.now(timezone.utc)
    period_from = now - timedelta(days=1)
    period_to = now + timedelta(days=1)

    invoice_payload = {
        "client_id": client_id,
        "case_id": None,
        "currency": "RUB",
        "amount_total": "100",
        "due_at": None,
        "idempotency_key": "invoice-e2e-1",
    }
    invoice_resp = api_client.post("/api/v1/admin/billing/flows/invoices", json=invoice_payload)
    assert invoice_resp.status_code == 201
    invoice = invoice_resp.json()

    payment_payload = {
        "invoice_id": invoice["id"],
        "amount": "100",
        "idempotency_key": "bank-stub-pay-1",
    }
    payment_resp = api_client.post("/api/v1/admin/bank_stub/payments", json=payment_payload)
    assert payment_resp.status_code == 201
    payment = payment_resp.json()

    payment_replay = api_client.post("/api/v1/admin/bank_stub/payments", json=payment_payload).json()
    assert payment_replay["id"] == payment["id"]

    statement_resp = api_client.post(
        "/api/v1/admin/bank_stub/statements/generate",
        params={"from": period_from.isoformat(), "to": period_to.isoformat()},
    )
    assert statement_resp.status_code == 201
    statement = statement_resp.json()

    statement_replay = api_client.post(
        "/api/v1/admin/bank_stub/statements/generate",
        params={"from": period_from.isoformat(), "to": period_to.isoformat()},
    ).json()
    assert statement_replay["id"] == statement["id"]

    run_resp = api_client.post(
        "/api/core/v1/admin/reconciliation/run",
        params={
            "source": "bank_stub",
            "period_from": period_from.isoformat(),
            "period_to": period_to.isoformat(),
        },
    )
    assert run_resp.status_code == 201
    run = run_resp.json()

    discrepancies_resp = api_client.get(f"/api/core/v1/admin/reconciliation/runs/{run['id']}/discrepancies")
    assert discrepancies_resp.status_code == 200
    discrepancies = discrepancies_resp.json()["discrepancies"]
    assert {item["discrepancy_type"] for item in discrepancies} == {"balance_mismatch"}
    assert {
        (item.get("details") or {}).get("kind")
        for item in discrepancies
    } == {"total_in", "total_out", "closing_balance"}

    period_payload = {
        "partner_id": client_id,
        "currency": invoice["currency"],
        "period_start": period_from.isoformat(),
        "period_end": period_to.isoformat(),
        "idempotency_key": "settlement-e2e-1",
    }
    period_resp = api_client.post("/api/v1/admin/settlement/periods/calculate", json=period_payload)
    assert period_resp.status_code == 200
    period = period_resp.json()
    assert Decimal(str(period["total_gross"])) == Decimal("100")

    approve_resp = api_client.post(f"/api/v1/admin/settlement/periods/{period['id']}/approve")
    assert approve_resp.status_code == 200

    payout_resp = api_client.post(
        f"/api/v1/admin/settlement/periods/{period['id']}/payout",
        json={"provider": "bank_stub", "idempotency_key": "payout-e2e-1"},
    )
    assert payout_resp.status_code == 200

    export_payload = {
        "export_type": "SETTLEMENT",
        "entity_ids": [period["id"]],
        "export_ref": "export-settlement-1",
    }
    export_resp = api_client.post("/api/v1/admin/erp_stub/exports", json=export_payload)
    assert export_resp.status_code == 201
    export_item = export_resp.json()
    assert export_item["status"] in {"SENT", "ACKED"}

    export_replay = api_client.post("/api/v1/admin/erp_stub/exports", json=export_payload).json()
    assert export_replay["id"] == export_item["id"]

    ack_resp = api_client.post(f"/api/v1/admin/erp_stub/exports/{export_item['id']}/ack")
    assert ack_resp.status_code == 200

    audit_events = {
        event.event_type
        for event in db_session.query(AuditLog)
        .filter(
            AuditLog.event_type.in_(
                [
                    "BANK_STUB_PAYMENT_CREATED",
                    "BANK_STUB_STATEMENT_GENERATED",
                    "RECONCILIATION_RUN_COMPLETED",
                    "PAYOUT_INITIATED",
                    "ERP_STUB_EXPORT_CREATED",
                ]
            )
        )
        .all()
    }
    assert "BANK_STUB_PAYMENT_CREATED" in audit_events
    assert "BANK_STUB_STATEMENT_GENERATED" in audit_events
    assert "RECONCILIATION_RUN_COMPLETED" in audit_events
    assert "PAYOUT_INITIATED" in audit_events
    assert "ERP_STUB_EXPORT_CREATED" in audit_events
