from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import Column, MetaData, String, Table, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.audit_log import AuditLog
from app.models.billing_flow import (
    BillingInvoice,
    BillingInvoiceStatus,
    BillingPayment,
    BillingPaymentStatus,
    BillingRefund,
)
from app.models.cases import Case, CaseComment, CaseEvent, CaseEventType, CaseSnapshot
from app.models.client import Client
from app.models.decision_memory import DecisionMemoryRecord
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransaction,
)
from app.models.reconciliation import (
    ExternalStatement,
    ReconciliationDiscrepancy,
    ReconciliationDiscrepancyType,
    ReconciliationLink,
    ReconciliationLinkStatus,
    ReconciliationRun,
)
from app.models.notifications import NotificationMessage
from app.services.billing_service import capture_payment, issue_invoice, refund_payment
from app.services.case_events_service import CaseEventActor, verify_case_event_chain, verify_case_event_signatures
from app.services.reconciliation_service import run_external_reconciliation, upload_external_statement


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
    ReconciliationDiscrepancy.__table__,
    ReconciliationLink.__table__,
    ExternalStatement.__table__,
    NotificationMessage.__table__,
)


def _engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


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


@pytest.fixture
def db_engine():
    stub_metadata = MetaData()
    Table("fleet_offline_profiles", stub_metadata, Column("id", String(36), primary_key=True))
    Table("notification_templates", stub_metadata, Column("id", String(36), primary_key=True))
    engine = _engine()
    stub_metadata.create_all(bind=engine)
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)
    try:
        yield engine
    finally:
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        stub_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()


@pytest.fixture
def db_session(db_engine):
    session = Session(bind=db_engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def db_session_runtime(db_engine):
    session = Session(bind=db_engine, expire_on_commit=False, autoflush=False)
    try:
        yield session
    finally:
        session.close()


def _ledger_balanced(db_session, tx_id: str) -> bool:
    entries = db_session.query(InternalLedgerEntry).filter(InternalLedgerEntry.ledger_transaction_id == tx_id).all()
    debit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.DEBIT)
    credit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.CREDIT)
    return debit_sum == credit_sum


def _client_id() -> str:
    return str(uuid4())


def _request_session(engine, *, autoflush: bool = True) -> Session:
    return Session(bind=engine, expire_on_commit=False, autoflush=autoflush)


def test_issue_invoice_creates_ledger_audit_and_link(db_session):
    actor = CaseEventActor(id="user-1", email="user@example.com")
    client_id = _client_id()
    result = issue_invoice(
        db_session,
        tenant_id=1,
        client_id=client_id,
        case_id=None,
        currency="RUB",
        amount_total=Decimal("100"),
        due_at=None,
        idempotency_key="invoice-1",
        actor=actor,
        request_id="req-1",
        trace_id="trace-1",
    )
    db_session.commit()

    invoice = db_session.query(BillingInvoice).filter(BillingInvoice.id == result.invoice.id).one()
    assert invoice.status == BillingInvoiceStatus.ISSUED
    assert invoice.amount_paid == Decimal("0")

    ledger_tx = (
        db_session.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.id == invoice.ledger_tx_id)
        .one()
    )
    assert ledger_tx.currency == "RUB"
    assert _ledger_balanced(db_session, str(invoice.ledger_tx_id))

    case_event = (
        db_session.query(CaseEvent)
        .filter(CaseEvent.case_id == invoice.case_id)
        .filter(CaseEvent.type == CaseEventType.INVOICE_ISSUED)
        .one()
    )
    assert case_event.signature is not None

    link = (
        db_session.query(ReconciliationLink)
        .filter(ReconciliationLink.entity_type == "invoice", ReconciliationLink.entity_id == invoice.id)
        .one()
    )
    assert link.status == ReconciliationLinkStatus.PENDING

    chain = verify_case_event_chain(db_session, case_id=str(invoice.case_id))
    signatures = verify_case_event_signatures(db_session, case_id=str(invoice.case_id))
    assert chain.verified is True
    assert signatures.verified is True


