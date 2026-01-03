from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.audit_log import AuditLog


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def api_client(admin_auth_headers):
    with TestClient(app) as client:
        client.headers.update(admin_auth_headers)
        yield client


def test_stubbed_finance_cycle(api_client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "BANK_STUB_ENABLED", True)
    monkeypatch.setattr(settings, "BANK_STUB_IMMEDIATE_SETTLE", True)
    monkeypatch.setattr(settings, "ERP_STUB_ENABLED", True)
    monkeypatch.setattr(settings, "ERP_STUB_AUTO_ACK", True)

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
        "/api/v1/admin/reconciliation/run",
        params={
            "source": "bank_stub",
            "period_from": period_from.isoformat(),
            "period_to": period_to.isoformat(),
        },
    )
    assert run_resp.status_code == 201
    run = run_resp.json()

    discrepancies_resp = api_client.get(f"/api/v1/admin/reconciliation/runs/{run['id']}/discrepancies")
    assert discrepancies_resp.status_code == 200
    assert discrepancies_resp.json()["discrepancies"] == []

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
        .filter(AuditLog.event_type.in_(
            [
                "BANK_STUB_PAYMENT_CREATED",
                "BANK_STUB_STATEMENT_GENERATED",
                "RECONCILIATION_RUN_COMPLETED",
                "PAYOUT_INITIATED",
                "ERP_STUB_EXPORT_CREATED",
            ]
        ))
        .all()
    }
    assert "BANK_STUB_PAYMENT_CREATED" in audit_events
    assert "BANK_STUB_STATEMENT_GENERATED" in audit_events
    assert "RECONCILIATION_RUN_COMPLETED" in audit_events
    assert "PAYOUT_INITIATED" in audit_events
    assert "ERP_STUB_EXPORT_CREATED" in audit_events
