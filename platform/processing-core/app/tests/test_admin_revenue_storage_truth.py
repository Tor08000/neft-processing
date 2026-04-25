from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Date, DateTime, Integer, MetaData, Numeric, String, Table, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.schema import DB_SCHEMA
from app.services.admin_revenue import revenue_overdue_list, revenue_summary, revenue_usage_totals


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


def test_revenue_handles_billing_flow_invoice_shape_without_legacy_columns() -> None:
    engine = _engine()
    metadata = MetaData()
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
    billing_invoice_lines = Table(
        "billing_invoice_lines",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("invoice_id", String(36), nullable=False),
        Column("line_type", String(32), nullable=False),
        Column("ref_code", String(64), nullable=True),
        Column("quantity", Numeric(18, 4), nullable=True),
        Column("amount", Numeric(18, 4), nullable=False),
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
                id="sub-client-1",
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
                id="invoice-flow-1",
                invoice_number="INV-FLOW-1",
                client_id="client-1",
                currency="RUB",
                amount_total=Decimal("125000.00"),
                amount_paid=Decimal("25000.00"),
                status="ISSUED",
                issued_at=datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
                due_at=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
                idempotency_key="subscription-invoice:sub-client-1:2026-04-01:2026-04-30",
                ledger_tx_id="ledger-1",
                audit_event_id="audit-1",
                created_at=now,
            )
        )
        db.execute(
            billing_invoice_lines.insert().values(
                id=1,
                invoice_id="invoice-flow-1",
                line_type="USAGE",
                ref_code="fuel-liters",
                quantity=Decimal("10"),
                amount=Decimal("555.00"),
            )
        )
        db.commit()

        summary = revenue_summary(db, as_of=date(2026, 4, 23))
        assert summary["active_orgs"] == 1
        assert summary["mrr"]["amount"] == Decimal("1299")
        assert summary["overdue_orgs"] == 1
        assert summary["overdue_amount"] == Decimal("100000.0000")
        assert summary["usage_revenue_mtd"] == Decimal("555.0000")
        assert summary["overdue_buckets"][1]["bucket"] == "8_30"
        assert summary["overdue_buckets"][1]["orgs"] == 1
        assert summary["overdue_buckets"][1]["amount"] == Decimal("100000.0000")

        items, total = revenue_overdue_list(db, as_of=date(2026, 4, 23), bucket="8_30", limit=20, offset=0)
        assert total == 1
        assert items[0]["org_id"] == 101
        assert items[0]["invoice_id"] == "invoice-flow-1"
        assert items[0]["amount"] == Decimal("100000.0000")

        usage = revenue_usage_totals(db, period_from=date(2026, 4, 1), period_to=date(2026, 4, 30))
        assert usage == [{"ref_code": "fuel-liters", "quantity": Decimal("10.0000"), "amount": Decimal("555.0000")}]


def test_revenue_keeps_legacy_org_invoice_shape() -> None:
    engine = _engine()
    metadata = MetaData()
    orgs = Table(
        "orgs",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(128), nullable=True),
        schema=DB_SCHEMA,
    )
    org_subscriptions = Table(
        "org_subscriptions",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("org_id", Integer, nullable=False),
        Column("plan_id", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        Column("billing_cycle", String(32), nullable=True),
        schema=DB_SCHEMA,
    )
    subscription_plans = Table(
        "subscription_plans",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("code", String(64), nullable=False),
        schema=DB_SCHEMA,
    )
    pricing_catalog = Table(
        "pricing_catalog",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("item_type", String(32), nullable=False),
        Column("item_id", String(64), nullable=False),
        Column("price_monthly", Numeric(18, 4), nullable=True),
        Column("price_yearly", Numeric(18, 4), nullable=True),
        Column("currency", String(8), nullable=True),
        Column("effective_from", DateTime(timezone=True), nullable=False),
        Column("effective_to", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    billing_invoices = Table(
        "billing_invoices",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("org_id", Integer, nullable=True),
        Column("subscription_id", Integer, nullable=True),
        Column("status", String(32), nullable=False),
        Column("period_start", Date, nullable=True),
        Column("due_at", DateTime(timezone=True), nullable=True),
        Column("total_amount", Numeric(18, 4), nullable=True),
        Column("currency", String(8), nullable=True),
        schema=DB_SCHEMA,
    )
    metadata.create_all(bind=engine)

    with Session(bind=engine) as db:
        db.execute(orgs.insert().values(id=202, name="ACME Logistics"))
        db.execute(
            org_subscriptions.insert().values(
                id=77,
                org_id=202,
                plan_id="plan-control",
                status="ACTIVE",
                billing_cycle="MONTHLY",
            )
        )
        db.execute(subscription_plans.insert().values(id="plan-control", code="CONTROL"))
        db.execute(
            pricing_catalog.insert().values(
                id=1,
                item_type="PLAN",
                item_id="plan-control",
                price_monthly=Decimal("1299.00"),
                price_yearly=None,
                currency="RUB",
                effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                effective_to=None,
            )
        )
        db.execute(
            billing_invoices.insert().values(
                id="invoice-legacy-1",
                org_id=202,
                subscription_id=77,
                status="OVERDUE",
                period_start=date(2026, 4, 1),
                due_at=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
                total_amount=Decimal("123.45"),
                currency="RUB",
            )
        )
        db.commit()

        summary = revenue_summary(db, as_of=date(2026, 4, 23))
        assert summary["active_orgs"] == 1
        assert summary["mrr"]["amount"] == Decimal("1299.0000")
        assert summary["overdue_orgs"] == 1
        assert summary["overdue_amount"] == Decimal("123.4500")
        assert summary["overdue_buckets"][0]["bucket"] == "0_7"
        assert summary["overdue_buckets"][0]["amount"] == Decimal("123.4500")

        items, total = revenue_overdue_list(db, as_of=date(2026, 4, 23), bucket="0_7", limit=20, offset=0)
        assert total == 1
        assert items[0]["org_id"] == 202
        assert items[0]["org_name"] == "ACME Logistics"
        assert items[0]["subscription_plan"] == "CONTROL"
        assert items[0]["subscription_status"] == "ACTIVE"
