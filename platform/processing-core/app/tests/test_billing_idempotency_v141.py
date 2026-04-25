from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.admin.billing as admin_billing_routes
from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.billing_job_run import BillingJobRun, BillingJobType
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.clearing import Clearing
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus, InvoiceTransitionLog, InvoiceLine
from app.models.money_flow import MoneyFlowEvent
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.models.risk_decision import RiskDecision
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.routers.admin.billing import router as admin_billing_router
from app.security.rbac.principal import Principal, get_principal
from app.services.billing_run import BillingRunService
from app.services.clearing_runs import ClearingRunService
from app.services.demo_seed import DEMO_CLIENT_ID
from app.services.finance import FinanceService


DEMO_MERCHANT_ID = "demo-merchant"
DEMO_TERMINAL_ID = "demo-terminal"
DEMO_CARD_ID = "demo-card"

TEST_TABLES = (
    AuditLog.__table__,
    BillingJobRun.__table__,
    BillingPeriod.__table__,
    BillingSummary.__table__,
    Clearing.__table__,
    Operation.__table__,
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
)


def _admin_token() -> dict:
    return {
        "sub": "admin-test",
        "tenant_id": 1,
        "roles": ["ADMIN", "ADMIN_FINANCE"],
    }


def _admin_principal() -> Principal:
    return Principal(
        user_id=None,
        roles={"admin"},
        scopes=set(),
        client_id=None,
        partner_id=None,
        is_admin=True,
        raw_claims=_admin_token(),
    )


