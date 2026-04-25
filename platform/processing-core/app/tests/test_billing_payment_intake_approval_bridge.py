from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.schema import DB_SCHEMA
from app.models.audit_log import ActorType
from app.services import billing_payment_intakes as payment_intakes_service
from app.services.audit_service import RequestContext


def _engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_processing_core(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE ':memory:' AS {DB_SCHEMA}")
        cursor.close()

    return engine


def test_approve_invoice_payment_intake_uses_capture_payment_for_billing_flow_invoice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_capture_payment(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(payment=SimpleNamespace(id="payment-1"), invoice=SimpleNamespace(id=kwargs["invoice_id"]))

    monkeypatch.setattr(payment_intakes_service, "capture_payment", _fake_capture_payment)

    engine = _engine()
    metadata = MetaData()
    billing_invoices = Table(
        "billing_invoices",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("invoice_number", String(64), nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("currency", String(8), nullable=False),
        Column("amount_total", Numeric(18, 4), nullable=False),
        Column("amount_paid", Numeric(18, 4), nullable=False),
        Column("status", String(32), nullable=False),
        Column("issued_at", DateTime(timezone=True), nullable=False),
        Column("due_at", DateTime(timezone=True), nullable=True),
        Column("idempotency_key", String(128), nullable=False),
        Column("ledger_tx_id", String(64), nullable=False),
        Column("audit_event_id", String(64), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    metadata.create_all(bind=engine)

    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.execute(
            billing_invoices.insert().values(
                id="inv-flow-1",
                invoice_number="INV-FLOW-1",
                client_id="client-1",
                currency="RUB",
                amount_total=Decimal("1299"),
                amount_paid=Decimal("0"),
                status="ISSUED",
                issued_at=now,
                due_at=now,
                idempotency_key="inv-key",
                ledger_tx_id="ledger-1",
                audit_event_id="audit-1",
                created_at=now,
            )
        )
        db.commit()

        invoice = payment_intakes_service.approve_invoice_payment_intake(
            db,
            intake={
                "id": 77,
                "org_id": 101,
                "invoice_id": "inv-flow-1",
                "amount": Decimal("1299"),
                "currency": "RUB",
                "bank_reference": "BANK-REF-1",
            },
            request_ctx=RequestContext(actor_type=ActorType.USER, actor_id="admin-1", actor_email="admin@neft.local"),
        )

    assert invoice is not None
    assert invoice["id"] == "inv-flow-1"
    assert captured["tenant_id"] == 101
    assert captured["invoice_id"] == "inv-flow-1"
    assert captured["provider"] == "MANUAL_PAYMENT_INTAKE"
    assert captured["provider_payment_id"] == "BANK-REF-1"
    assert captured["idempotency_key"] == "payment-intake:77"


def test_get_invoice_accepts_string_for_legacy_numeric_invoice_id() -> None:
    engine = _engine()
    metadata = MetaData()
    billing_invoices = Table(
        "billing_invoices",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("org_id", Integer, nullable=False),
        Column("subscription_id", String(64), nullable=True),
        Column("status", String(32), nullable=False),
        Column("total_amount", Numeric(18, 2), nullable=True),
        Column("currency", String(8), nullable=True),
        Column("issued_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    metadata.create_all(bind=engine)

    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.execute(
            billing_invoices.insert().values(
                id=701,
                org_id=101,
                subscription_id="legacy-sub-1",
                status="ISSUED",
                total_amount=Decimal("1000.00"),
                currency="RUB",
                issued_at=now,
                created_at=now,
            )
        )
        db.commit()

        invoice = payment_intakes_service.get_invoice(db, invoice_id="701")

    assert invoice is not None
    assert invoice["id"] == 701


def test_approve_invoice_payment_intake_rejects_already_paid_billing_flow_invoice() -> None:
    engine = _engine()
    metadata = MetaData()
    billing_invoices = Table(
        "billing_invoices",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("invoice_number", String(64), nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("currency", String(8), nullable=False),
        Column("amount_total", Numeric(18, 4), nullable=False),
        Column("amount_paid", Numeric(18, 4), nullable=False),
        Column("status", String(32), nullable=False),
        Column("issued_at", DateTime(timezone=True), nullable=False),
        Column("due_at", DateTime(timezone=True), nullable=True),
        Column("idempotency_key", String(128), nullable=False),
        Column("ledger_tx_id", String(64), nullable=False),
        Column("audit_event_id", String(64), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    metadata.create_all(bind=engine)

    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.execute(
            billing_invoices.insert().values(
                id="inv-paid-1",
                invoice_number="INV-PAID-1",
                client_id="client-1",
                currency="RUB",
                amount_total=Decimal("299"),
                amount_paid=Decimal("299"),
                status="PAID",
                issued_at=now,
                due_at=now,
                idempotency_key="inv-paid-key",
                ledger_tx_id="ledger-paid-1",
                audit_event_id="audit-paid-1",
                created_at=now,
            )
        )
        db.commit()

        with pytest.raises(ValueError, match="invoice_already_paid"):
            payment_intakes_service.approve_invoice_payment_intake(
                db,
                intake={
                    "id": 78,
                    "org_id": 101,
                    "invoice_id": "inv-paid-1",
                    "amount": Decimal("299"),
                    "currency": "RUB",
                    "bank_reference": "BANK-REF-PAID",
                },
                request_ctx=RequestContext(actor_type=ActorType.USER, actor_id="admin-1", actor_email="admin@neft.local"),
            )


def test_approve_invoice_payment_intake_rejects_overpay_against_billing_flow_invoice() -> None:
    engine = _engine()
    metadata = MetaData()
    billing_invoices = Table(
        "billing_invoices",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("invoice_number", String(64), nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("currency", String(8), nullable=False),
        Column("amount_total", Numeric(18, 4), nullable=False),
        Column("amount_paid", Numeric(18, 4), nullable=False),
        Column("status", String(32), nullable=False),
        Column("issued_at", DateTime(timezone=True), nullable=False),
        Column("due_at", DateTime(timezone=True), nullable=True),
        Column("idempotency_key", String(128), nullable=False),
        Column("ledger_tx_id", String(64), nullable=False),
        Column("audit_event_id", String(64), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    metadata.create_all(bind=engine)

    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.execute(
            billing_invoices.insert().values(
                id="inv-partial-1",
                invoice_number="INV-PARTIAL-1",
                client_id="client-1",
                currency="RUB",
                amount_total=Decimal("299"),
                amount_paid=Decimal("200"),
                status="PARTIALLY_PAID",
                issued_at=now,
                due_at=now,
                idempotency_key="inv-partial-key",
                ledger_tx_id="ledger-partial-1",
                audit_event_id="audit-partial-1",
                created_at=now,
            )
        )
        db.commit()

        with pytest.raises(ValueError, match="payment_amount_exceeds_due"):
            payment_intakes_service.approve_invoice_payment_intake(
                db,
                intake={
                    "id": 79,
                    "org_id": 101,
                    "invoice_id": "inv-partial-1",
                    "amount": Decimal("150"),
                    "currency": "RUB",
                    "bank_reference": "BANK-REF-OVERPAY",
                },
                request_ctx=RequestContext(actor_type=ActorType.USER, actor_id="admin-1", actor_email="admin@neft.local"),
            )


def test_approve_invoice_payment_intake_reactivates_subscription_storage_after_paid_billing_flow_invoice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {"phase": "before"}

    def _fake_get_invoice(db, *, invoice_id):
        if observed["phase"] == "before":
            return {
                "id": str(invoice_id),
                "client_id": "client-1",
                "invoice_number": "INV-1",
                "currency": "RUB",
                "amount_total": Decimal("299"),
                "amount_paid": Decimal("0"),
                "status": "ISSUED",
                "issued_at": datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc),
                "idempotency_key": "invoice-key",
                "ledger_tx_id": "ledger-1",
                "audit_event_id": "audit-1",
            }
        return {
            "id": str(invoice_id),
            "client_id": "client-1",
            "invoice_number": "INV-1",
            "currency": "RUB",
            "amount_total": Decimal("299"),
            "amount_paid": Decimal("299"),
            "status": "PAID",
            "issued_at": datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc),
            "idempotency_key": "invoice-key",
            "ledger_tx_id": "ledger-1",
            "audit_event_id": "audit-1",
        }

    def _fake_capture_payment(db, **kwargs):
        observed["phase"] = "after"
        return SimpleNamespace(payment=SimpleNamespace(id="payment-1"), invoice=SimpleNamespace(id=kwargs["invoice_id"]))

    monkeypatch.setattr(payment_intakes_service, "get_invoice", _fake_get_invoice)
    monkeypatch.setattr(payment_intakes_service, "capture_payment", _fake_capture_payment)
    monkeypatch.setattr(
        payment_intakes_service,
        "reactivate_subscription_storage",
        lambda db, *, tenant_id: observed.setdefault("tenant_id", tenant_id),
    )

    invoice = payment_intakes_service.approve_invoice_payment_intake(
        db=object(),
        intake={
            "id": 80,
            "org_id": 101,
            "invoice_id": "inv-paid-bridge",
            "amount": Decimal("299"),
            "currency": "RUB",
            "bank_reference": "BANK-REF-PAID",
        },
        request_ctx=RequestContext(actor_type=ActorType.USER, actor_id="admin-1", actor_email="admin@neft.local"),
    )

    assert invoice is not None
    assert invoice["status"] == "PAID"
    assert observed["tenant_id"] == 101
