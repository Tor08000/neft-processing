from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger, Column, DateTime, Integer, MetaData, Numeric, String, Table, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.schema import DB_SCHEMA
from app.services.audit_service import AuditService
from app.services.subscription_billing import generate_invoice_pdf, generate_invoices_for_period
from app.services import subscription_billing as subscription_billing_service


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


def test_generate_invoices_for_period_uses_billing_flow_issue_invoice_when_live_storage_is_uuid_shaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AuditService, "audit", lambda self, **kwargs: None)
    captured: dict[str, object] = {}

    def _fake_issue_invoice(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(invoice=SimpleNamespace(id="inv-flow-1"), is_replay=False)

    monkeypatch.setattr(subscription_billing_service, "issue_invoice", _fake_issue_invoice)

    engine = _engine()

    metadata = MetaData()
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("plan_id", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        Column("start_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    subscription_plans = Table(
        "subscription_plans",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("code", String(64), nullable=False),
        Column("title", String(128), nullable=True),
        Column("billing_period_months", Integer, nullable=False),
        Column("price_cents", Integer, nullable=True),
        Column("currency", String(8), nullable=True),
        schema=DB_SCHEMA,
    )
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
            subscription_plans.insert().values(
                id="plan-control",
                code="CONTROL",
                title="Control plan",
                billing_period_months=1,
                price_cents=129900,
                currency="RUB",
            )
        )
        db.execute(
            client_subscriptions.insert().values(
                id="legacy-sub-1",
                tenant_id=101,
                client_id="client-1",
                plan_id="plan-control",
                status="ACTIVE",
                start_at=now,
                created_at=now,
            )
        )
        db.commit()

        invoice_ids = generate_invoices_for_period(
            db,
            target_date=now.date(),
            org_id=101,
            request_ctx=None,
        )

    assert invoice_ids == ["inv-flow-1"]
    assert captured["tenant_id"] == 101
    assert captured["client_id"] == "client-1"
    assert captured["currency"] == "RUB"
    assert str(captured["amount_total"]) == "1299"
    assert captured["idempotency_key"] == "subscription-invoice:legacy-sub-1:2026-03-01:2026-03-31"


def test_generate_invoices_for_period_reuses_existing_billing_flow_invoice_without_idempotency_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AuditService, "audit", lambda self, **kwargs: None)

    def _unexpected_issue_invoice(db, **kwargs):
        raise AssertionError("issue_invoice should not be called when billing-flow invoice already exists")

    monkeypatch.setattr(subscription_billing_service, "issue_invoice", _unexpected_issue_invoice)

    engine = _engine()

    metadata = MetaData()
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("plan_id", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        Column("start_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    subscription_plans = Table(
        "subscription_plans",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("code", String(64), nullable=False),
        Column("title", String(128), nullable=True),
        Column("billing_period_months", Integer, nullable=False),
        Column("price_cents", Integer, nullable=True),
        Column("currency", String(8), nullable=True),
        schema=DB_SCHEMA,
    )
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
            subscription_plans.insert().values(
                id="plan-control",
                code="CONTROL",
                title="Control plan",
                billing_period_months=1,
                price_cents=129900,
                currency="RUB",
            )
        )
        db.execute(
            client_subscriptions.insert().values(
                id="legacy-sub-1",
                tenant_id=101,
                client_id="client-1",
                plan_id="plan-control",
                status="ACTIVE",
                start_at=now,
                created_at=now,
            )
        )
        db.execute(
            billing_invoices.insert().values(
                id="inv-existing-1",
                invoice_number="INV-EXISTING-1",
                client_id="client-1",
                currency="RUB",
                amount_total=Decimal("999"),
                amount_paid=Decimal("0"),
                status="ISSUED",
                issued_at=now,
                due_at=now,
                idempotency_key="subscription-invoice:legacy-sub-1:2026-03-01:2026-03-31",
                ledger_tx_id="ledger-existing-1",
                audit_event_id="audit-existing-1",
                created_at=now,
            )
        )
        db.commit()

        invoice_ids = generate_invoices_for_period(
            db,
            target_date=now.date(),
            org_id=101,
            request_ctx=None,
        )

    assert invoice_ids == []


