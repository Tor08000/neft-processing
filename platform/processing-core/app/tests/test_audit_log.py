from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Iterator

import pytest
from fastapi import APIRouter
from sqlalchemy import Column, String, text
from sqlalchemy.orm import Session

import app.services.billing_invoice_service as billing_invoice_service
from app.api.dependencies.admin import require_admin_user
from app.api.v1.endpoints.audit import router as audit_router
from app.api.v1.endpoints.billing_invoices import router as billing_router
from app.db import get_sessionmaker
from app.models.audit_log import ActorType, AuditLog
from app.models.billing_job_run import BillingJobRun
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation, PaymentStatus
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.invoice import Invoice, InvoicePdfStatus
from app.models.legal_graph import LegalEdge, LegalNode
from app.models.money_flow import MoneyFlowEvent
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.abac.engine import AbacDecision, AbacEngine
from app.services.audit_service import AuditService, RequestContext
from app.services.decision import DecisionEngine, DecisionOutcome
from app.services.finance import FinanceService
from app.tests._money_router_harness import (
    ADMIN_BILLING_INVOICE_TEST_TABLES,
    PAYOUT_TEST_TABLES,
    money_session_context,
    payout_client_context,
)
from app.tests._scoped_router_harness import router_client_context, scoped_session_context

os.environ.setdefault("DISABLE_CELERY", "1")
os.environ.setdefault("NEFT_S3_ENDPOINT", "http://minio:9000")
os.environ.setdefault("NEFT_S3_ACCESS_KEY", "change-me")
os.environ.setdefault("NEFT_S3_SECRET_KEY", "change-me")
os.environ.setdefault("NEFT_S3_BUCKET_INVOICES", "neft-invoices")
os.environ.setdefault("NEFT_S3_BUCKET_PAYOUTS", "neft-payouts")
os.environ.setdefault("NEFT_S3_REGION", "us-east-1")


def _dedupe_tables(*tables):
    seen: set[str] = set()
    ordered = []
    for table in tables:
        key = str(getattr(table, "key", table))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(table)
    return tuple(ordered)


AUDIT_TEST_TABLES = (AuditLog.__table__,)
FINANCE_AUDIT_TEST_TABLES = _dedupe_tables(
    *ADMIN_BILLING_INVOICE_TEST_TABLES,
    *PAYOUT_TEST_TABLES,
    BillingJobRun.__table__,
    CreditNote.__table__,
    InvoicePayment.__table__,
    InvoiceSettlementAllocation.__table__,
    InternalLedgerAccount.__table__,
    InternalLedgerEntry.__table__,
    InternalLedgerTransaction.__table__,
    LegalNode.__table__,
    LegalEdge.__table__,
    MoneyFlowEvent.__table__,
)


class _AllowDecisionEngine:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def evaluate(self, _ctx):
        return type("Decision", (), {"outcome": billing_invoice_service.DecisionOutcome.ALLOW})()


class _NoopGraphBuilder:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def ensure_invoice_graph(self, *args, **kwargs) -> None:
        return None


class _MemoryInvoiceStorage:
    _objects: dict[str, bytes] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    @classmethod
    def reset(cls) -> None:
        cls._objects = {}

    def ensure_bucket(self) -> None:
        return None

    def put_bytes(self, object_key: str, payload: bytes, *, content_type: str) -> str:
        self._objects[object_key] = payload
        return self.public_url(object_key)

    def exists(self, object_key: str) -> bool:
        return object_key in self._objects

    def get_bytes(self, object_key: str) -> bytes | None:
        return self._objects.get(object_key)

    def public_url(self, object_key: str) -> str:
        return f"https://test-s3.local/{object_key}"


class _MemoryInvoicePdfService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = _MemoryInvoiceStorage()

    def generate(self, invoice: Invoice, *, force: bool = False) -> Invoice:
        key = invoice.pdf_object_key or f"invoices/{invoice.id}.pdf"
        payload = b"%PDF-1.4 test invoice pdf%"
        invoice.pdf_status = InvoicePdfStatus.READY
        invoice.pdf_generated_at = datetime.now(timezone.utc)
        invoice.pdf_object_key = key
        invoice.pdf_url = self.storage.put_bytes(key, payload, content_type="application/pdf")
        self.db.add(invoice)
        return invoice


