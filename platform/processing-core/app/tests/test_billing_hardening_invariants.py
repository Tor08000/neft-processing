from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from app.db import Base, SessionLocal, engine, reset_engine
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.billing.daily import run_billing_daily
from app.services.billing_periods import BillingPeriodConflict
from app.services.billing_run import BillingPeriodClosedError, BillingRunService
from app.services.finance import FinanceService
from app.services.invoice_state_machine import InvalidTransitionError, InvoiceStateMachine
from app.services.payouts_service import PayoutError, close_payout_period


@pytest.fixture(autouse=True)
def _use_sqlite(monkeypatch: pytest.MonkeyPatch):
    import app.db as db

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(db, "DATABASE_URL", "sqlite:///:memory:", raising=False)
    monkeypatch.setattr(db, "raw_db_url", "sqlite:///:memory:", raising=False)
    reset_engine()


@pytest.fixture(autouse=True)
def _reset_db(_use_sqlite):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


def _seed_operation(session, *, target_date: date, amount: int = 1000):
    ts = datetime.combine(target_date, time.min, tzinfo=timezone.utc) + timedelta(hours=2)
    op = Operation(
        ext_operation_id=f"inv-op-{target_date.isoformat()}-{amount}",
        operation_type=OperationType.COMMIT,
        status=OperationStatus.COMPLETED,
        created_at=ts,
        updated_at=ts,
        merchant_id="m-1",
        terminal_id="t-1",
        client_id="client-1",
        card_id="card-1",
        product_id="FUEL",
        product_type=ProductType.AI92,
        amount=amount,
        amount_settled=amount,
        currency="RUB",
        quantity=Decimal("1.0"),
        unit_price=Decimal("1.0"),
        captured_amount=amount,
        refunded_amount=0,
        response_code="00",
        response_message="OK",
        authorized=True,
    )
    session.add(op)
    session.flush()


def test_billing_summary_rebuild_blocked_after_finalize(session):
    billing_date = date(2024, 4, 1)
    _create_period(
        session,
        date_from=billing_date,
        date_to=billing_date,
        status=BillingPeriodStatus.FINALIZED,
        period_type=BillingPeriodType.DAILY,
    )
    _seed_operation(session, target_date=billing_date)
    session.commit()

    with pytest.raises(BillingPeriodConflict):
        run_billing_daily(billing_date, session=session)


def test_billing_run_blocks_invoice_lines_after_finalize(session):
    start_at = datetime(2024, 5, 1, tzinfo=timezone.utc)
    end_at = datetime(2024, 5, 2, tzinfo=timezone.utc)
    period = BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=start_at,
        end_at=end_at,
        tz="UTC",
        status=BillingPeriodStatus.FINALIZED,
    )
    session.add(period)
    _seed_operation(session, target_date=start_at.date())
    session.commit()

    service = BillingRunService(session)
    with pytest.raises(BillingPeriodClosedError):
        service.run(
            period_type=BillingPeriodType.ADHOC,
            start_at=start_at,
            end_at=end_at,
            tz="UTC",
            client_id=None,
        )


def test_payout_blocked_before_finalize_allows_after_lock(session):
    target_date = date(2024, 6, 1)
    period = _create_period(
        session,
        date_from=target_date,
        date_to=target_date,
        status=BillingPeriodStatus.OPEN,
    )
    _seed_operation(session, target_date=target_date)
    session.commit()

    with pytest.raises(PayoutError):
        close_payout_period(
            session,
            tenant_id=1,
            partner_id="m-1",
            date_from=target_date,
            date_to=target_date,
        )

    period.status = BillingPeriodStatus.LOCKED
    session.add(period)
    session.commit()

    result = close_payout_period(
        session,
        tenant_id=1,
        partner_id="m-1",
        date_from=target_date,
        date_to=target_date,
    )
    assert result.batch.state.value == "READY"


def test_payments_allowed_after_finalize(session):
    target_date = date(2024, 7, 1)
    period = _create_period(
        session,
        date_from=target_date,
        date_to=target_date,
        status=BillingPeriodStatus.FINALIZED,
    )
    invoice = Invoice(
        client_id="client-1",
        period_from=target_date,
        period_to=target_date,
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
    session.commit()

    service = FinanceService(session)
    result = service.apply_payment(
        invoice_id=invoice.id,
        amount=400,
        currency="RUB",
        idempotency_key="pay-finalized",
    )
    assert result.payment.invoice_id == invoice.id
    assert result.invoice.status == InvoiceStatus.PARTIALLY_PAID


def test_locked_period_blocks_amount_transition(session):
    target_date = date(2024, 8, 1)
    period = _create_period(
        session,
        date_from=target_date,
        date_to=target_date,
        status=BillingPeriodStatus.LOCKED,
    )
    invoice = Invoice(
        client_id="client-1",
        period_from=target_date,
        period_to=target_date,
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
    session.commit()

    machine = InvoiceStateMachine(invoice, db=session)
    with pytest.raises(InvalidTransitionError):
        machine.transition(
            to=InvoiceStatus.PARTIALLY_PAID,
            actor="test",
            reason="locked-period",
            payment_amount=100,
        )


def test_billing_hash_deterministic(session):
    billing_date = date(2024, 9, 1)
    _create_period(
        session,
        date_from=billing_date,
        date_to=billing_date,
        status=BillingPeriodStatus.OPEN,
        period_type=BillingPeriodType.DAILY,
    )
    _seed_operation(session, target_date=billing_date, amount=1200)
    session.commit()

    first = run_billing_daily(billing_date, session=session)
    second = run_billing_daily(billing_date, session=session)

    assert first
    assert second
    assert first[0].hash == second[0].hash
    assert first[0].total_amount == second[0].total_amount
