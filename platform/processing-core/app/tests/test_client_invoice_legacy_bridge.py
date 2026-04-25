from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table, create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.schema import DB_SCHEMA
from app.routers import client_portal_v1


def test_client_invoice_legacy_bridge_resolves_org_id_from_subscription() -> None:
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
    billing_invoices = Table(
        "billing_invoices",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("subscription_id", String(64), nullable=True),
        Column("period_start", String(16), nullable=True),
        Column("period_end", String(16), nullable=True),
        Column("status", String(32), nullable=False),
        Column("total_amount", Integer, nullable=True),
        Column("currency", String(8), nullable=True),
        Column("issued_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        schema=DB_SCHEMA,
    )
    metadata.create_all(bind=engine)

    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.execute(client_subscriptions.insert().values(id="legacy-sub", tenant_id=1))
        db.execute(
            billing_invoices.insert().values(
                id=501,
                subscription_id="legacy-sub",
                period_start="2026-04-01",
                period_end="2026-04-30",
                status="ISSUED",
                total_amount=1000,
                currency="RUB",
                issued_at=now,
                created_at=now,
            )
        )
        db.commit()

        invoice = db.execute(select(billing_invoices)).mappings().first()
        rows = client_portal_v1._list_subscription_invoice_rows_for_org(
            db,
            org_id=1,
            billing_invoices=billing_invoices,
        )
        assert invoice is not None
        assert client_portal_v1._resolve_subscription_invoice_org_id(db, invoice) == 1
        assert len(rows) == 1
        assert rows[0]["id"] == 501
        assert rows[0]["org_id"] == 1


def test_client_invoice_billing_flow_bridge_resolves_org_id_from_client_id() -> None:
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
    billing_invoices = Table(
        "billing_invoices",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("client_id", String(64), nullable=False),
        Column("invoice_number", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        Column("amount_total", Numeric(18, 2), nullable=True),
        Column("amount_paid", Numeric(18, 2), nullable=True),
        Column("currency", String(8), nullable=True),
        Column("idempotency_key", String(128), nullable=False),
        Column("ledger_tx_id", String(64), nullable=False),
        Column("audit_event_id", String(64), nullable=False),
        Column("issued_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("status", String(32), nullable=True),
        Column("start_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    metadata.create_all(bind=engine)

    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.execute(
            client_subscriptions.insert().values(
                id="legacy-sub-flow",
                tenant_id=1,
                client_id="client-flow-1",
                status="ACTIVE",
                start_at=now,
                created_at=now,
            )
        )
        db.execute(
            billing_invoices.insert().values(
                id="inv-flow-1",
                client_id="client-flow-1",
                invoice_number="INV-FLOW-1",
                status="ISSUED",
                amount_total=Decimal("1250.00"),
                amount_paid=Decimal("0"),
                currency="RUB",
                idempotency_key="subscription-invoice:legacy-sub-flow:2026-03-01:2026-03-31",
                ledger_tx_id="ledger-1",
                audit_event_id="audit-1",
                issued_at=now,
                created_at=now,
            )
        )
        db.commit()

        invoice = db.execute(select(billing_invoices)).mappings().first()
        rows = client_portal_v1._list_subscription_invoice_rows_for_org(
            db,
            org_id=1,
            billing_invoices=billing_invoices,
        )
        assert invoice is not None
        assert client_portal_v1._resolve_subscription_invoice_org_id(db, invoice) == 1
        assert len(rows) == 1
        assert rows[0]["id"] == "inv-flow-1"
        assert rows[0]["org_id"] == 1
        assert rows[0]["subscription_id"] == "legacy-sub-flow"
        assert client_portal_v1._subscription_invoice_total_amount(rows[0]) == Decimal("1250.00")


def test_client_invoice_bridge_stringifies_uuid_client_id_for_legacy_lookup() -> None:
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
        Column("created_at", DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    metadata.create_all(bind=engine)

    client_id = "00000000-0000-0000-0000-000000000001"
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.execute(
            client_subscriptions.insert().values(
                id="legacy-sub-uuid",
                tenant_id=1,
                client_id=client_id,
                created_at=now,
            )
        )
        db.commit()

        invoice = {"id": "inv-flow-uuid", "client_id": UUID(client_id), "status": "ISSUED"}
        assert client_portal_v1._subscription_invoice_identifier(UUID(client_id)) == client_id
        assert client_portal_v1._resolve_subscription_invoice_org_id(db, invoice) == 1
