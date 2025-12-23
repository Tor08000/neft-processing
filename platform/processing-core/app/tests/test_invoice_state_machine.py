from datetime import date, datetime

import pytest

from app.models.invoice import Invoice, InvoiceStatus
from app.services.invoice_state_machine import InvoiceInvariantError, InvoiceStateMachine, InvalidTransitionError


class _StubSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, obj) -> None:  # pragma: no cover - trivial
        self.added.append(obj)


def _make_invoice(status: InvoiceStatus) -> Invoice:
    return Invoice(
        client_id="client-1",
        period_from=date(2024, 1, 1),
        period_to=date(2024, 1, 31),
        currency="RUB",
        total_amount=1000,
        tax_amount=0,
        total_with_tax=1000,
        amount_paid=0,
        amount_due=1000,
        status=status,
    )


def test_draft_to_issued_sets_timestamp_and_due():
    now = datetime(2024, 2, 1, 10, 0, 0)
    invoice = _make_invoice(InvoiceStatus.DRAFT)
    machine = InvoiceStateMachine(invoice, db=_StubSession(), now_provider=lambda: now)

    machine.transition(
        to=InvoiceStatus.ISSUED,
        actor="tester",
        reason="issue",
    )

    assert invoice.status == InvoiceStatus.ISSUED
    assert invoice.issued_at == now
    assert invoice.amount_due == invoice.total_with_tax


def test_sent_to_paid_updates_financials_and_paid_at():
    now = datetime(2024, 2, 3, 14, 0, 0)
    invoice = _make_invoice(InvoiceStatus.SENT)
    session = _StubSession()
    machine = InvoiceStateMachine(invoice, db=session, now_provider=lambda: now)

    machine.transition(
        to=InvoiceStatus.PARTIALLY_PAID,
        actor="tester",
        reason="payment",
        payment_amount=invoice.total_with_tax,
    )
    machine.transition(
        to=InvoiceStatus.PAID,
        actor="tester",
        reason="settle",
    )

    assert invoice.status == InvoiceStatus.PAID
    assert invoice.paid_at == now
    assert invoice.amount_due == 0
    assert invoice.amount_paid == invoice.total_with_tax
    assert any(getattr(log, "to_status", None) == InvoiceStatus.PAID for log in session.added)


def test_partial_payment_requires_amount():
    invoice = _make_invoice(InvoiceStatus.SENT)
    machine = InvoiceStateMachine(invoice, db=_StubSession())

    with pytest.raises(InvalidTransitionError):
        machine.transition(
            to=InvoiceStatus.PARTIALLY_PAID,
            actor="tester",
            reason="partial",
        )


def test_credit_note_allows_partial_from_sent():
    invoice = _make_invoice(InvoiceStatus.SENT)
    machine = InvoiceStateMachine(invoice, db=_StubSession())

    machine.transition(
        to=InvoiceStatus.PARTIALLY_PAID,
        actor="tester",
        reason="credit",
        credit_note_amount=500,
    )

    assert invoice.status == InvoiceStatus.PARTIALLY_PAID
    assert invoice.amount_due == 500
    assert invoice.credited_amount == 500


def test_cannot_cancel_with_existing_payment():
    invoice = _make_invoice(InvoiceStatus.SENT)
    invoice.amount_paid = 100
    machine = InvoiceStateMachine(invoice, db=_StubSession())

    with pytest.raises(InvalidTransitionError):
        machine.transition(
            to=InvoiceStatus.CANCELLED,
            actor="tester",
            reason="cancel",
        )


def test_credit_note_covers_remaining_balance():
    invoice = _make_invoice(InvoiceStatus.PARTIALLY_PAID)
    invoice.amount_paid = 600
    invoice.amount_due = 400
    machine = InvoiceStateMachine(invoice, db=_StubSession())

    machine.transition(
        to=InvoiceStatus.PAID,
        actor="tester",
        reason="apply credit",
        credit_note_amount=400,
    )

    assert invoice.status == InvoiceStatus.PAID
    assert invoice.amount_due == 0
    assert invoice.credited_amount == 400


def test_overdue_requires_outstanding_due():
    invoice = _make_invoice(InvoiceStatus.SENT)
    invoice.amount_paid = invoice.total_with_tax
    invoice.amount_due = 0
    machine = InvoiceStateMachine(invoice, db=_StubSession())

    with pytest.raises(InvalidTransitionError):
        machine.transition(
            to=InvoiceStatus.OVERDUE,
            actor="tester",
            reason="scheduler",
        )


def test_invariants_guard_against_negative_due():
    invoice = _make_invoice(InvoiceStatus.SENT)
    machine = InvoiceStateMachine(invoice, db=_StubSession())

    with pytest.raises(InvoiceInvariantError):
        machine.transition(
            to=InvoiceStatus.PARTIALLY_PAID,
            actor="tester",
            reason="bad_payment",
            payment_amount=-1,
        )
