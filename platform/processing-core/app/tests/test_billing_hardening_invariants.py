from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.audit_log import AuditLog
from app.models.billing_job_run import BillingJobRun
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.billing_summary import BillingSummary
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus, InvoiceStatus, InvoiceTransitionLog
from app.models.money_flow import MoneyFlowEvent
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.models.fuel import FuelTransaction
from app.models.payout_batch import PayoutBatch, PayoutItem
from app.models.risk_decision import RiskDecision
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.billing.daily import run_billing_daily
from app.services.billing_periods import BillingPeriodConflict
from app.services.billing_run import BillingPeriodClosedError, BillingRunService
from app.services.finance import FinanceService
from app.services.policy import PolicyAccessDenied
from app.services.invoice_state_machine import InvalidTransitionError, InvoiceStateMachine
from app.services.payouts_service import close_payout_period


TEST_TABLES = (
    AuditLog.__table__,
    BillingPeriod.__table__,
    BillingSummary.__table__,
    BillingJobRun.__table__,
    Operation.__table__,
    FuelTransaction.__table__,
    Invoice.__table__,
    InvoiceLine.__table__,
    InvoiceTransitionLog.__table__,
    InvoicePayment.__table__,
    CreditNote.__table__,
    InvoiceSettlementAllocation.__table__,
    InternalLedgerAccount.__table__,
    InternalLedgerTransaction.__table__,
    InternalLedgerEntry.__table__,
    MoneyFlowEvent.__table__,
    DecisionResultRecord.__table__,
    RiskDecision.__table__,
    RiskPolicy.__table__,
    RiskThresholdSet.__table__,
    RiskThreshold.__table__,
    RiskTrainingSnapshot.__table__,
    PayoutBatch.__table__,
    PayoutItem.__table__,
)


@pytest.fixture
def _session_factory():
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

    stub_metadata = MetaData()
    Table("fuel_cards", stub_metadata, Column("id", String(36), primary_key=True))
    Table("fleet_vehicles", stub_metadata, Column("id", String(36), primary_key=True))
    Table("fleet_drivers", stub_metadata, Column("id", String(36), primary_key=True))
    Table("fuel_stations", stub_metadata, Column("id", String(36), primary_key=True))
    Table("fuel_networks", stub_metadata, Column("id", String(36), primary_key=True))
    Table("clearing_batch", stub_metadata, Column("id", String(36), primary_key=True))
    Table("reconciliation_requests", stub_metadata, Column("id", String(36), primary_key=True))
    stub_metadata.create_all(bind=engine)
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    session_local = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    try:
        yield session_local
    finally:
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        stub_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()


@pytest.fixture
def session(_session_factory):
    db = _session_factory()
    db.add_all(
        [
            RiskThresholdSet(
                id="global-payment-thresholds",
                subject_type=RiskSubjectType.PAYMENT,
                version=1,
                active=True,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.PAYMENT,
                block_threshold=90,
                review_threshold=70,
                allow_threshold=0,
            ),
            RiskThresholdSet(
                id="global-invoice-thresholds",
                subject_type=RiskSubjectType.INVOICE,
                version=1,
                active=True,
                scope=RiskThresholdScope.GLOBAL,
                action=RiskThresholdAction.INVOICE,
                block_threshold=90,
                review_threshold=70,
                allow_threshold=0,
            ),
        ]
    )
    db.flush()
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
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}
    with pytest.raises(BillingPeriodClosedError):
        service.run(
            period_type=BillingPeriodType.ADHOC,
            start_at=start_at,
            end_at=end_at,
            tz="UTC",
            client_id=None,
            token=token,
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
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}

    with pytest.raises(PolicyAccessDenied):
        close_payout_period(
            session,
            tenant_id=1,
            partner_id="m-1",
            date_from=target_date,
            date_to=target_date,
            token=token,
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
        token=token,
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
        token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
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