def _create_period(
    session: Session,
    *,
    billing_date: date,
    status: BillingPeriodStatus = BillingPeriodStatus.OPEN,
    period_type: BillingPeriodType = BillingPeriodType.ADHOC,
) -> BillingPeriod:
    start_at = datetime.combine(billing_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    period = (
        session.query(BillingPeriod)
        .filter(BillingPeriod.period_type == period_type)
        .filter(BillingPeriod.start_at == start_at)
        .filter(BillingPeriod.end_at == end_at)
        .one_or_none()
    )
    if period is None:
        period = BillingPeriod(
            period_type=period_type,
            start_at=start_at,
            end_at=end_at,
            tz="UTC",
            status=status,
        )
        session.add(period)
        session.flush()
    else:
        period.status = status
        session.add(period)
        session.flush()
    return period


def _seed_global_thresholds(session: Session) -> None:
    if session.query(RiskThresholdSet).count():
        return
    session.add_all(
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
    session.flush()


def _seed_operations(session: Session, *, billing_date: date) -> list[Operation]:
    base_dt = datetime.combine(billing_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    operations: list[Operation] = []
    for idx, amount in enumerate((500, 700, 900), start=1):
        ext_id = f"idem-op-{billing_date.isoformat()}-{idx}"
        existing = session.query(Operation).filter(Operation.ext_operation_id == ext_id).one_or_none()
        if existing is not None:
            operations.append(existing)
            continue
        operation = Operation(
            ext_operation_id=ext_id,
            operation_type=OperationType.COMMIT,
            status=OperationStatus.CAPTURED if idx % 2 else OperationStatus.COMPLETED,
            created_at=base_dt + timedelta(hours=idx),
            updated_at=base_dt + timedelta(hours=idx),
            merchant_id=DEMO_MERCHANT_ID,
            terminal_id=DEMO_TERMINAL_ID,
            client_id=DEMO_CLIENT_ID,
            card_id=DEMO_CARD_ID,
            product_id="FUEL",
            product_type=ProductType.AI92,
            amount=amount,
            amount_settled=amount,
            currency="RUB",
            quantity=Decimal("1.0"),
            unit_price=Decimal(str(amount)),
            captured_amount=amount,
            refunded_amount=0,
            response_code="00",
            response_message="OK",
            authorized=True,
        )
        session.add(operation)
        operations.append(operation)
    session.flush()
    return operations


def _seed_billing_summary(session: Session, *, billing_date: date, billing_period_id: str, operations: list[Operation]) -> BillingSummary:
    summary = (
        session.query(BillingSummary)
        .filter(BillingSummary.billing_date == billing_date)
        .filter(BillingSummary.merchant_id == DEMO_MERCHANT_ID)
        .filter(BillingSummary.currency == "RUB")
        .one_or_none()
    )
    total_amount = sum(int(operation.amount_settled or operation.amount or 0) for operation in operations)
    if summary is None:
        summary = BillingSummary(
            billing_date=billing_date,
            billing_period_id=billing_period_id,
            client_id=DEMO_CLIENT_ID,
            merchant_id=DEMO_MERCHANT_ID,
            product_type=ProductType.AI92,
            currency="RUB",
            total_amount=total_amount,
            total_quantity=len(operations),
            operations_count=len(operations),
            commission_amount=0,
            status=BillingSummaryStatus.FINALIZED,
        )
        session.add(summary)
    else:
        summary.billing_period_id = billing_period_id
        summary.total_amount = total_amount
        summary.total_quantity = len(operations)
        summary.operations_count = len(operations)
        summary.status = BillingSummaryStatus.FINALIZED
        session.add(summary)
    session.flush()
    return summary


class _HarnessDemoSeeder:
    def __init__(self, db: Session):
        self.db = db

    def seed(self, billing_date: date | None = None) -> dict[str, str]:
        target_date = billing_date or date.today() - timedelta(days=1)
        operations = _seed_operations(self.db, billing_date=target_date)
        period = _create_period(
            self.db,
            billing_date=target_date,
            status=BillingPeriodStatus.OPEN,
            period_type=BillingPeriodType.ADHOC,
        )
        _seed_billing_summary(
            self.db,
            billing_date=target_date,
            billing_period_id=str(period.id),
            operations=operations,
        )
        self.db.commit()

        result = BillingRunService(self.db).run(
            period_type=BillingPeriodType.ADHOC,
            start_at=datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            end_at=datetime.combine(target_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
            tz="UTC",
            client_id=None,
            idempotency_key=f"billing-seed-{target_date.isoformat()}",
            token=_admin_token(),
        )
        result.billing_period.status = BillingPeriodStatus.FINALIZED
        result.billing_period.finalized_at = datetime.now(timezone.utc)
        self.db.add(result.billing_period)
        self.db.commit()
        return {
            "client_id": DEMO_CLIENT_ID,
            "merchant_id": DEMO_MERCHANT_ID,
            "terminal_id": DEMO_TERMINAL_ID,
            "card_id": DEMO_CARD_ID,
            "billing_period_id": str(result.billing_period.id),
            "period_from": str(result.period_from),
            "period_to": str(result.period_to),
        }


@pytest.fixture()
def billing_idempotency_context(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(admin_billing_routes, "DemoSeeder", _HarnessDemoSeeder)

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
    Table("fuel_stations", stub_metadata, Column("id", String(36), primary_key=True))
    Table("clearing_batch", stub_metadata, Column("id", String(36), primary_key=True))
    Table("reconciliation_requests", stub_metadata, Column("id", String(36), primary_key=True))
    stub_metadata.create_all(bind=engine)
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    with session_factory() as session:
        _seed_global_thresholds(session)
        session.commit()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    local_app = FastAPI()
    local_app.include_router(admin_billing_router, prefix="/api/v1/admin")
    local_app.dependency_overrides[get_db] = override_get_db
    local_app.dependency_overrides[require_admin_user] = _admin_token
    local_app.dependency_overrides[get_principal] = _admin_principal

    try:
        with TestClient(local_app) as api_client:
            yield session_factory, api_client
    finally:
        local_app.dependency_overrides.clear()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        stub_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()


@pytest.fixture()
def admin_client(billing_idempotency_context) -> TestClient:
    _, api_client = billing_idempotency_context
    return api_client


@pytest.fixture()
def session(billing_idempotency_context) -> Session:
    session_factory, _ = billing_idempotency_context
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def _make_period(day: date) -> tuple[str, str]:
    start_at = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    return start_at.isoformat(), end_at.isoformat()


def test_manual_billing_idempotent_key_reuses_job(admin_client: TestClient, session: Session):
    billing_date = date(2024, 1, 5)
    _seed_operations(session, billing_date=billing_date)
    session.commit()
    start_at, end_at = _make_period(billing_date)

    payload = {
        "period_type": "ADHOC",
        "start_at": start_at,
        "end_at": end_at,
        "tz": "UTC",
        "client_id": None,
        "idempotency_key": "idem-billing-manual",
    }

    first = admin_client.post("/api/v1/admin/billing/run", json=payload)
    assert first.status_code == 200
    second = admin_client.post("/api/v1/admin/billing/run", json=payload)
    assert second.status_code == 200

    runs = (
        session.query(BillingJobRun)
        .filter(BillingJobRun.job_type == BillingJobType.MANUAL_RUN)
        .filter(BillingJobRun.correlation_id == "idem-billing-manual")
        .all()
    )
    assert len(runs) == 1


def test_clearing_run_reuses_existing_result(session: Session):
    billing_date = date(2024, 1, 6)
    period = _create_period(
        session,
        billing_date=billing_date,
        status=BillingPeriodStatus.FINALIZED,
        period_type=BillingPeriodType.DAILY,
    )
    operations = _seed_operations(session, billing_date=billing_date)
    _seed_billing_summary(
        session,
        billing_date=billing_date,
        billing_period_id=str(period.id),
        operations=operations,
    )
    session.commit()
    job_key = "idem-clearing"
    service = ClearingRunService(session)

    first = asyncio.run(service.run(clearing_date=billing_date, idempotency_key=job_key))
    assert first
    second = asyncio.run(service.run(clearing_date=billing_date, idempotency_key=job_key))
    assert len(second) == len(first)

    runs = (
        session.query(BillingJobRun)
        .filter(BillingJobRun.job_type == BillingJobType.CLEARING_RUN)
        .filter(BillingJobRun.correlation_id == job_key)
        .all()
    )
    assert len(runs) == 1


def test_finance_payment_and_credit_note_idempotent(session: Session):
    billing_date = date(2024, 1, 7)
    period = _create_period(
        session,
        billing_date=billing_date,
        status=BillingPeriodStatus.FINALIZED,
        period_type=BillingPeriodType.ADHOC,
    )
    invoice = Invoice(
        client_id=DEMO_CLIENT_ID,
        billing_period_id=period.id,
        period_from=billing_date,
        period_to=billing_date,
        currency="RUB",
        total_amount=1_000,
        tax_amount=0,
        total_with_tax=1_000,
        amount_paid=0,
        amount_due=1_000,
        status=InvoiceStatus.SENT,
        pdf_status=InvoicePdfStatus.READY,
    )
    session.add(invoice)
    session.commit()

    finance = FinanceService(session)
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": 1}
    payment_key = "idem-payment"
    payment = finance.apply_payment(
        invoice_id=invoice.id,
        amount=100,
        currency="RUB",
        idempotency_key=payment_key,
        token=token,
    )
    payment_repeat = finance.apply_payment(
        invoice_id=invoice.id,
        amount=100,
        currency="RUB",
        idempotency_key=payment_key,
        token=token,
    )
    assert payment.payment.id == payment_repeat.payment.id

    credit_key = "idem-credit"
    credit = finance.create_credit_note(
        invoice_id=invoice.id,
        amount=50,
        currency="RUB",
        reason="test",
        idempotency_key=credit_key,
        token=token,
    )
    credit_repeat = finance.create_credit_note(
        invoice_id=invoice.id,
        amount=50,
        currency="RUB",
        reason="test",
        idempotency_key=credit_key,
        token=token,
    )
    assert credit.credit_note.id == credit_repeat.credit_note.id
    assert credit_repeat.invoice.amount_due == credit.invoice.amount_due


def test_seed_endpoint_returns_period(admin_client: TestClient):
    first = admin_client.post("/api/v1/admin/billing/seed")
    assert first.status_code == 200
    second = admin_client.post("/api/v1/admin/billing/seed")
    assert second.status_code == 200

    payload = first.json()
    replay = second.json()
    assert "billing_period_id" in payload
    assert "period_from" in payload
    assert replay["billing_period_id"] == payload["billing_period_id"]
