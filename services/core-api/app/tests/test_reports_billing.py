from datetime import datetime, timedelta
from typing import Iterable

from app.schemas.transactions import TransactionsPage
from app.services.reports import aggregate_transactions_for_turnover, get_turnover_report
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


def test_turnover_group_by_fuel_category():
    base_time = datetime.now()

    auth1 = make_auth(3000, created_at=base_time)
    auth1.product_category = "DIESEL"
    capture1 = make_capture(auth1, 3000)
    tx1 = _build_transaction([auth1, capture1])

    auth2 = make_auth(2000, created_at=base_time + timedelta(minutes=2))
    auth2.product_category = "GASOLINE_95"
    capture2 = make_capture(auth2, 2000)
    tx2 = _build_transaction([auth2, capture2])

    report = aggregate_transactions_for_turnover(
        [tx1, tx2],
        group_by="fuel_category",
        from_created_at=base_time,
        to_created_at=base_time + timedelta(hours=1),
    )

    assert len(report.items) == 2
    items_by_category = {
        item.group_key.product_category: item for item in report.items
    }
    assert items_by_category["DIESEL"].net_turnover == 3000
    assert items_by_category["GASOLINE_95"].net_turnover == 2000
    assert report.totals.net_turnover == 5000


def test_turnover_filter_by_product_category(monkeypatch):
    base_time = datetime.now()

    auth1 = make_auth(3000, created_at=base_time)
    auth1.product_category = "DIESEL"
    capture1 = make_capture(auth1, 3000)
    tx1 = _build_transaction([auth1, capture1])

    auth2 = make_auth(2000, created_at=base_time + timedelta(minutes=2))
    auth2.product_category = "GASOLINE_95"
    capture2 = make_capture(auth2, 2000)
    tx2 = _build_transaction([auth2, capture2])

    def _stub_list_transactions(*args, **kwargs):
        return TransactionsPage(items=[tx1, tx2], total=2, limit=2, offset=0)

    monkeypatch.setattr("app.services.reports.list_transactions", _stub_list_transactions)

    report = get_turnover_report(
        db=None,  # db is not used by stub
        group_by="fuel_category",
        from_created_at=base_time,
        to_created_at=base_time + timedelta(hours=1),
        product_category="DIESEL",
    )

    assert len(report.items) == 1
    item = report.items[0]
    assert item.group_key.product_category == "DIESEL"
    assert item.net_turnover == 3000
    assert report.totals.net_turnover == 3000


def test_turnover_group_by_mcc():
    base_time = datetime.now()

    auth1 = make_auth(1500, created_at=base_time)
    auth1.mcc = "5541"
    capture1 = make_capture(auth1, 1500)
    tx1 = _build_transaction([auth1, capture1])

    auth2 = make_auth(2500, created_at=base_time + timedelta(minutes=3))
    auth2.mcc = "5542"
    capture2 = make_capture(auth2, 2500)
    tx2 = _build_transaction([auth2, capture2])

    report = aggregate_transactions_for_turnover(
        [tx1, tx2],
        group_by="mcc",
        from_created_at=base_time,
        to_created_at=base_time + timedelta(hours=1),
    )

    assert len(report.items) == 2
    items_by_mcc = {item.group_key.mcc: item for item in report.items}
    assert items_by_mcc["5541"].net_turnover == 1500
    assert items_by_mcc["5542"].net_turnover == 2500
    assert report.totals.net_turnover == 4000


def test_turnover_group_by_tx_type_and_filter(monkeypatch):
    base_time = datetime.now()

    auth1 = make_auth(1200, created_at=base_time)
    auth1.product_category = "DIESEL"
    capture1 = make_capture(auth1, 1200)
    tx1 = _build_transaction([auth1, capture1])

    auth2 = make_auth(800, created_at=base_time + timedelta(minutes=4))
    auth2.product_category = "SERVICE"
    capture2 = make_capture(auth2, 800)
    tx2 = _build_transaction([auth2, capture2])

    def _stub_list_transactions(*args, **kwargs):
        return TransactionsPage(items=[tx1, tx2], total=2, limit=2, offset=0)

    monkeypatch.setattr("app.services.reports.list_transactions", _stub_list_transactions)

    report = get_turnover_report(
        db=None,
        group_by="tx_type",
        from_created_at=base_time,
        to_created_at=base_time + timedelta(hours=1),
    )

    assert len(report.items) == 2
    items_by_type = {item.group_key.tx_type: item for item in report.items}
    assert items_by_type["FUEL"].net_turnover == 1200
    assert items_by_type["OTHER"].net_turnover == 800

    filtered_report = get_turnover_report(
        db=None,
        group_by="tx_type",
        from_created_at=base_time,
        to_created_at=base_time + timedelta(hours=1),
        tx_type="FUEL",
    )

    assert len(filtered_report.items) == 1
    assert filtered_report.items[0].group_key.tx_type == "FUEL"
    assert filtered_report.totals.net_turnover == 1200
