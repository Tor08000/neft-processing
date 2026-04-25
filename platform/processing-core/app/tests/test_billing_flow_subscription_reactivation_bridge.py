from __future__ import annotations

import base64
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.schema import DB_SCHEMA
from app.models.audit_log import AuditLog
from app.models.billing_flow import BillingInvoice, BillingPayment, BillingRefund
from app.models.cases import Case, CaseComment, CaseEvent, CaseSnapshot
from app.models.client import Client
from app.models.decision_memory import DecisionMemoryRecord
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.notifications import NotificationMessage
from app.models.reconciliation import ReconciliationLink, ReconciliationRun
from app.services import billing_service
from app.services.billing_service import capture_payment, issue_invoice, reactivate_subscription_storage
from app.services.case_events_service import CaseEventActor


TEST_TABLES = (
    AuditLog.__table__,
    BillingInvoice.__table__,
    BillingPayment.__table__,
    BillingRefund.__table__,
    Case.__table__,
    CaseSnapshot.__table__,
    CaseComment.__table__,
    CaseEvent.__table__,
    Client.__table__,
    DecisionMemoryRecord.__table__,
    InternalLedgerAccount.__table__,
    InternalLedgerTransaction.__table__,
    InternalLedgerEntry.__table__,
    ReconciliationRun.__table__,
    ReconciliationLink.__table__,
    NotificationMessage.__table__,
)


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


