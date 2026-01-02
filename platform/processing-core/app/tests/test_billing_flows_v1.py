from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.db import Base, SessionLocal, engine
from app.models.billing_flow import BillingInvoice, BillingInvoiceStatus, BillingPayment, BillingPaymentStatus
from app.models.cases import CaseEvent, CaseEventType
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerEntryDirection, InternalLedgerTransaction
from app.models.reconciliation import (
    ReconciliationDiscrepancy,
    ReconciliationDiscrepancyType,
    ReconciliationLink,
    ReconciliationLinkStatus,
)
from app.services.billing_service import capture_payment, issue_invoice, refund_payment
from app.services.case_events_service import CaseEventActor, verify_case_event_chain, verify_case_event_signatures
from app.services.reconciliation_service import run_external_reconciliation, upload_external_statement


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _ledger_balanced(db_session, tx_id: str) -> bool:
    entries = db_session.query(InternalLedgerEntry).filter(InternalLedgerEntry.ledger_transaction_id == tx_id).all()
    debit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.DEBIT)
    credit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.CREDIT)
    return debit_sum == credit_sum


def test_issue_invoice_creates_ledger_audit_and_link(db_session):
    actor = CaseEventActor(id="user-1", email="user@example.com")
    result = issue_invoice(
        db_session,
        tenant_id=1,
        client_id="client-1",
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


def test_capture_payment_updates_invoice_status(db_session):
    actor = CaseEventActor(id="user-2", email="ops@example.com")
    invoice_result = issue_invoice(
        db_session,
        tenant_id=1,
        client_id="client-2",
        case_id=None,
        currency="USD",
        amount_total=Decimal("200"),
        due_at=None,
        idempotency_key="invoice-2",
        actor=actor,
        request_id="req-2",
        trace_id="trace-2",
    )
    payment_result = capture_payment(
        db_session,
        tenant_id=1,
        invoice_id=invoice_result.invoice.id,
        provider="bank_stub",
        provider_payment_id="pay-1",
        amount=Decimal("200"),
        currency="USD",
        idempotency_key="payment-1",
        actor=actor,
        request_id="req-3",
        trace_id="trace-3",
    )
    db_session.commit()

    invoice = payment_result.invoice
    assert invoice.amount_paid == Decimal("200")
    assert invoice.status == BillingInvoiceStatus.PAID

    payment = db_session.query(BillingPayment).filter(BillingPayment.id == payment_result.payment.id).one()
    assert payment.status == BillingPaymentStatus.CAPTURED
    assert _ledger_balanced(db_session, str(payment.ledger_tx_id))


def test_refund_adjusts_status(db_session):
    actor = CaseEventActor(id="user-3", email="finance@example.com")
    invoice_result = issue_invoice(
        db_session,
        tenant_id=1,
        client_id="client-3",
        case_id=None,
        currency="EUR",
        amount_total=Decimal("150"),
        due_at=None,
        idempotency_key="invoice-3",
        actor=actor,
        request_id="req-4",
        trace_id="trace-4",
    )
    payment_result = capture_payment(
        db_session,
        tenant_id=1,
        invoice_id=invoice_result.invoice.id,
        provider="bank_stub",
        provider_payment_id="pay-2",
        amount=Decimal("150"),
        currency="EUR",
        idempotency_key="payment-2",
        actor=actor,
        request_id="req-5",
        trace_id="trace-5",
    )
    refund_result = refund_payment(
        db_session,
        tenant_id=1,
        payment_id=payment_result.payment.id,
        provider_refund_id="refund-1",
        amount=Decimal("150"),
        currency="EUR",
        idempotency_key="refund-1",
        actor=actor,
        request_id="req-6",
        trace_id="trace-6",
    )
    db_session.commit()

    invoice = refund_result.invoice
    assert invoice.amount_paid == Decimal("0")
    assert invoice.status == BillingInvoiceStatus.ISSUED
    assert refund_result.payment.status == BillingPaymentStatus.REFUNDED_FULL


def test_idempotency_returns_same_records(db_session):
    actor = CaseEventActor(id="user-4", email="ops@example.com")
    first = issue_invoice(
        db_session,
        tenant_id=1,
        client_id="client-4",
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
        client_id="client-4",
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


def test_external_reconciliation_matches_links(db_session):
    actor = CaseEventActor(id="user-5", email="ops@example.com")
    invoice_result = issue_invoice(
        db_session,
        tenant_id=1,
        client_id="client-5",
        case_id=None,
        currency="RUB",
        amount_total=Decimal("120"),
        due_at=None,
        idempotency_key="invoice-5",
        actor=actor,
        request_id="req-9",
        trace_id="trace-9",
    )
    payment_result = capture_payment(
        db_session,
        tenant_id=1,
        invoice_id=invoice_result.invoice.id,
        provider="bank_stub",
        provider_payment_id="stmt-pay-1",
        amount=Decimal("120"),
        currency="RUB",
        idempotency_key="payment-5",
        actor=actor,
        request_id="req-10",
        trace_id="trace-10",
    )
    refund_result = refund_payment(
        db_session,
        tenant_id=1,
        payment_id=payment_result.payment.id,
        provider_refund_id="stmt-refund-1",
        amount=Decimal("20"),
        currency="RUB",
        idempotency_key="refund-5",
        actor=actor,
        request_id="req-11",
        trace_id="trace-11",
    )
    statement = upload_external_statement(
        db_session,
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

    run_external_reconciliation(db_session, statement_id=str(statement.id))
    db_session.commit()

    payment_link = (
        db_session.query(ReconciliationLink)
        .filter(ReconciliationLink.entity_type == "payment", ReconciliationLink.entity_id == payment_result.payment.id)
        .one()
    )
    refund_link = (
        db_session.query(ReconciliationLink)
        .filter(ReconciliationLink.entity_type == "refund", ReconciliationLink.entity_id == refund_result.refund.id)
        .one()
    )
    assert payment_link.status == ReconciliationLinkStatus.MATCHED
    assert refund_link.status == ReconciliationLinkStatus.MATCHED


def test_external_reconciliation_mismatch_creates_discrepancy(db_session):
    actor = CaseEventActor(id="user-6", email="ops@example.com")
    invoice_result = issue_invoice(
        db_session,
        tenant_id=1,
        client_id="client-6",
        case_id=None,
        currency="RUB",
        amount_total=Decimal("70"),
        due_at=None,
        idempotency_key="invoice-6",
        actor=actor,
        request_id="req-12",
        trace_id="trace-12",
    )
    payment_result = capture_payment(
        db_session,
        tenant_id=1,
        invoice_id=invoice_result.invoice.id,
        provider="bank_stub",
        provider_payment_id="stmt-pay-2",
        amount=Decimal("70"),
        currency="RUB",
        idempotency_key="payment-6",
        actor=actor,
        request_id="req-13",
        trace_id="trace-13",
    )
    statement = upload_external_statement(
        db_session,
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

    run_external_reconciliation(db_session, statement_id=str(statement.id))
    db_session.commit()

    discrepancy = (
        db_session.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.discrepancy_type == ReconciliationDiscrepancyType.MISMATCHED_AMOUNT)
        .one()
    )
    assert discrepancy.internal_amount == Decimal("70")
    assert discrepancy.external_amount == Decimal("50")
