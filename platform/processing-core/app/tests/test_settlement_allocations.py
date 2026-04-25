from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from app.config import settings
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.billing_summary import BillingSummary
from app.models.finance import InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus, InvoiceStatus
from app.services.billing_periods import period_bounds_for_dates
from app.services.finance import FinanceService
from app.tests._finance_test_harness import finance_invariant_session_context, seed_default_finance_thresholds


@pytest.fixture(autouse=True)
def _disable_legal_graph(monkeypatch: pytest.MonkeyPatch):
    class _NoopGraphBuilder:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ensure_settlement_allocation_graph(self, *args, **kwargs) -> None:
            return None

    monkeypatch.setattr("app.services.finance.LegalGraphBuilder", _NoopGraphBuilder)


@pytest.fixture
def session():
    with finance_invariant_session_context() as db:
        seed_default_finance_thresholds(db)
        yield db


def _create_period(
    session,
    *,
    date_from: date,
    date_to: date,
    status: BillingPeriodStatus,
    period_type: BillingPeriodType = BillingPeriodType.ADHOC,
) -> BillingPeriod:
    period = BillingPeriod(
        period_type=period_type,
        start_at=datetime.combine(date_from, time.min, tzinfo=timezone.utc),
        end_at=datetime.combine(date_to, time.max, tzinfo=timezone.utc),
        tz="UTC",
        status=status,
    )
    session.add(period)
    session.flush()
    return period


def _transition_period(session, *, period: BillingPeriod, status: BillingPeriodStatus) -> BillingPeriod:
    period.status = status
    session.add(period)
    session.flush()
    return period


def _create_invoice(session, *, period: BillingPeriod) -> Invoice:
    invoice = Invoice(
        client_id="client-1",
        period_from=period.start_at.date(),
        period_to=period.end_at.date(),
        currency="RUB",
        billing_period_id=period.id,
        total_amount=1000,
        tax_amount=0,
        total_with_tax=1000,
        amount_paid=0,
        amount_due=1000,
        status=InvoiceStatus.SENT,
        pdf_status=InvoicePdfStatus.READY,
    )
    session.add(invoice)
    session.flush()
    line = InvoiceLine(
        invoice_id=invoice.id,
        operation_id="op-1",
        product_id="FUEL",
        line_amount=1000,
        tax_amount=0,
    )
    session.add(line)
    session.flush()
    return invoice


def test_payment_allocates_after_lock_without_mutating_charges(session):
    charge_date = date(2024, 3, 1)
    charge_period = _create_period(
        session,
        date_from=charge_date,
        date_to=charge_date,
        status=BillingPeriodStatus.OPEN,
    )
    invoice = _create_invoice(session, period=charge_period)
    _transition_period(session, period=charge_period, status=BillingPeriodStatus.LOCKED)
    summary = BillingSummary(
        billing_date=charge_date,
        billing_period_id=charge_period.id,
        client_id=invoice.client_id,
        merchant_id="merchant-1",
        currency="RUB",
        total_amount=1000,
        operations_count=1,
        hash="hash-before",
    )
    session.add(summary)
    session.commit()

    line_snapshot = [
        (line.id, line.operation_id, line.product_id, int(line.line_amount))
        for line in session.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).all()
    ]

    service = FinanceService(session)
    result = service.apply_payment(
        invoice_id=invoice.id,
        amount=400,
        currency="RUB",
        idempotency_key="alloc-payment",
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
    )

    session.refresh(result.invoice)
    assert result.invoice.status == InvoiceStatus.PARTIALLY_PAID

    refreshed_lines = [
        (line.id, line.operation_id, line.product_id, int(line.line_amount))
        for line in session.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).all()
    ]
    assert refreshed_lines == line_snapshot

    session.refresh(summary)
    assert summary.hash == "hash-before"

    allocation = (
        session.query(InvoiceSettlementAllocation)
        .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
        .one()
    )
    assert allocation.source_type == SettlementSourceType.PAYMENT
    assert allocation.amount == 400

    applied_at = result.payment.created_at or datetime.now(timezone.utc)
    event_date = applied_at.astimezone(ZoneInfo(settings.NEFT_BILLING_TZ)).date()
    start_at, end_at = period_bounds_for_dates(
        date_from=event_date,
        date_to=event_date,
        tz=settings.NEFT_BILLING_TZ,
    )
    settlement_period = (
        session.query(BillingPeriod)
        .filter(BillingPeriod.id == allocation.settlement_period_id)
        .one()
    )
    assert settlement_period.start_at == start_at.replace(tzinfo=None)
    assert settlement_period.end_at == end_at.replace(tzinfo=None)


def test_payment_allocation_is_idempotent(session):
    charge_date = date(2024, 4, 1)
    charge_period = _create_period(
        session,
        date_from=charge_date,
        date_to=charge_date,
        status=BillingPeriodStatus.OPEN,
    )
    invoice = _create_invoice(session, period=charge_period)
    _transition_period(session, period=charge_period, status=BillingPeriodStatus.FINALIZED)
    session.commit()

    service = FinanceService(session)
    first = service.apply_payment(
        invoice_id=invoice.id,
        amount=200,
        currency="RUB",
        idempotency_key="idem-payment",
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
    )
    second = service.apply_payment(
        invoice_id=invoice.id,
        amount=200,
        currency="RUB",
        idempotency_key="idem-payment",
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
    )

    allocations = (
        session.query(InvoiceSettlementAllocation)
        .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
        .all()
    )
    assert len(allocations) == 1
    assert first.invoice.amount_paid == second.invoice.amount_paid


def test_credit_note_allocation_after_lock(session):
    charge_date = date(2024, 5, 1)
    charge_period = _create_period(
        session,
        date_from=charge_date,
        date_to=charge_date,
        status=BillingPeriodStatus.OPEN,
    )
    invoice = _create_invoice(session, period=charge_period)
    _transition_period(session, period=charge_period, status=BillingPeriodStatus.LOCKED)
    session.commit()

    service = FinanceService(session)
    result = service.create_credit_note(
        invoice_id=invoice.id,
        amount=150,
        currency="RUB",
        reason="adjustment",
        idempotency_key="credit-after-lock",
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
    )

    allocation = (
        session.query(InvoiceSettlementAllocation)
        .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
        .one()
    )
    assert allocation.source_type == SettlementSourceType.CREDIT_NOTE
    assert allocation.amount == 150
    assert result.invoice.amount_due <= 1000