def test_generate_invoice_pdf_routes_existing_billing_flow_invoice_to_pdf_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    called: dict[str, object] = {}

    def _fake_generate_billing_flow_invoice_pdf(db: Session, *, invoice_id: object, invoice: dict | None = None) -> bool:
        called["invoice_id"] = invoice_id
        called["invoice_number"] = invoice["invoice_number"] if invoice else None
        return True

    monkeypatch.setattr(
        subscription_billing_service,
        "_generate_billing_flow_invoice_pdf",
        _fake_generate_billing_flow_invoice_pdf,
    )

    with Session(bind=engine) as db:
        now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
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
                idempotency_key="subscription-invoice:legacy-sub-1:2026-03-01:2026-03-31",
                ledger_tx_id="ledger-1",
                audit_event_id="audit-1",
                created_at=now,
            )
        )
        db.commit()

        assert generate_invoice_pdf(db, invoice_id="inv-flow-1") is True

    assert called == {"invoice_id": "inv-flow-1", "invoice_number": "INV-FLOW-1"}


def test_generate_invoice_pdf_persists_billing_flow_pdf_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AuditService, "audit", lambda self, **kwargs: None)

    class _MemoryStorage:
        blobs: dict[str, bytes] = {}

        def ensure_bucket(self) -> None:
            return None

        def put_bytes(self, key: str, payload: bytes, *, content_type: str | None = None) -> str:
            self.blobs[key] = payload
            return f"memory://{key}"

    monkeypatch.setattr(subscription_billing_service, "S3Storage", _MemoryStorage)

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
        Column("pdf_status", String(32), nullable=False),
        Column("pdf_object_key", String(512), nullable=True),
        Column("pdf_url", String(512), nullable=True),
        Column("pdf_hash", String(64), nullable=True),
        Column("pdf_generated_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    metadata.create_all(bind=engine)

    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.execute(
            billing_invoices.insert().values(
                id="inv-flow-2",
                invoice_number="INV-FLOW-2",
                client_id="client-2",
                currency="RUB",
                amount_total=Decimal("1299"),
                amount_paid=Decimal("100"),
                status="PARTIALLY_PAID",
                issued_at=now,
                due_at=now,
                idempotency_key="subscription-invoice:legacy-sub-2:2026-03-01:2026-03-31",
                ledger_tx_id="ledger-2",
                audit_event_id="audit-2",
                created_at=now,
                pdf_status="NONE",
            )
        )
        db.commit()

        assert generate_invoice_pdf(db, invoice_id="inv-flow-2") is True

        stored = db.execute(billing_invoices.select()).mappings().one()

    assert stored["pdf_status"] == "READY"
    assert stored["pdf_object_key"] == "billing-invoices/inv-flow-2.pdf"
    assert stored["pdf_url"] == "memory://billing-invoices/inv-flow-2.pdf"
    assert len(stored["pdf_hash"]) == 64
    assert stored["pdf_generated_at"] is not None
    assert _MemoryStorage.blobs["billing-invoices/inv-flow-2.pdf"].startswith(b"%PDF")


def test_coerce_pricing_catalog_item_id_returns_none_for_bigint_catalog_and_uuid_plan_id() -> None:
    metadata = MetaData()
    pricing_catalog = Table(
        "pricing_catalog",
        metadata,
        Column("item_id", BigInteger, nullable=False),
    )

    resolved = subscription_billing_service._coerce_pricing_catalog_item_id(
        pricing_catalog.c.item_id,
        "f9ab795a-d061-4af1-b3f3-070da3f78040",
    )

    assert resolved is None


def test_generate_invoices_for_period_skips_zero_total_subscription_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AuditService, "audit", lambda self, **kwargs: None)

    def _unexpected_issue_invoice(db, **kwargs):
        raise AssertionError("issue_invoice should not be called for zero-total subscriptions")

    monkeypatch.setattr(subscription_billing_service, "issue_invoice", _unexpected_issue_invoice)

    engine = _engine()
    metadata = MetaData()
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("plan_id", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        Column("start_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    subscription_plans = Table(
        "subscription_plans",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("code", String(64), nullable=False),
        Column("title", String(128), nullable=True),
        Column("billing_period_months", Integer, nullable=False),
        Column("price_cents", Integer, nullable=True),
        Column("currency", String(8), nullable=True),
        schema=DB_SCHEMA,
    )
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
            subscription_plans.insert().values(
                id="plan-free",
                code="FREE",
                title="Free plan",
                billing_period_months=1,
                price_cents=0,
                currency="RUB",
            )
        )
        db.execute(
            client_subscriptions.insert().values(
                id="legacy-sub-free",
                tenant_id=101,
                client_id="client-1",
                plan_id="plan-free",
                status="ACTIVE",
                start_at=now,
                created_at=now,
            )
        )
        db.commit()

        invoice_ids = generate_invoices_for_period(db, target_date=now.date(), org_id=101, request_ctx=None)

    assert invoice_ids == []
