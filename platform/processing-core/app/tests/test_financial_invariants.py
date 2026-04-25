from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest

from app.config import settings
from app.models.audit_log import AuditLog
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.finance import InvoiceSettlementAllocation
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus
from app.services.billing_periods import period_bounds_for_dates
from app.services.finance import FinanceService
from app.services.finance_invariants.errors import FinancialInvariantViolation
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


def _create_period(session, *, target_date: date, status: BillingPeriodStatus, period_type: BillingPeriodType) -> BillingPeriod:
    start_at, end_at = period_bounds_for_dates(
        date_from=target_date,
        date_to=target_date,
        tz=settings.NEFT_BILLING_TZ,
    )
    period = BillingPeriod(
        period_type=period_type,
        start_at=start_at,
        end_at=end_at,
        tz=settings.NEFT_BILLING_TZ,
        status=status,
    )
    session.add(period)
    session.flush()
    return period


def _create_invoice(session, *, period: BillingPeriod, amount_due: int = 1000) -> Invoice:
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
        amount_due=amount_due,
        status=InvoiceStatus.SENT,
        pdf_status=InvoicePdfStatus.READY,
    )
    session.add(invoice)
    session.flush()
    return invoice


def _latest_audit(session) -> AuditLog:
    return session.query(AuditLog).order_by(AuditLog.ts.desc(), AuditLog.id.desc()).first()


def test_payment_exceeds_due_blocks_and_audits(session):
    period = _create_period(
        session,
        target_date=date(2024, 2, 1),
        status=BillingPeriodStatus.FINALIZED,
        period_type=BillingPeriodType.ADHOC,
    )
    invoice = _create_invoice(session, period=period)
    session.commit()

    service = FinanceService(session)
    service.apply_payment(
        invoice_id=invoice.id,
        amount=600,
        currency="RUB",
        idempotency_key="pay-1",
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
    )

    with pytest.raises(FinancialInvariantViolation):
        service.apply_payment(
            invoice_id=invoice.id,
            amount=600,
            currency="RUB",
            idempotency_key="pay-2",
            token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
        )

    audit = _latest_audit(session)
    assert audit.event_type == "FINANCIAL_INVARIANT_VIOLATION"
    assert audit.entity_type == "payment"
    assert audit.after["invariants"][0]["name"] == "payment.amount_within_due"


def test_refund_exceeds_paid_blocks_and_audits(session):
    period = _create_period(
        session,
        target_date=date(2024, 3, 1),
        status=BillingPeriodStatus.FINALIZED,
        period_type=BillingPeriodType.ADHOC,
    )
    invoice = _create_invoice(session, period=period)
    session.commit()

    service = FinanceService(session)
    service.apply_payment(
        invoice_id=invoice.id,
        amount=400,
        currency="RUB",
        idempotency_key="pay-1",
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
    )

    with pytest.raises(FinancialInvariantViolation):
        service.create_refund(
            invoice_id=invoice.id,
            amount=500,
            currency="RUB",
            reason="over-refund",
            external_ref="refund-1",
            provider="bank",
            token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
        )

    audit = _latest_audit(session)
    assert audit.event_type == "FINANCIAL_INVARIANT_VIOLATION"
    assert audit.after["invariants"][0]["name"] == "refund.amount_within_paid"


def test_settlement_allocation_blocked_in_locked_period(session):
    target_date = datetime.now(timezone.utc).date()
    daily_period = _create_period(
        session,
        target_date=target_date,
        status=BillingPeriodStatus.LOCKED,
        period_type=BillingPeriodType.DAILY,
    )
    _create_period(
        session,
        target_date=target_date,
        status=BillingPeriodStatus.LOCKED,
        period_type=BillingPeriodType.ADHOC,
    )
    invoice = _create_invoice(session, period=daily_period)
    session.commit()

    service = FinanceService(session)
    with pytest.raises(FinancialInvariantViolation):
        service.apply_payment(
            invoice_id=invoice.id,
            amount=100,
            currency="RUB",
            idempotency_key="pay-locked",
            token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
        )

    session.expire_all()
    refreshed_invoice = session.get(Invoice, invoice.id)
    assert refreshed_invoice is not None
    assert refreshed_invoice.status == InvoiceStatus.SENT
    assert refreshed_invoice.amount_paid == 0
    assert refreshed_invoice.amount_due == 1000
    assert (
        session.query(InvoiceSettlementAllocation)
        .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
        .count()
        == 0
    )

    audit = _latest_audit(session)
    assert audit.event_type == "FINANCIAL_INVARIANT_VIOLATION"
    assert audit.after["invariants"][0]["name"] == "settlement.period_locked"

    start_at, end_at = period_bounds_for_dates(
        date_from=target_date,
        date_to=target_date,
        tz=settings.NEFT_BILLING_TZ,
    )
    assert daily_period.start_at == start_at.replace(tzinfo=None)
    assert daily_period.end_at == end_at.replace(tzinfo=None)


def test_invoice_negative_due_blocks_and_audits(session):
    period = _create_period(
        session,
        target_date=date(2024, 5, 1),
        status=BillingPeriodStatus.FINALIZED,
        period_type=BillingPeriodType.ADHOC,
    )
    invoice = _create_invoice(session, period=period, amount_due=-5)
    session.commit()

    service = FinanceService(session)
    with pytest.raises(FinancialInvariantViolation):
        service.apply_payment(
            invoice_id=invoice.id,
            amount=1,
            currency="RUB",
            idempotency_key="pay-negative",
            token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
        )

    audit = _latest_audit(session)
    assert audit.event_type == "FINANCIAL_INVARIANT_VIOLATION"
    assert audit.entity_type == "invoice"
    assert audit.after["invariants"][0]["name"] == "invoice.amount_due"
