from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

import app.repositories.billing_repository as billing_repository
import app.services.billing.daily as billing_daily_service
import app.services.invoice_state_machine as invoice_state_machine
import app.services.invoicing.monthly as monthly_service
from app.config import settings
from app.models.audit_log import AuditLog
from app.models.billing_job_run import BillingJobRun
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.clearing_batch import ClearingBatch
from app.models.clearing_batch_operation import ClearingBatchOperation
from app.models.client_actions import ReconciliationRequest
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, InvoiceTransitionLog
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.billing.daily import run_billing_daily
from app.services.clearing_daily import run_clearing_daily
from app.services.invoicing import run_invoice_monthly
from app.tests._money_router_harness import FUEL_STATIONS_REFLECTED, money_session_context


class _AllowDecisionEngine:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def evaluate(self, _ctx):
        return type("Decision", (), {"outcome": invoice_state_machine.DecisionOutcome.ALLOW})()


BILLING_PIPELINE_TEST_TABLES = (
    FUEL_STATIONS_REFLECTED,
    BillingJobRun.__table__,
    BillingPeriod.__table__,
    BillingSummary.__table__,
    ClearingBatch.__table__,
    ClearingBatchOperation.__table__,
    ReconciliationRequest.__table__,
    Operation.__table__,
    Invoice.__table__,
    InvoiceLine.__table__,
    InvoiceTransitionLog.__table__,
    AuditLog.__table__,
)


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "NEFT_BILLING_DAILY_ENABLED", True)
    monkeypatch.setattr(settings, "NEFT_CLEARING_DAILY_ENABLED", True)
    monkeypatch.setattr(settings, "NEFT_INVOICE_MONTHLY_ENABLED", True)
    monkeypatch.setattr(billing_daily_service, "_aggregate_fuel_transactions", lambda _session, _date: [])
    monkeypatch.setattr(monthly_service, "_link_fuel_transactions_to_invoice", lambda *args, **kwargs: None)
    monkeypatch.setattr(monthly_service.FinancialInvariantChecker, "check_invoice", lambda self, invoice, **kwargs: None)
    monkeypatch.setattr(invoice_state_machine, "DecisionEngine", _AllowDecisionEngine)
    monkeypatch.setattr(
        billing_repository.InternalLedgerService,
        "post_invoice_issued",
        lambda self, *, invoice, tenant_id: None,
    )

    with money_session_context(tables=BILLING_PIPELINE_TEST_TABLES) as db:
        yield db


def _operation_for_date(target_date: date, *, client_id: str = "c1", merchant_id: str = "m1", amount: int = 1_000):
    ts = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=10)
    return Operation(
        ext_operation_id=f"ext-{target_date.isoformat()}-{client_id}-{amount}",
        operation_type=OperationType.COMMIT,
        status=OperationStatus.COMPLETED,
        created_at=ts,
        updated_at=ts,
        merchant_id=merchant_id,
        terminal_id="terminal-1",
        client_id=client_id,
        card_id="card-1",
        product_id="prod-1",
        product_type=ProductType.AI95,
        amount=amount,
        amount_settled=amount,
        currency="RUB",
        quantity=Decimal("1.0"),
        unit_price=Decimal("1000.0"),
        captured_amount=amount,
        refunded_amount=0,
        response_code="00",
        response_message="OK",
        authorized=True,
    )


def _create_period(session, date_from: date, date_to: date, period_type: BillingPeriodType) -> BillingPeriod:
    period = BillingPeriod(
        period_type=period_type,
        start_at=datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc),
        end_at=datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc),
        tz="UTC",
        status=BillingPeriodStatus.OPEN,
    )
    session.add(period)
    session.flush()
    return period


def test_billing_daily_smoke(session):
    billing_date = date(2024, 6, 1)
    session.add_all(
        [
            _operation_for_date(billing_date, amount=1_000),
            _operation_for_date(billing_date, amount=500, client_id="c2"),
        ]
    )
    session.commit()

    summaries = run_billing_daily(billing_date, session=session)
    db_summary = session.query(BillingSummary).filter_by(billing_date=billing_date).all()

    assert summaries
    assert len(db_summary) == 2
    assert all(summary.status == BillingSummaryStatus.PENDING for summary in db_summary)


def test_clearing_daily_smoke(session):
    clearing_date = date(2024, 6, 2)
    session.add_all(
        [
            _operation_for_date(clearing_date, merchant_id="m1", amount=700),
            _operation_for_date(clearing_date, merchant_id="m1", amount=300, client_id="c2"),
        ]
    )
    session.commit()

    batches = run_clearing_daily(clearing_date, session=session)
    stored_batches = session.query(ClearingBatch).filter_by(date_from=clearing_date).all()

    assert batches
    assert len(stored_batches) == 1
    assert stored_batches[0].operations_count == 2
    assert stored_batches[0].status == "PENDING"


def test_invoice_monthly_smoke(session):
    target_month = date(2024, 5, 1)
    period = _create_period(session, date(2024, 5, 1), date(2024, 5, 31), BillingPeriodType.MONTHLY)
    session.add_all(
        [
            BillingSummary(
                billing_date=date(2024, 5, 10),
                billing_period_id=period.id,
                client_id="client-1",
                merchant_id="m1",
                product_type=ProductType.AI92,
                currency="RUB",
                total_amount=1_500,
                total_quantity=Decimal("1.5"),
                operations_count=2,
                commission_amount=15,
                status=BillingSummaryStatus.FINALIZED,
            ),
            BillingSummary(
                billing_date=date(2024, 5, 11),
                billing_period_id=period.id,
                client_id="client-1",
                merchant_id="m2",
                product_type=ProductType.AI95,
                currency="RUB",
                total_amount=500,
                total_quantity=Decimal("0.5"),
                operations_count=1,
                commission_amount=5,
                status=BillingSummaryStatus.FINALIZED,
            ),
        ]
    )
    session.commit()

    result = run_invoice_monthly(target_month, session=session)
    invoices = result.invoices

    assert invoices
    assert result.metrics["created"] == 1
    assert invoices[0].status == InvoiceStatus.ISSUED
    assert invoices[0].total_amount == 2_000
    assert len(invoices[0].lines) == 2