def test_capture_payment_updates_invoice_status(db_engine):
    actor = CaseEventActor(id="user-2", email="ops@example.com")
    client_id = _client_id()
    with _request_session(db_engine) as issue_session:
        invoice_result = issue_invoice(
            issue_session,
            tenant_id=1,
            client_id=client_id,
            case_id=None,
            currency="USD",
            amount_total=Decimal("200"),
            due_at=None,
            idempotency_key="invoice-2",
            actor=actor,
            request_id="req-2",
            trace_id="trace-2",
        )
        issue_session.commit()
        invoice_id = invoice_result.invoice.id

    with _request_session(db_engine) as payment_session:
        payment_result = capture_payment(
            payment_session,
            tenant_id=1,
            invoice_id=invoice_id,
            provider="bank_stub",
            provider_payment_id="pay-1",
            amount=Decimal("200"),
            currency="USD",
            idempotency_key="payment-1",
            actor=actor,
            request_id="req-3",
            trace_id="trace-3",
        )
        payment_session.commit()

        invoice = payment_result.invoice
        assert invoice.amount_paid == Decimal("200")
        assert invoice.status == BillingInvoiceStatus.PAID

        payment = payment_session.query(BillingPayment).filter(BillingPayment.id == payment_result.payment.id).one()
        assert payment.status == BillingPaymentStatus.CAPTURED
        assert _ledger_balanced(payment_session, str(payment.ledger_tx_id))


def test_capture_payment_updates_invoice_status_with_runtime_autoflush_disabled(db_session_runtime):
    actor = CaseEventActor(id="user-2b", email="ops@example.com")
    client_id = _client_id()
    invoice_result = issue_invoice(
        db_session_runtime,
        tenant_id=1,
        client_id=client_id,
        case_id=None,
        currency="USD",
        amount_total=Decimal("200"),
        due_at=None,
        idempotency_key="invoice-2b",
        actor=actor,
        request_id="req-2b",
        trace_id="trace-2b",
    )
    db_session_runtime.commit()
    payment_result = capture_payment(
        db_session_runtime,
        tenant_id=1,
        invoice_id=invoice_result.invoice.id,
        provider="bank_stub",
        provider_payment_id="pay-2b",
        amount=Decimal("200"),
        currency="USD",
        idempotency_key="payment-2b",
        actor=actor,
        request_id="req-3b",
        trace_id="trace-3b",
    )
    db_session_runtime.commit()

    invoice = payment_result.invoice
    assert invoice.amount_paid == Decimal("200")
    assert invoice.status == BillingInvoiceStatus.PAID


def test_refund_adjusts_status(db_engine):
    actor = CaseEventActor(id="user-3", email="finance@example.com")
    client_id = _client_id()
    with _request_session(db_engine) as issue_session:
        invoice_result = issue_invoice(
            issue_session,
            tenant_id=1,
            client_id=client_id,
            case_id=None,
            currency="EUR",
            amount_total=Decimal("150"),
            due_at=None,
            idempotency_key="invoice-3",
            actor=actor,
            request_id="req-4",
            trace_id="trace-4",
        )
        issue_session.commit()
        invoice_id = invoice_result.invoice.id

    with _request_session(db_engine) as payment_session:
        payment_result = capture_payment(
            payment_session,
            tenant_id=1,
            invoice_id=invoice_id,
            provider="bank_stub",
            provider_payment_id="pay-2",
            amount=Decimal("150"),
            currency="EUR",
            idempotency_key="payment-2",
            actor=actor,
            request_id="req-5",
            trace_id="trace-5",
        )
        payment_session.commit()
        payment_id = payment_result.payment.id

    with _request_session(db_engine) as refund_session:
        refund_result = refund_payment(
            refund_session,
            tenant_id=1,
            payment_id=payment_id,
            provider_refund_id="refund-1",
            amount=Decimal("150"),
            currency="EUR",
            idempotency_key="refund-1",
            actor=actor,
            request_id="req-6",
            trace_id="trace-6",
        )
        refund_session.commit()

        invoice = refund_result.invoice
        assert invoice.amount_paid == Decimal("0")
        assert invoice.status == BillingInvoiceStatus.ISSUED
        assert refund_result.payment.status == BillingPaymentStatus.REFUNDED_FULL


