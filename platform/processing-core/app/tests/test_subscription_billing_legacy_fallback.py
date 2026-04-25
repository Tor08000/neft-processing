from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table, create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.schema import DB_SCHEMA
from app.services.audit_service import AuditService
from app.services.subscription_billing import generate_invoices_for_period


def test_generate_invoices_for_period_legacy_fallback_without_pricing_catalog_or_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AuditService, "audit", lambda self, **kwargs: None)
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
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("org_id", Integer, nullable=False),
        Column("subscription_id", String(64), nullable=True),
        Column("period_start", String(16), nullable=True),
        Column("period_end", String(16), nullable=True),
        Column("status", String(32), nullable=False),
        Column("total_amount", Numeric(18, 2), nullable=True),
        Column("currency", String(8), nullable=True),
        Column("issued_at", DateTime(timezone=True), nullable=True),
        Column("due_at", DateTime(timezone=True), nullable=True),
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
        db.commit()

        assert len(invoice_ids) == 1

        stored_invoice = db.execute(select(billing_invoices)).mappings().one()
        assert stored_invoice["id"] == invoice_ids[0]
        assert Decimal(str(stored_invoice["total_amount"])) == Decimal("1299")
        assert stored_invoice["currency"] == "RUB"
        assert stored_invoice["status"] == "ISSUED"
