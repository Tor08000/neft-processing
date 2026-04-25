import pytest
from sqlalchemy.orm import Session
from app.models.financial_adjustment import FinancialAdjustment
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.posting_batch import PostingBatch, PostingBatchType
from app.models.reversal import Reversal
from app.services.operations_scenarios.reversals import ReversalService
from app.tests._money_router_harness import ACCOUNT_LEDGER_TEST_TABLES, money_session_context

REVERSAL_TEST_TABLES = ACCOUNT_LEDGER_TEST_TABLES + (
    Reversal.__table__,
    FinancialAdjustment.__table__,
)


@pytest.fixture
def session() -> Session:
    with money_session_context(tables=REVERSAL_TEST_TABLES) as db:
        yield db


def _make_operation(db, *, captured: int = 60) -> Operation:
    op = Operation(
        operation_id="op-rev",
        operation_type=OperationType.CAPTURE,
        status=OperationStatus.CAPTURED,
        merchant_id="22222222-2222-2222-2222-222222222222",
        terminal_id="term-1",
        client_id="33333333-3333-3333-3333-333333333333",
        card_id="44444444-4444-4444-4444-444444444444",
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