def test_refund_adjusts_status_with_runtime_autoflush_disabled(db_session_runtime):
    actor = CaseEventActor(id="user-3b", email="finance@example.com")
    client_id = _client_id()
    invoice_result = issue_invoice(
        db_session_runtime,
        tenant_id=1,
        client_id=client_id,
        case_id=None,
        currency="EUR",
        amount_total=Decimal("150"),
        due_at=None,
        idempotency_key="invoice-3b",
        actor=actor,
        request_id="req-4b",
        trace_id="trace-4b",
    )
    db_session_runtime.commit()
    payment_result = capture_payment(
        db_session_runtime,
        tenant_id=1,
        invoice_id=invoice_result.invoice.id,
        provider="bank_stub",
        provider_payment_id="pay-3b",
        amount=Decimal("150"),
        currency="EUR",
        idempotency_key="payment-3b",
        actor=actor,
        request_id="req-5b",
        trace_id="trace-5b",
    )
    db_session_runtime.commit()
    refund_result = refund_payment(
        db_session_runtime,
        tenant_id=1,
        payment_id=payment_result.payment.id,
        provider_refund_id="refund-3b",
        amount=Decimal("150"),
        currency="EUR",
        idempotency_key="refund-3b",
        actor=actor,
        request_id="req-6b",
        trace_id="trace-6b",
    )
    db_session_runtime.commit()

    invoice = refund_result.invoice
    assert invoice.amount_paid == Decimal("0")
    assert invoice.status == BillingInvoiceStatus.ISSUED
    assert refund_result.payment.status == BillingPaymentStatus.REFUNDED_FULL


def test_idempotency_returns_same_records(db_session):
    actor = CaseEventActor(id="user-4", email="ops@example.com")
    client_id = _client_id()
    first = issue_invoice(
        db_session,
        tenant_id=1,
        client_id=client_id,
        case_id=None,
        currency="RUB",
        amount_total=Decimal("80"),
        due_at=None,
        idempotency_key="invoice-idem",
        actor=actor,
        request_id="req-7",
        trace_id="trace-7",
    )
    second = issue_invoice(
        db_session,
        tenant_id=1,
        client_id=client_id,
        case_id=None,
        currency="RUB",
        amount_total=Decimal("80"),
        due_at=None,
        idempotency_key="invoice-idem",
        actor=actor,
        request_id="req-8",
        trace_id="trace-8",
    )
    db_session.commit()

    assert first.invoice.id == second.invoice.id
    assert db_session.query(BillingInvoice).count() == 1


