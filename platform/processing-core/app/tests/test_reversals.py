import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.posting_batch import PostingBatch, PostingBatchType
from app.services.operations_scenarios.reversals import ReversalService

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _reset_db():
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


def _make_operation(db, *, captured: int = 60) -> Operation:
    op = Operation(
        operation_id="op-rev",
        operation_type=OperationType.CAPTURE,
        status=OperationStatus.CAPTURED,
        merchant_id="merchant-1",
        terminal_id="term-1",
        client_id="client-1",
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


def test_reversal_blocks_direct_on_closed_settlement(session):
    op = _make_operation(session)
    service = ReversalService(session)

    result = service.reverse_capture(
        operation=op,
        reason="late",
        initiator="tester",
        idempotency_key="rev-late",
        settlement_closed=True,
    )

    assert result.settlement_policy.name == "ADJUSTMENT_REQUIRED"
    assert result.adjustment_id is not None
    posting = session.query(PostingBatch).filter(PostingBatch.id == result.posting_id).one()
    assert posting.posting_type == PostingBatchType.ADJUSTMENT
