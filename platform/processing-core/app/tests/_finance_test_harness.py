from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Column, MetaData, String, Table, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.audit_log import AuditLog
from app.models.billing_job_run import BillingJobRun
from app.models.billing_period import BillingPeriod
from app.models.billing_summary import BillingSummary
from app.models.decision_result import DecisionResult
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.invoice import Invoice, InvoiceLine, InvoiceTransitionLog
from app.models.money_flow import MoneyFlowEvent
from app.models.refund_request import RefundRequest
from app.models.risk_decision import RiskDecision
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope


FINANCE_INVARIANT_TEST_TABLES = (
    AuditLog.__table__,
    BillingPeriod.__table__,
    BillingJobRun.__table__,
    BillingSummary.__table__,
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
    RefundRequest.__table__,
    DecisionResult.__table__,
    RiskDecision.__table__,
    RiskPolicy.__table__,
    RiskThresholdSet.__table__,
    RiskThreshold.__table__,
    RiskTrainingSnapshot.__table__,
)


def seed_default_finance_thresholds(session: Session) -> None:
    if session.get(RiskThresholdSet, "global-payment-thresholds") is None:
        session.add(
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
            )
        )
    if session.get(RiskThresholdSet, "global-invoice-thresholds") is None:
        session.add(
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
            )
        )
    session.flush()


@contextmanager
def finance_invariant_session_context() -> Iterator[Session]:
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
    for table_name in (
        "fuel_cards",
        "fleet_vehicles",
        "fleet_drivers",
        "fuel_stations",
        "fuel_networks",
        "clearing_batch",
        "reconciliation_requests",
    ):
        Table(table_name, stub_metadata, Column("id", String(36), primary_key=True))

    stub_metadata.create_all(bind=engine)
    for table in FINANCE_INVARIANT_TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    session_local = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(FINANCE_INVARIANT_TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        stub_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()
