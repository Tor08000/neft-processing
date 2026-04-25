from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.operation import Operation, OperationStatus, OperationType
from app.models.posting_batch import PostingBatch, PostingBatchType
from app.services.ledger.balance_service import BalanceService
from app.services.operations_scenarios.refunds import RefundCapExceeded, RefundService

from ._money_router_harness import OPERATIONAL_DISPUTE_REFUND_TEST_TABLES, money_session_context

MERCHANT_ID = "11111111-1111-1111-1111-111111111111"
CLIENT_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def session():
    with money_session_context(tables=OPERATIONAL_DISPUTE_REFUND_TEST_TABLES) as db:
        yield db


def _make_operation(db, *, captured: int = 100) -> Operation:
    op = Operation(
        operation_id=str(uuid4()),
        operation_type=OperationType.CAPTURE,
        status=OperationStatus.CAPTURED,
        merchant_id=MERCHANT_ID,
        terminal_id="term-1",
        client_id=CLIENT_ID,
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


def test_refund_cap_enforced(session):
    op = _make_operation(session, captured=100)
    service = RefundService(session)

    with pytest.raises(RefundCapExceeded):
        service.request_refund(
            operation=op,
            amount=150,
            reason=None,
            initiator="tester",
            idempotency_key="refund-cap",
        )


def test_refund_idempotent(session):
    op = _make_operation(session, captured=100)
    service = RefundService(session)

    first = service.request_refund(
        operation=op,
        amount=50,
        reason="test",
        initiator="tester",
        idempotency_key="refund-idem",
    )
    second = service.request_refund(
        operation=op,
        amount=50,
        reason="test",
        initiator="tester",
        idempotency_key="refund-idem",
    )

    assert first.posting_id == second.posting_id
    assert first.refund.id == second.refund.id


def test_refund_same_period_posting_affects_balances(session):
    op = _make_operation(session, captured=120)
    service = RefundService(session)
    result = service.request_refund(
        operation=op,
        amount=70,
        reason="partial",
        initiator="tester",
        idempotency_key="refund-balance",
    )

    payable_account = service._partner_payable(op)
    client_account = service._client_main(op)
    balances = BalanceService(session).snapshot_balances([payable_account, client_account])
    assert balances[payable_account]["current"] == Decimal("-70")
    assert balances[client_account]["current"] == Decimal("70")
    posting = session.query(PostingBatch).filter(PostingBatch.id == result.posting_id).one()
    assert posting.posting_type == PostingBatchType.REFUND


def test_refund_cross_period_creates_adjustment(session):
    op = _make_operation(session, captured=80)
    service = RefundService(session)
    result = service.request_refund(
        operation=op,
        amount=30,
        reason="late",
        initiator="tester",
        idempotency_key="refund-adjust",
        settlement_closed=True,
    )

    assert result.settlement_policy.name == "ADJUSTMENT_REQUIRED"
    assert result.adjustment_id is not None
    posting = session.query(PostingBatch).filter(PostingBatch.id == result.posting_id).one()
    assert posting.posting_type == PostingBatchType.ADJUSTMENT