def test_external_reconciliation_matches_links(db_engine):
    actor = CaseEventActor(id="user-5", email="ops@example.com")
    client_id = _client_id()
    with _request_session(db_engine) as issue_session:
        invoice_result = issue_invoice(
            issue_session,
            tenant_id=1,
            client_id=client_id,
            case_id=None,
            currency="RUB",
            amount_total=Decimal("120"),
            due_at=None,
            idempotency_key="invoice-5",
            actor=actor,
            request_id="req-9",
            trace_id="trace-9",
        )
        issue_session.commit()
        invoice_id = invoice_result.invoice.id

    with _request_session(db_engine) as payment_session:
        payment_result = capture_payment(
            payment_session,
            tenant_id=1,
            invoice_id=invoice_id,
            provider="bank_stub",
            provider_payment_id="stmt-pay-1",
            amount=Decimal("120"),
            currency="RUB",
            idempotency_key="payment-5",
            actor=actor,
            request_id="req-10",
            trace_id="trace-10",
        )
        payment_session.commit()
        payment_id = payment_result.payment.id

    with _request_session(db_engine) as refund_session:
        refund_result = refund_payment(
            refund_session,
            tenant_id=1,
            payment_id=payment_id,
            provider_refund_id="stmt-refund-1",
            amount=Decimal("20"),
            currency="RUB",
            idempotency_key="refund-5",
            actor=actor,
            request_id="req-11",
            trace_id="trace-11",
        )
        refund_session.commit()
        refund_id = refund_result.refund.id

    with _request_session(db_engine) as statement_session:
        statement = upload_external_statement(
            statement_session,
            provider="bank_stub",
            period_start=datetime.now(timezone.utc) - timedelta(days=1),
            period_end=datetime.now(timezone.utc) + timedelta(days=1),
            currency="RUB",
            total_in=None,
            total_out=None,
            closing_balance=None,
            lines=[
                {"id": "stmt-pay-1", "amount": "120", "direction": "IN"},
                {"id": "stmt-refund-1", "amount": "20", "direction": "OUT"},
            ],
        )
        statement_session.commit()
        statement_id = str(statement.id)

    with _request_session(db_engine) as reconcile_session:
        run_external_reconciliation(reconcile_session, statement_id=statement_id)
        reconcile_session.commit()

    with _request_session(db_engine) as verify_session:
        payment_link = (
            verify_session.query(ReconciliationLink)
            .filter(ReconciliationLink.entity_type == "payment", ReconciliationLink.entity_id == payment_id)
            .one()
        )
        refund_link = (
            verify_session.query(ReconciliationLink)
            .filter(ReconciliationLink.entity_type == "refund", ReconciliationLink.entity_id == refund_id)
            .one()
        )
        assert payment_link.status == ReconciliationLinkStatus.MATCHED
        assert refund_link.status == ReconciliationLinkStatus.MATCHED


def test_external_reconciliation_mismatch_creates_discrepancy(db_engine):
    actor = CaseEventActor(id="user-6", email="ops@example.com")
    client_id = _client_id()
    with _request_session(db_engine) as issue_session:
        invoice_result = issue_invoice(
            issue_session,
            tenant_id=1,
            client_id=client_id,
            case_id=None,
            currency="RUB",
            amount_total=Decimal("70"),
            due_at=None,
            idempotency_key="invoice-6",
            actor=actor,
            request_id="req-12",
            trace_id="trace-12",
        )
        issue_session.commit()
        invoice_id = invoice_result.invoice.id

    with _request_session(db_engine) as payment_session:
        capture_payment(
            payment_session,
            tenant_id=1,
            invoice_id=invoice_id,
            provider="bank_stub",
            provider_payment_id="stmt-pay-2",
            amount=Decimal("70"),
            currency="RUB",
            idempotency_key="payment-6",
            actor=actor,
            request_id="req-13",
            trace_id="trace-13",
        )
        payment_session.commit()

    with _request_session(db_engine) as statement_session:
        statement = upload_external_statement(
            statement_session,
            provider="bank_stub",
            period_start=datetime.now(timezone.utc) - timedelta(days=1),
            period_end=datetime.now(timezone.utc) + timedelta(days=1),
            currency="RUB",
            total_in=None,
            total_out=None,
            closing_balance=None,
            lines=[
                {"id": "stmt-pay-2", "amount": "50", "direction": "IN"},
            ],
        )
        statement_session.commit()
        statement_id = str(statement.id)

    with _request_session(db_engine) as reconcile_session:
        run_external_reconciliation(reconcile_session, statement_id=statement_id)
        reconcile_session.commit()

    with _request_session(db_engine) as verify_session:
        discrepancy = (
            verify_session.query(ReconciliationDiscrepancy)
            .filter(ReconciliationDiscrepancy.discrepancy_type == ReconciliationDiscrepancyType.MISMATCHED_AMOUNT)
            .one()
        )
        assert discrepancy.internal_amount == Decimal("70")
        assert discrepancy.external_amount == Decimal("50")