@pytest.fixture()
def runtime_bridge_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _setup_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"ATTACH DATABASE ':memory:' AS {DB_SCHEMA}")
        cursor.close()

    bridge_metadata = MetaData()
    Table(
        "fleet_offline_profiles",
        bridge_metadata,
        Column("id", String(36), primary_key=True),
    )
    Table(
        "org_subscriptions",
        bridge_metadata,
        Column("id", String(64), primary_key=True),
        Column("org_id", Integer, nullable=False),
        Column("status", String(32), nullable=False),
        schema=DB_SCHEMA,
    )
    Table(
        "client_subscriptions",
        bridge_metadata,
        Column("id", String(64), primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        schema=DB_SCHEMA,
    )
    bridge_metadata.create_all(bind=engine)
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    session = Session(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        yield session
    finally:
        session.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        bridge_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()


def test_capture_payment_reactivates_subscription_storage_after_full_payment(runtime_bridge_session: Session) -> None:
    client_id = str(uuid4())
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    engine = runtime_bridge_session.bind
    org_subscriptions = Table("org_subscriptions", MetaData(), autoload_with=engine, schema=DB_SCHEMA)
    client_subscriptions = Table(
        "client_subscriptions",
        MetaData(),
        autoload_with=engine,
        schema=DB_SCHEMA,
    )

    runtime_bridge_session.add(Client(id=UUID(client_id), name="Runtime Bridge Client", status="ACTIVE"))
    runtime_bridge_session.execute(
        org_subscriptions.insert().values(id="org-sub-1", org_id=1, status="OVERDUE")
    )
    runtime_bridge_session.execute(
        client_subscriptions.insert().values(
            id="legacy-sub-1",
            tenant_id=1,
            client_id=client_id,
            status="PAST_DUE",
        )
    )
    runtime_bridge_session.commit()

    actor = CaseEventActor(id="ops-1", email="ops@example.com")
    with Session(bind=engine, expire_on_commit=False, autoflush=False) as issue_session:
        invoice_result = issue_invoice(
            issue_session,
            tenant_id=1,
            client_id=client_id,
            case_id=None,
            currency="RUB",
            amount_total=Decimal("299"),
            due_at=now,
            idempotency_key="runtime-bridge-invoice",
            actor=actor,
            request_id="req-runtime-1",
            trace_id="trace-runtime-1",
        )
        issue_session.commit()
        invoice_id = invoice_result.invoice.id

    with Session(bind=engine, expire_on_commit=False, autoflush=False) as payment_session:
        capture_payment(
            payment_session,
            tenant_id=1,
            invoice_id=invoice_id,
            provider="MANUAL_PAYMENT_INTAKE",
            provider_payment_id="payment-runtime-1",
            amount=Decimal("299"),
            currency="RUB",
            idempotency_key="runtime-bridge-payment",
            actor=actor,
            request_id="req-runtime-2",
            trace_id="trace-runtime-2",
        )
        payment_session.commit()

    with Session(bind=engine, expire_on_commit=False, autoflush=False) as verify_session:
        invoice_status = verify_session.execute(
            select(BillingInvoice.status).where(BillingInvoice.id == invoice_id)
        ).scalar_one()
        org_status = verify_session.execute(select(org_subscriptions.c.status)).scalar_one()
        legacy_status = verify_session.execute(select(client_subscriptions.c.status)).scalar_one()

    assert invoice_status.value == "PAID"
    assert legacy_status == "ACTIVE"


def test_capture_payment_reactivates_subscription_storage_with_runtime_autoflush_enabled(
    runtime_bridge_session: Session,
) -> None:
    client_id = str(uuid4())
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    engine = runtime_bridge_session.bind
    org_subscriptions = Table("org_subscriptions", MetaData(), autoload_with=engine, schema=DB_SCHEMA)
    client_subscriptions = Table(
        "client_subscriptions",
        MetaData(),
        autoload_with=engine,
        schema=DB_SCHEMA,
    )

    runtime_bridge_session.add(Client(id=UUID(client_id), name="Autoflush Bridge Client", status="ACTIVE"))
    runtime_bridge_session.execute(
        org_subscriptions.insert().values(id="org-sub-2", org_id=1, status="OVERDUE")
    )
    runtime_bridge_session.execute(
        client_subscriptions.insert().values(
            id="legacy-sub-2",
            tenant_id=1,
            client_id=client_id,
            status="PAST_DUE",
        )
    )
    runtime_bridge_session.commit()

    actor = CaseEventActor(id="ops-2", email="ops@example.com")
    with Session(bind=engine, expire_on_commit=False) as issue_session:
        invoice_result = issue_invoice(
            issue_session,
            tenant_id=1,
            client_id=client_id,
            case_id=None,
            currency="RUB",
            amount_total=Decimal("399"),
            due_at=now,
            idempotency_key="runtime-bridge-invoice-autoflush",
            actor=actor,
            request_id="req-runtime-3",
            trace_id="trace-runtime-3",
        )
        issue_session.commit()
        invoice_id = invoice_result.invoice.id

    with Session(bind=engine, expire_on_commit=False) as payment_session:
        payment_result = capture_payment(
            payment_session,
            tenant_id=1,
            invoice_id=invoice_id,
            provider="MANUAL_PAYMENT_INTAKE",
            provider_payment_id="payment-runtime-2",
            amount=Decimal("399"),
            currency="RUB",
            idempotency_key="runtime-bridge-payment-autoflush",
            actor=actor,
            request_id="req-runtime-4",
            trace_id="trace-runtime-4",
        )
        payment_session.commit()
        payment_id = payment_result.payment.id

    with Session(bind=engine, expire_on_commit=False) as verify_session:
        invoice_status = verify_session.execute(
            select(BillingInvoice.status).where(BillingInvoice.id == invoice_id)
        ).scalar_one()
        stored_payment = verify_session.execute(
            select(BillingPayment.id).where(BillingPayment.id == payment_id)
        ).scalar_one()
        org_status = verify_session.execute(select(org_subscriptions.c.status)).scalar_one()
        legacy_status = verify_session.execute(select(client_subscriptions.c.status)).scalar_one()

    assert invoice_status.value == "PAID"
    assert str(stored_payment) == str(payment_id)
    assert org_status == "ACTIVE"
    assert legacy_status == "ACTIVE"


def test_reactivate_subscription_storage_targets_org_and_legacy_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_subscriptions = Table(
        "org_subscriptions",
        MetaData(),
        Column("org_id", Integer, nullable=False),
        Column("status", String(32), nullable=False),
        schema=DB_SCHEMA,
    )
    client_subscriptions = Table(
        "client_subscriptions",
        MetaData(),
        Column("tenant_id", Integer, nullable=False),
        Column("status", String(32), nullable=False),
        schema=DB_SCHEMA,
    )

    seen: list[tuple[str, dict[str, object] | None]] = []

    class _FakeSession:
        def execute(self, statement, params=None):
            seen.append((getattr(statement, "text", str(statement)), params))
            return None

    monkeypatch.setattr(
        billing_service,
        "_reflected_table_exists",
        lambda db, name: name in {"org_subscriptions", "client_subscriptions"},
    )
    monkeypatch.setattr(
        billing_service,
        "_reflected_table",
        lambda db, name: org_subscriptions if name == "org_subscriptions" else client_subscriptions,
    )

    reactivate_subscription_storage(_FakeSession(), tenant_id=1)

    assert len(seen) == 2
    assert seen[0][0] == f'UPDATE "{DB_SCHEMA}".org_subscriptions SET status = :status WHERE org_id = :tenant_id'
    assert seen[0][1] == {"status": "ACTIVE", "tenant_id": 1}
    assert seen[1][0] == (
        f'UPDATE "{DB_SCHEMA}".client_subscriptions SET status = :status WHERE tenant_id = :tenant_id'
    )
    assert seen[1][1] == {"status": "ACTIVE", "tenant_id": 1}
