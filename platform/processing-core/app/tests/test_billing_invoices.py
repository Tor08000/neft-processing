from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.audit_log import AuditLog
from app.models.billing_period import BillingPeriod, BillingPeriodType
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.models.internal_ledger import InternalLedgerAccount, InternalLedgerEntry, InternalLedgerTransaction
from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus, InvoiceStatus, InvoiceTransitionLog
from app.models.risk_decision import RiskDecision
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from app.services.billing_service import generate_invoices_for_period


TEST_TABLES = (
    AuditLog.__table__,
    BillingPeriod.__table__,
    Invoice.__table__,
    InvoiceLine.__table__,
    InvoiceTransitionLog.__table__,
    InternalLedgerAccount.__table__,
    InternalLedgerTransaction.__table__,
    InternalLedgerEntry.__table__,
    DecisionResultRecord.__table__,
    RiskDecision.__table__,
    RiskPolicy.__table__,
    RiskThresholdSet.__table__,
    RiskThreshold.__table__,
    RiskTrainingSnapshot.__table__,
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
    db.add(
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
    db.flush()
    try:
        yield db
    finally:
        db.close()


def test_create_invoice_totals(session):
    repo = BillingRepository(session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-1",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            currency="RUB",
            status=InvoiceStatus.ISSUED,
            lines=[
                BillingLineData(
                    product_id="p1",
                    liters=Decimal("10.000"),
                    unit_price=Decimal("50.000"),
                    line_amount=5000,
                    tax_amount=1000,
                ),
                BillingLineData(
                    product_id="p2",
                    liters=None,
                    unit_price=None,
                    line_amount=2500,
                    tax_amount=0,
                ),
            ],
            external_number="INV-1",
        )
    )

    assert invoice.total_amount == 7500
    assert invoice.tax_amount == 1000
    assert invoice.total_with_tax == 8500
    assert invoice.status == InvoiceStatus.ISSUED
    assert invoice.billing_period_id is not None
    period = session.get(BillingPeriod, invoice.billing_period_id)
    assert period is not None
    assert period.period_type == BillingPeriodType.ADHOC
    assert len(invoice.lines) == 2


def test_update_status(session):
    repo = BillingRepository(session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-2",
            period_from=date(2024, 2, 1),
            period_to=date(2024, 2, 28),
            currency="RUB",
            status=InvoiceStatus.ISSUED,
            pdf_status=InvoicePdfStatus.READY,
            lines=[BillingLineData(product_id="p1", liters=None, unit_price=None, line_amount=1000, tax_amount=0)],
        )
    )

    sent = repo.update_status(invoice.id, InvoiceStatus.SENT, issued_at=datetime.now(timezone.utc))
    assert sent is not None
    assert sent.status == InvoiceStatus.SENT

    sent.amount_paid = sent.total_with_tax
    sent.amount_due = 0
    session.add(sent)
    session.commit()

    paid_at = datetime.now(timezone.utc)
    updated = repo.update_status(invoice.id, InvoiceStatus.PAID, paid_at=paid_at)

    assert updated is not None
    assert updated.status == InvoiceStatus.PAID
    assert updated.paid_at == paid_at.replace(tzinfo=None)


def test_generate_invoices_for_period_reads_existing_invoices(session):
    session.add_all(
        [
            Invoice(
                client_id="client-1",
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
                currency="RUB",
                total_amount=5000,
                tax_amount=0,
                total_with_tax=5000,
                amount_paid=0,
                amount_due=5000,
                status=InvoiceStatus.ISSUED,
                created_at=datetime(2024, 3, 10, 12, 0, 0),
            ),
            Invoice(
                client_id="client-2",
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
                currency="RUB",
                total_amount=1500,
                tax_amount=0,
                total_with_tax=1500,
                amount_paid=0,
                amount_due=1500,
                status=InvoiceStatus.ISSUED,
                created_at=datetime(2024, 3, 11, 12, 0, 0),
            ),
            Invoice(
                client_id="client-3",
                period_from=date(2024, 4, 1),
                period_to=date(2024, 4, 30),
                currency="RUB",
                total_amount=900,
                tax_amount=0,
                total_with_tax=900,
                amount_paid=0,
                amount_due=900,
                status=InvoiceStatus.DRAFT,
                created_at=datetime(2024, 4, 1, 9, 0, 0),
            ),
        ]
    )
    session.commit()

    generated = generate_invoices_for_period(
        session,
        period_from=date(2024, 3, 1),
        period_to=date(2024, 3, 31),
        status=InvoiceStatus.ISSUED,
    )

    assert len(generated) == 2
    assert [invoice.client_id for invoice in generated] == ["client-2", "client-1"]
