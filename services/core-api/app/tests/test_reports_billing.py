from datetime import datetime, timedelta
from typing import Iterable
from app.services.reports import aggregate_transactions_for_turnover
from app.services.transactions import build_transaction_from_operations
from app.tests.test_transactions_service import (
    DummyOperation,
    make_auth,
    make_capture,
    make_refund,
    make_reversal,
)


def _build_transaction(operations: Iterable[DummyOperation]):
    transaction = build_transaction_from_operations(list(operations))
    assert transaction is not None
    return transaction


def test_turnover_aggregation_partial_refund():
    base_time = datetime.now()

    auth1 = make_auth(3000, created_at=base_time)
    capture1 = make_capture(auth1, 3000)
    refund1 = make_refund(capture1, 1000)
    tx1 = _build_transaction([auth1, capture1, refund1])

    auth2 = make_auth(2000, created_at=base_time + timedelta(minutes=5))
    capture2 = make_capture(auth2, 2000)
    tx2 = _build_transaction([auth2, capture2])

    report = aggregate_transactions_for_turnover(
        [tx1, tx2],
        group_by="client",
        from_created_at=base_time,
        to_created_at=base_time + timedelta(hours=1),
    )

    assert len(report.items) == 1
    item = report.items[0]
    assert item.transaction_count == 2
    assert item.authorized_amount == 5000
    assert item.captured_amount == 5000
    assert item.refunded_amount == 1000
    assert item.net_turnover == 4000
    assert report.totals.net_turnover == 4000


def test_turnover_excludes_cancelled_transactions():
    base_time = datetime.now()

    auth_cancelled = make_auth(1000, created_at=base_time)
    reversal = make_reversal(auth_cancelled)
    cancelled_tx = _build_transaction([auth_cancelled, reversal])

    active_auth = make_auth(500, created_at=base_time + timedelta(minutes=2))
    active_tx = _build_transaction([active_auth])

    report = aggregate_transactions_for_turnover(
        [cancelled_tx, active_tx],
        group_by="client",
        from_created_at=base_time,
        to_created_at=base_time + timedelta(hours=1),
    )

    assert len(report.items) == 1
    item = report.items[0]
    assert item.transaction_count == 1
    assert item.authorized_amount == active_tx.authorized_amount
    assert item.captured_amount == active_tx.captured_amount
    assert item.refunded_amount == active_tx.refunded_amount
    assert item.net_turnover == active_tx.captured_amount - active_tx.refunded_amount


def test_turnover_group_by_station_splits_by_terminal():
    base_time = datetime.now()

    auth1 = make_auth(1000, created_at=base_time)
    capture1 = make_capture(auth1, 1000)
    tx1 = _build_transaction([auth1, capture1])

    auth2 = make_auth(1500, created_at=base_time + timedelta(minutes=3))
    auth2.merchant_id = auth1.merchant_id
    auth2.terminal_id = "t2"
    capture2 = make_capture(auth2, 1500)
    capture2.merchant_id = auth1.merchant_id
    capture2.terminal_id = "t2"
    tx2 = _build_transaction([auth2, capture2])

    report = aggregate_transactions_for_turnover(
        [tx1, tx2],
        group_by="station",
        from_created_at=base_time,
        to_created_at=base_time + timedelta(hours=1),
    )

    assert len(report.items) == 2
    items_by_terminal = {item.group_key.terminal_id: item for item in report.items}

    assert set(items_by_terminal.keys()) == {"t1", "t2"}
    assert items_by_terminal["t1"].net_turnover == tx1.captured_amount - tx1.refunded_amount
    assert items_by_terminal["t2"].net_turnover == tx2.captured_amount - tx2.refunded_amount