class _InMemoryPayoutStorage:
    _objects: dict[tuple[str, str], bytes] = {}

    def __init__(self, *, bucket: str | None = None):
        self.bucket = bucket or "neft-payouts"

    def put_bytes(self, key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> str:
        self._objects[(self.bucket, key)] = payload
        return f"s3://{self.bucket}/{key}"

    def exists(self, key: str) -> bool:
        return (self.bucket, key) in self._objects

    def get_bytes(self, key: str) -> bytes | None:
        return self._objects.get((self.bucket, key))


@pytest.fixture(autouse=True)
def _stub_billing_and_payout_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1.endpoints import payouts as payouts_api
    from app.services import payout_exports as payout_exports_service

    monkeypatch.setattr(billing_invoice_service, "DecisionEngine", _AllowDecisionEngine)
    monkeypatch.setattr(billing_invoice_service, "LegalGraphBuilder", _NoopGraphBuilder)
    monkeypatch.setattr(billing_invoice_service, "InvoicePdfService", _MemoryInvoicePdfService)

    monkeypatch.setattr(
        DecisionEngine,
        "evaluate",
        lambda *_args, **_kwargs: SimpleNamespace(outcome=DecisionOutcome.ALLOW),
    )
    monkeypatch.setattr(
        AbacEngine,
        "evaluate",
        lambda *_args, **_kwargs: AbacDecision(True, None, [], {"result": True}),
    )
    _MemoryInvoiceStorage.reset()
    _InMemoryPayoutStorage._objects = {}
    monkeypatch.setattr(payout_exports_service, "S3Storage", _InMemoryPayoutStorage)
    monkeypatch.setattr(payouts_api, "S3Storage", _InMemoryPayoutStorage)


def _admin_token_override() -> dict[str, object]:
    return {
        "sub": "admin-1",
        "user_id": "admin-1",
        "roles": ["ADMIN", "ADMIN_FINANCE", "SUPERADMIN"],
        "tenant_id": "1",
    }


@contextmanager
def audit_client_context(*, db_session: Session) -> Iterator:
    router = APIRouter()
    router.include_router(audit_router)
    with router_client_context(
        router=router,
        db_session=db_session,
        dependency_overrides={require_admin_user: _admin_token_override},
    ) as client:
        yield client


@contextmanager
def billing_client_context(*, db_session: Session) -> Iterator:
    with router_client_context(router=billing_router, db_session=db_session) as client:
        yield client


def _seed_captured_operations(db_session: Session, target_date: date, *, merchant_id: str, client_id: str) -> None:
    base_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    for idx in range(2):
        amount = 2000 + idx * 1000
        db_session.add(
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
    db_session.commit()


def _seed_billing_period(db_session: Session, target_date: date, status: BillingPeriodStatus) -> None:
    period = BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
        end_at=datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc),
        tz="UTC",
        status=status,
    )
    db_session.add(period)
    db_session.commit()


def test_audit_hash_chain_and_verify() -> None:
    with scoped_session_context(tables=AUDIT_TEST_TABLES) as session:
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

        with audit_client_context(db_session=session) as client:
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


def test_audit_immutable_enforcement() -> None:
    with scoped_session_context(tables=AUDIT_TEST_TABLES) as session:
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

        if session.get_bind().dialect.name == "postgresql":
            with pytest.raises(Exception):
                session.execute(
                    text("UPDATE audit_log SET event_type = 'IMMUTABLE_TEST' WHERE id = :id"),
                    {"id": record.id},
                )
            with pytest.raises(Exception):
                session.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": record.id})


def test_audit_search_by_external_ref() -> None:
    with scoped_session_context(tables=AUDIT_TEST_TABLES) as session:
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

        with audit_client_context(db_session=session) as client:
            response = client.get("/api/v1/audit/search", params={"external_ref": "BANK-REF-1"})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["event_type"] == "PAYMENT_POSTED"


def test_finance_flow_emits_audit() -> None:
    target_date = date.today()
    payout_date = target_date + timedelta(days=1)
    with money_session_context(tables=FINANCE_AUDIT_TEST_TABLES) as session:
        _seed_captured_operations(session, target_date, merchant_id="m-1", client_id="client-1")
        _seed_billing_period(session, target_date, BillingPeriodStatus.OPEN)

        with billing_client_context(db_session=session) as client:
            close_resp = client.post(
                "/api/v1/billing/close-period",
                json={"date_from": target_date.isoformat(), "date_to": target_date.isoformat(), "tenant_id": 1},
            )
            assert close_resp.status_code == 200
            batch_id = close_resp.json()["batch_id"]

            invoice_resp = client.post("/api/v1/invoices/generate", params={"batch_id": batch_id})
            assert invoice_resp.status_code == 200
            invoice_id = invoice_resp.json()["invoice_id"]

        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one()
        period = session.query(BillingPeriod).filter(BillingPeriod.id == invoice.billing_period_id).one()
        period.status = BillingPeriodStatus.FINALIZED
        session.add(period)
        session.commit()

        finance_service = FinanceService(session)
        payment_result = finance_service.apply_payment(
            invoice_id=invoice_id,
            amount=3000,
            currency="RUB",
            idempotency_key="AUDIT-PAY-1",
            request_ctx=RequestContext(actor_type=ActorType.USER, actor_id="admin-1", tenant_id=1),
            token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "admin-1", "user_id": "admin-1", "tenant_id": 1},
        )
        session.commit()
        AuditService(session).audit(
            event_type="PAYMENT_POSTED",
            entity_type="payment",
            entity_id=str(payment_result.payment.id),
            action="CREATE",
            after={
                "invoice_id": payment_result.payment.invoice_id,
                "amount": payment_result.payment.amount,
                "currency": payment_result.payment.currency,
                "status": payment_result.payment.status.value if payment_result.payment.status else PaymentStatus.POSTED.value,
                "invoice_status": payment_result.invoice.status.value if payment_result.invoice.status else None,
            },
            request_ctx=RequestContext(actor_type=ActorType.USER, actor_id="admin-1", tenant_id=1),
        )
        session.commit()

        _seed_captured_operations(session, payout_date, merchant_id="partner-1", client_id="client-2")
        _seed_billing_period(session, payout_date, BillingPeriodStatus.FINALIZED)

        with payout_client_context(db_session=session) as client:
            payout_resp = client.post(
                "/api/v1/payouts/close-period",
                json={
                    "tenant_id": 1,
                    "partner_id": "partner-1",
                    "date_from": payout_date.isoformat(),
                    "date_to": payout_date.isoformat(),
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

        event_types = {row.event_type for row in session.query(AuditLog.event_type).all()}
        expected = {
            "INVOICE_CREATED",
            "PAYMENT_POSTED",
            "PAYOUT_BATCH_CREATED",
            "PAYOUT_STATUS_CHANGED",
            "PAYOUT_RECONCILE_OK",
            "PAYOUT_EXPORT_CREATED",
            "PAYOUT_EXPORT_UPLOADED",
        }
        assert expected.issubset(event_types)
