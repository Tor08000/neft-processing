from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.audit_log import AuditLog
from app.models.billing_period import BillingPeriod
from app.models.clearing_batch import ClearingBatch
from app.models.decision_result import DecisionResult as DecisionResultRecord
from app.models.invoice import Invoice
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.models.risk_decision import RiskDecision
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_training_snapshot import RiskTrainingSnapshot
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services import billing_invoice_service
from app.services.billing_invoice_service import close_clearing_period, generate_invoice_for_batch
from app.services.billing_metrics import metrics


TEST_TABLES = (
    AuditLog.__table__,
    BillingPeriod.__table__,
    ClearingBatch.__table__,
    Invoice.__table__,
    Operation.__table__,
    DecisionResultRecord.__table__,
    RiskDecision.__table__,
    RiskPolicy.__table__,
    RiskThresholdSet.__table__,
    RiskThreshold.__table__,
    RiskTrainingSnapshot.__table__,
)


@pytest.fixture
def session():
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
    Table("reconciliation_requests", stub_metadata, Column("id", String(36), primary_key=True))
    stub_metadata.create_all(bind=engine)
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )

    metrics.reset()
    db = SessionLocal()
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
    db.commit()
    try:
        yield db
    finally:
        db.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        stub_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()


def _seed_captured_batch(session: Session, *, target_date: date) -> str:
    occurred_at = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=10)
    session.add(
        Operation(
            ext_operation_id=f"metrics-op-{target_date.isoformat()}",
            operation_type=OperationType.COMMIT,
            status=OperationStatus.CAPTURED,
            merchant_id="m1",
            terminal_id="t1",
            client_id="client-1",
            card_id="card-1",
            product_id="diesel",
            product_type=ProductType.AI95,
            amount=1000,
            amount_settled=1000,
            currency="RUB",
            quantity=Decimal("1.000"),
            unit_price=Decimal("1000.000"),
            captured_amount=1000,
            refunded_amount=0,
            created_at=occurred_at,
            updated_at=occurred_at,
            response_code="00",
            response_message="OK",
            authorized=True,
        )
    )
    session.commit()
    batch = close_clearing_period(session, date_from=target_date, date_to=target_date, tenant_id=1)
    return str(batch.id)


def test_metrics_record_successful_generation(session: Session):
    batch_id = _seed_captured_batch(session, target_date=date(2024, 1, 15))

    result = generate_invoice_for_batch(session, batch_id=batch_id, run_pdf_sync=False)

    assert result.created is True
    assert result.invoice.total_with_tax == 1000
    assert metrics.last_run_generated == 1
    assert metrics.generated_invoices_total >= 1
    assert metrics.billing_errors == 0


def test_metrics_count_errors(session: Session, monkeypatch: pytest.MonkeyPatch):
    batch_id = _seed_captured_batch(session, target_date=date(2024, 2, 10))

    def _boom(self, ctx):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(billing_invoice_service.DecisionEngine, "evaluate", _boom)

    with pytest.raises(RuntimeError, match="boom"):
        generate_invoice_for_batch(session, batch_id=batch_id, run_pdf_sync=False)

    assert metrics.billing_errors == 1
    assert metrics.last_run_generated == 0
