from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("DISABLE_CELERY", "1")
os.environ.setdefault("NEFT_S3_ENDPOINT", "http://minio:9000")
os.environ.setdefault("NEFT_S3_ACCESS_KEY", "change-me")
os.environ.setdefault("NEFT_S3_SECRET_KEY", "change-me")
os.environ.setdefault("NEFT_S3_BUCKET_INVOICES", "neft-invoices")
os.environ.setdefault("NEFT_S3_BUCKET_PAYOUTS", "neft-payouts")
os.environ.setdefault("NEFT_S3_REGION", "us-east-1")

from app.db import Base, engine, get_sessionmaker
from app.main import app
from app.models.audit_log import ActorType, AuditLog
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.audit_service import AuditService, RequestContext


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_captured_operations(target_date: date, *, merchant_id: str, client_id: str) -> None:
    session = get_sessionmaker()()
    base_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    for idx in range(2):
        amount = 2000 + idx * 1000
        session.add(
            Operation(
                ext_operation_id=f"audit-op-{merchant_id}-{idx}",
                operation_type=OperationType.COMMIT,
                status=OperationStatus.CAPTURED,
                created_at=base_dt + timedelta(hours=idx + 1),
                updated_at=base_dt + timedelta(hours=idx + 1),
                merchant_id=merchant_id,
                terminal_id="t-1",
                client_id=client_id,
                card_id="card-1",
                product_id="FUEL",
                product_type=ProductType.AI92,
                amount=amount,
                amount_settled=amount,
                currency="RUB",
                quantity=Decimal("1.0"),
                unit_price=Decimal(str(amount)),
                captured_amount=amount,
                refunded_amount=0,
                response_code="00",
                response_message="OK",
                authorized=True,
            )
        )
    session.commit()
    session.close()


def test_audit_hash_chain_and_verify(admin_auth_headers: dict):
    session = get_sessionmaker()()
    service = AuditService(session)
    ctx = RequestContext(actor_type=ActorType.SYSTEM, actor_id="test")

    first = service.audit(
        event_type="PAYMENT_POSTED",
        entity_type="payment",
        entity_id="pay-1",
        action="CREATE",
        after={"amount": 100},
        request_ctx=ctx,
    )
    second = service.audit(
        event_type="REFUND_POSTED",
        entity_type="refund",
        entity_id="ref-1",
        action="CREATE",
        after={"amount": 50},
        request_ctx=ctx,
    )
    service.audit(
        event_type="PAYOUT_BATCH_CREATED",
        entity_type="payout_batch",
        entity_id="batch-1",
        action="CREATE",
        after={"total": 123},
        request_ctx=ctx,
    )
    session.commit()
    assert second.prev_hash == first.hash

    with TestClient(app) as client:
        client.headers.update(admin_auth_headers)
        response = client.post(
            "/api/v1/audit/verify",
            json={
                "from": "2000-01-01T00:00:00Z",
                "to": "2100-01-01T00:00:00Z",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "OK"
    assert body["checked"] == 3


def test_audit_immutable_enforcement():
    session = get_sessionmaker()()
    service = AuditService(session)
    ctx = RequestContext(actor_type=ActorType.SYSTEM, actor_id="test")
    record = service.audit(
        event_type="PAYMENT_POSTED",
        entity_type="payment",
        entity_id="immutable-1",
        action="CREATE",
        after={"amount": 100},
        request_ctx=ctx,
    )
    session.commit()

    if engine.dialect.name == "postgresql":
        with pytest.raises(Exception):
            session.execute(text("UPDATE audit_log SET event_type = 'HACK' WHERE id = :id"), {"id": record.id})
        with pytest.raises(Exception):
            session.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": record.id})
    session.close()


def test_audit_search_by_external_ref(admin_auth_headers: dict):
    session = get_sessionmaker()()
    service = AuditService(session)
    ctx = RequestContext(actor_type=ActorType.SYSTEM, actor_id="test")
    service.audit(
        event_type="PAYMENT_POSTED",
        entity_type="payment",
        entity_id="pay-ext-1",
        action="CREATE",
        after={"amount": 150},
        external_refs={"provider": "bank", "external_ref": "BANK-REF-1"},
        request_ctx=ctx,
    )
    session.commit()

    with TestClient(app) as client:
        client.headers.update(admin_auth_headers)
        response = client.get("/api/v1/audit/search", params={"external_ref": "BANK-REF-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["event_type"] == "PAYMENT_POSTED"


def test_finance_flow_emits_audit(client_auth_headers: dict, admin_auth_headers: dict):
    target_date = date.today()
    _seed_captured_operations(target_date, merchant_id="m-1", client_id="client-1")

    with TestClient(app) as client:
        close_resp = client.post(
            "/api/v1/billing/close-period",
            json={"date_from": target_date.isoformat(), "date_to": target_date.isoformat(), "tenant_id": 1},
        )
        assert close_resp.status_code == 200
        batch_id = close_resp.json()["batch_id"]

        invoice_resp = client.post("/api/v1/invoices/generate", params={"batch_id": batch_id})
        assert invoice_resp.status_code == 200
        invoice_id = invoice_resp.json()["invoice_id"]

        client.headers.update(client_auth_headers)
        payment_resp = client.post(
            f"/api/v1/invoices/{invoice_id}/payments",
            json={"amount": 3000, "external_ref": "BANK-111"},
        )
        assert payment_resp.status_code == 201

        refund_resp = client.post(
            f"/api/v1/invoices/{invoice_id}/refunds",
            json={"amount": 500, "external_ref": "REF-111", "provider": "bank"},
        )
        assert refund_resp.status_code == 201

        _seed_captured_operations(target_date, merchant_id="partner-1", client_id="client-2")
        payout_resp = client.post(
            "/api/v1/payouts/close-period",
            json={
                "tenant_id": 1,
                "partner_id": "partner-1",
                "date_from": target_date.isoformat(),
                "date_to": target_date.isoformat(),
            },
        )
        assert payout_resp.status_code == 200
        payout_batch_id = payout_resp.json()["batch_id"]

        mark_sent = client.post(
            f"/api/v1/payouts/batches/{payout_batch_id}/mark-sent",
            json={"provider": "bank", "external_ref": "PAYOUT-1"},
        )
        assert mark_sent.status_code == 200

        reconcile = client.get(f"/api/v1/payouts/batches/{payout_batch_id}/reconcile")
        assert reconcile.status_code == 200

        export_resp = client.post(
            f"/api/v1/payouts/batches/{payout_batch_id}/export",
            json={"format": "CSV", "provider": "bank", "external_ref": "EXPORT-1"},
        )
        assert export_resp.status_code == 200

    session = get_sessionmaker()()
    event_types = {row.event_type for row in session.query(AuditLog.event_type).all()}
    expected = {
        "INVOICE_CREATED",
        "PAYMENT_POSTED",
        "REFUND_POSTED",
        "PAYOUT_BATCH_CREATED",
        "PAYOUT_STATUS_CHANGED",
        "PAYOUT_RECONCILE_OK",
        "PAYOUT_EXPORT_CREATED",
        "PAYOUT_EXPORT_UPLOADED",
    }
    assert expected.issubset(event_types)
    session.close()
