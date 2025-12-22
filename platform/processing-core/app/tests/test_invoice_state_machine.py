from datetime import date, datetime

import pytest
from fastapi import HTTPException

from app.models.invoice import Invoice, InvoiceStatus
from app.services.invoice_state_machine import InvoiceStateMachine, InvoiceTransitionContext


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


def test_draft_to_issued_sets_timestamp():
    now = datetime(2024, 2, 1, 10, 0, 0)
    invoice = _make_invoice(InvoiceStatus.DRAFT)
    machine = InvoiceStateMachine(now_provider=lambda: now)

    machine.apply_transition(
        invoice,
        InvoiceStatus.ISSUED,
        context=InvoiceTransitionContext(actor="tester", reason="issue"),
    )

    assert invoice.status == InvoiceStatus.ISSUED
    assert invoice.issued_at == now


def test_issued_to_sent_sets_sent_at():
    now = datetime(2024, 2, 2, 12, 0, 0)
    invoice = _make_invoice(InvoiceStatus.ISSUED)
    invoice.issued_at = datetime(2024, 2, 1, 10, 0, 0)
    machine = InvoiceStateMachine(now_provider=lambda: now)

    machine.apply_transition(
        invoice,
        InvoiceStatus.SENT,
        context=InvoiceTransitionContext(actor="tester", reason="send"),
    )

    assert invoice.status == InvoiceStatus.SENT
    assert invoice.sent_at == now


def test_sent_to_paid_sets_paid_at_and_due():
    now = datetime(2024, 2, 3, 14, 0, 0)
    invoice = _make_invoice(InvoiceStatus.SENT)
    machine = InvoiceStateMachine(now_provider=lambda: now)

    machine.apply_transition(
        invoice,
        InvoiceStatus.PAID,
        context=InvoiceTransitionContext(
            actor="tester",
            reason="payment",
            payments_total=invoice.total_with_tax,
        ),
    )

    assert invoice.status == InvoiceStatus.PAID
    assert invoice.paid_at == now
    assert invoice.amount_due == 0
    assert invoice.amount_paid == invoice.total_with_tax


def test_paid_to_sent_forbidden():
    invoice = _make_invoice(InvoiceStatus.PAID)
    invoice.amount_paid = invoice.total_with_tax
    machine = InvoiceStateMachine()

    with pytest.raises(HTTPException) as exc:
        machine.apply_transition(
            invoice,
            InvoiceStatus.SENT,
            context=InvoiceTransitionContext(actor="tester", reason="revert"),
        )

    assert exc.value.status_code == 409


def test_cancelled_is_terminal():
    invoice = _make_invoice(InvoiceStatus.CANCELLED)
    machine = InvoiceStateMachine()

    with pytest.raises(HTTPException) as exc:
        machine.apply_transition(
            invoice,
            InvoiceStatus.ISSUED,
            context=InvoiceTransitionContext(actor="tester", reason="resurrect"),
        )

    assert exc.value.status_code == 409


def test_sent_cannot_cancel_with_payments():
    invoice = _make_invoice(InvoiceStatus.SENT)
    invoice.amount_paid = 100
    machine = InvoiceStateMachine()

    with pytest.raises(HTTPException) as exc:
        machine.apply_transition(
            invoice,
            InvoiceStatus.CANCELLED,
            context=InvoiceTransitionContext(actor="tester", reason="cancel"),
        )

    assert exc.value.status_code == 409
