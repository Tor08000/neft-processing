import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.posting_batch import PostingBatch, PostingBatchType
from app.models.refund_request import SettlementPolicy
from app.services.operations_scenarios.refunds import RefundAmountInvalid, RefundCapExceeded, RefundService
from app.services.operations_scenarios.reversals import ReversalAlreadyExists, ReversalService

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

_aux = MetaData()
Table("cards", _aux, Column("id", String(64), primary_key=True))
Table("fuel_stations", _aux, Column("id", String(36), primary_key=True))


@pytest.fixture(autouse=True)
def _reset_db():
    tables = [
        _aux.tables["cards"],
        _aux.tables["fuel_stations"],
        Base.metadata.tables["operations"],
        Base.metadata.tables["accounts"],
        Base.metadata.tables["account_balances"],
        Base.metadata.tables["ledger_entries"],
        Base.metadata.tables["posting_batches"],
        Base.metadata.tables["audit_log"],
        Base.metadata.tables["refund_requests"],
        Base.metadata.tables["reversals"],
        Base.metadata.tables["financial_adjustments"],
    ]
    for table in reversed(tables):
        table.drop(bind=engine, checkfirst=True)
    for table in tables:
        table.create(bind=engine, checkfirst=True)
    yield
    for table in reversed(tables):
        table.drop(bind=engine, checkfirst=True)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _make_capture(db, captured: int = 200):
    op = Operation(
        operation_id="cap-boundary",
        operation_type=OperationType.CAPTURE,
        status=OperationStatus.CAPTURED,
        merchant_id="22222222-2222-2222-2222-222222222222",
        terminal_id="term-1",
        client_id="33333333-3333-3333-3333-333333333333",
        card_id="card-1",
        amount=captured,
        currency="RUB",
        captured_amount=captured,
        refunded_amount=0,
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return op


def test_closed_settlement_refund_creates_adjustment_only(session):
    op = _make_capture(session, captured=200)
    service = RefundService(session)

    result = service.request_refund(
        operation=op,
        amount=60,
        reason="late-refund",
        initiator="audit",
        idempotency_key="settlement-closed-refund-1",
        settlement_closed=True,
    )

    assert result.settlement_policy == SettlementPolicy.ADJUSTMENT_REQUIRED
    assert result.adjustment_id is not None

    posting = session.query(PostingBatch).filter(PostingBatch.id == result.posting_id).one()
    assert posting.posting_type == PostingBatchType.ADJUSTMENT


def test_refund_negative_or_zero_amount_rejected_with_domain_error(session):
    op = _make_capture(session)
    service = RefundService(session)

    with pytest.raises(RefundAmountInvalid, match="positive"):
        service.request_refund(
            operation=op,
            amount=0,
            reason="bad",
            initiator="audit",
            idempotency_key="refund-zero",
        )


def test_refund_cannot_exceed_captured_amount(session):
    op = _make_capture(session, captured=100)
    service = RefundService(session)

    with pytest.raises(RefundCapExceeded):
        service.request_refund(
            operation=op,
            amount=101,
            reason="over-refund",
            initiator="audit",
            idempotency_key="refund-over-cap",
        )


def test_repeated_reversal_of_same_operation_is_rejected(session):
    op = _make_capture(session, captured=50)
    service = ReversalService(session)

    first = service.reverse_capture(
        operation=op,
        reason="first",
        initiator="audit",
        idempotency_key="reversal-1",
    )
    assert first.posting_id is not None

    with pytest.raises(ReversalAlreadyExists, match="already reversed"):
        service.reverse_capture(
            operation=op,
            reason="second",
            initiator="audit",
            idempotency_key="reversal-2",
        )
