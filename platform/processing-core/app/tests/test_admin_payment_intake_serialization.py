from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, Request
import pytest

from app.routers.admin import billing_payment_intakes, finance
from app.schemas.billing_payment_intakes import PaymentIntakeApproveRequest


def _payment_intake_row(*, invoice_id):
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    return {
        "id": 101,
        "org_id": 1,
        "invoice_id": invoice_id,
        "status": "UNDER_REVIEW",
        "amount": Decimal("1250.00"),
        "currency": "RUB",
        "payer_name": "ООО Клиент",
        "payer_inn": "7701001001",
        "bank_reference": "PAY-101",
        "paid_at_claimed": date(2026, 4, 15),
        "comment": "manual upload",
        "created_by_user_id": "client-user-1",
        "reviewed_by_admin": None,
        "reviewed_at": None,
        "review_note": None,
        "created_at": now,
    }


def test_admin_billing_payment_intake_serializer_stringifies_uuid_invoice_id() -> None:
    invoice_id = uuid4()

    payload = billing_payment_intakes._serialize_payment_intake(_payment_intake_row(invoice_id=invoice_id))

    assert payload.invoice_id == str(invoice_id)


def test_admin_finance_payment_intake_serializer_stringifies_uuid_invoice_id() -> None:
    invoice_id = uuid4()

    payload = finance._serialize_payment_intake(_payment_intake_row(invoice_id=invoice_id))

    assert payload.invoice_id == str(invoice_id)
    assert payload.invoice_link == f"/finance/invoices/{invoice_id}"


class _AuditServiceStub:
    def __init__(self, _db) -> None:
        self.db = _db

    def audit(self, *args, **kwargs) -> None:
        return None


class _DbStub:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/core/v1/admin/billing/payment-intakes/101/approve",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


def test_admin_billing_payment_intake_approve_uses_intake_org_when_invoice_row_has_only_client_id(
    monkeypatch,
) -> None:
    invoice_id = uuid4()
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    intake = {
        **_payment_intake_row(invoice_id=invoice_id),
        "status": "SUBMITTED",
    }
    updated = {
        **intake,
        "status": "APPROVED",
        "reviewed_by_admin": "admin-1",
        "reviewed_at": now,
        "review_note": "matched",
    }
    captured: dict[str, object] = {}

    monkeypatch.setattr(billing_payment_intakes, "get_payment_intake", lambda db, *, intake_id: intake)
    monkeypatch.setattr(billing_payment_intakes, "review_payment_intake", lambda db, **kwargs: updated)
    monkeypatch.setattr(
        billing_payment_intakes,
        "approve_invoice_payment_intake",
        lambda db, *, intake, request_ctx: {"id": str(invoice_id), "client_id": "client-flow-1"},
    )
    monkeypatch.setattr(
        billing_payment_intakes,
        "get_org_entitlements_snapshot",
        lambda db, *, org_id, force_new_version=False: captured.setdefault(
            "snapshot_call",
            {"org_id": org_id, "force_new_version": force_new_version},
        ),
    )
    monkeypatch.setattr(billing_payment_intakes, "resolve_client_email", lambda db, org_id: None)
    monkeypatch.setattr(billing_payment_intakes, "create_notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(billing_payment_intakes, "AuditService", _AuditServiceStub)

    db = _DbStub()
    payload = PaymentIntakeApproveRequest(review_note="matched")

    result = billing_payment_intakes.approve_payment_intake(
        101,
        payload,
        _request(),
        token={"user_id": "admin-1"},
        db=db,
    )

    assert captured["snapshot_call"] == {"org_id": 1, "force_new_version": True}
    assert result.invoice_id == str(invoice_id)
    assert db.commits == 1


def test_admin_billing_payment_intake_approve_returns_409_for_already_paid_invoice(monkeypatch) -> None:
    invoice_id = uuid4()
    intake = {
        **_payment_intake_row(invoice_id=invoice_id),
        "status": "SUBMITTED",
    }
    updated = {
        **intake,
        "status": "APPROVED",
        "reviewed_by_admin": "admin-1",
        "reviewed_at": datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc),
        "review_note": "matched",
    }

    monkeypatch.setattr(billing_payment_intakes, "get_payment_intake", lambda db, *, intake_id: intake)
    monkeypatch.setattr(billing_payment_intakes, "review_payment_intake", lambda db, **kwargs: updated)
    monkeypatch.setattr(
        billing_payment_intakes,
        "approve_invoice_payment_intake",
        lambda db, *, intake, request_ctx: (_ for _ in ()).throw(ValueError("invoice_already_paid")),
    )

    with pytest.raises(HTTPException) as exc_info:
        billing_payment_intakes.approve_payment_intake(
            101,
            PaymentIntakeApproveRequest(review_note="matched"),
            _request(),
            token={"user_id": "admin-1"},
            db=_DbStub(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "invoice_already_paid"
