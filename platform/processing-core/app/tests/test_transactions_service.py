from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from app.services.transactions import (
    _group_operations_by_auth,
    build_transaction_from_operations,
)


class DummyOperation:
    def __init__(
        self,
        operation_type: str,
        amount: int,
        created_at: datetime,
        operation_id: Optional[str] = None,
        parent_operation_id: Optional[str] = None,
    ) -> None:
        self.operation_id = operation_id or str(uuid4())
        self.created_at = created_at
        self.operation_type = operation_type
        self.status = "OK"
        self.merchant_id = "m1"
        self.terminal_id = "t1"
        self.client_id = "c1"
        self.card_id = "card1"
        self.amount = amount
        self.currency = "RUB"
        self.daily_limit = None
        self.limit_per_tx = None
        self.used_today = None
        self.new_used_today = None
        self.authorized = False
        self.response_code = "00"
        self.response_message = "OK"
        self.parent_operation_id = parent_operation_id
        self.reason = None
        self.mcc = None
        self.product_code = None
        self.product_category = None
        self.tx_type = None


DEFAULT_TIME = datetime.now()


def make_auth(amount: int, created_at: datetime = DEFAULT_TIME) -> DummyOperation:
    return DummyOperation("AUTH", amount, created_at, operation_id=str(uuid4()))


def make_capture(auth: DummyOperation, amount: int, shift: int = 1) -> DummyOperation:
    return DummyOperation(
        "CAPTURE",
        amount,
        created_at=auth.created_at + timedelta(minutes=shift),
        parent_operation_id=auth.operation_id,
    )


def make_refund(parent_op: DummyOperation, amount: int, shift: int = 2) -> DummyOperation:
    return DummyOperation(
        "REFUND",
        amount,
        created_at=parent_op.created_at + timedelta(minutes=shift),
        parent_operation_id=parent_op.operation_id,
    )


def make_reversal(auth: DummyOperation, shift: int = 1) -> DummyOperation:
    return DummyOperation(
        "REVERSAL",
        0,
        created_at=auth.created_at + timedelta(minutes=shift),
        parent_operation_id=auth.operation_id,
    )


def test_authorized_only_status():
    auth = make_auth(100)
    transaction = build_transaction_from_operations([auth])

    assert transaction is not None
    assert transaction.status == "AUTHORIZED"
    assert transaction.authorized_amount == 100
    assert transaction.captured_amount == 0
    assert transaction.refunded_amount == 0


def test_full_capture_status():
    auth = make_auth(200)
    capture = make_capture(auth, 200)
    transaction = build_transaction_from_operations([auth, capture])

    assert transaction is not None
    assert transaction.status == "CAPTURED"
    assert transaction.captured_amount == 200


def test_partial_capture_status():
    auth = make_auth(200)
    capture = make_capture(auth, 50)
    transaction = build_transaction_from_operations([auth, capture])

    assert transaction is not None
    assert transaction.status == "PARTIALLY_CAPTURED"
    assert transaction.captured_amount == 50


def test_partial_refund_status():
    auth = make_auth(300)
    capture = make_capture(auth, 300)
    refund = make_refund(capture, 100)
    transaction = build_transaction_from_operations([auth, capture, refund])

    assert transaction is not None
    assert transaction.status == "PARTIALLY_REFUNDED"
    assert transaction.refunded_amount == 100


def test_full_refund_status():
    auth = make_auth(300)
    capture = make_capture(auth, 300)
    refund = make_refund(capture, 300)
    transaction = build_transaction_from_operations([auth, capture, refund])

    assert transaction is not None
    assert transaction.status == "REFUNDED"
    assert transaction.refunded_amount == 300


def test_reversal_status():
    auth = make_auth(150)
    reversal = make_reversal(auth)
    transaction = build_transaction_from_operations([auth, reversal])

    assert transaction is not None
    assert transaction.status == "CANCELLED"


def test_group_operations_includes_refund_child_of_capture():
    auth = make_auth(300)
    capture = make_capture(auth, 300)
    refund = make_refund(capture, 100)

    mapping = _group_operations_by_auth([auth, capture, refund], [auth.operation_id])

    assert auth.operation_id in mapping
    assert refund in mapping[auth.operation_id]


def test_build_transaction_from_grouped_operations_with_refund_on_capture():
    auth = make_auth(3000)
    capture = make_capture(auth, 3000)
    refund = make_refund(capture, 1000)

    mapping = _group_operations_by_auth([auth, capture, refund], [auth.operation_id])
    transaction = build_transaction_from_operations(mapping[auth.operation_id])

    assert transaction is not None
    assert transaction.status == "PARTIALLY_REFUNDED"
    assert transaction.captured_amount == 3000
    assert transaction.refunded_amount == 1000
