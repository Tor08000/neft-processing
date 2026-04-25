from decimal import Decimal

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.account import Account, AccountOwnerType, AccountType
from app.models.ledger_entry import LedgerDirection, LedgerEntry
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.posting_batch import PostingBatchType
from app.services.ledger.balance_service import BalanceService
from app.services.ledger.posting_engine import PostingEngine, PostingInvariantError, PostingLine

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

ACCOUNT_A_CLIENT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ACCOUNT_B_CLIENT_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ACCOUNT_RUB_CLIENT_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
ACCOUNT_USD_CLIENT_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"

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


def _make_account(db, *, owner_id: str, currency: str = "RUB") -> Account:
    account = Account(
        client_id=owner_id,
        owner_type=AccountOwnerType.CLIENT,
        owner_id="11111111-1111-1111-1111-111111111111",
        currency=currency,
        type=AccountType.CLIENT_MAIN,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _make_operation(db) -> Operation:
    op = Operation(
        operation_id="cap-1",
        operation_type=OperationType.CAPTURE,
        status=OperationStatus.CAPTURED,
        merchant_id="22222222-2222-2222-2222-222222222222",
        terminal_id="t-1",
        client_id="33333333-3333-3333-3333-333333333333",
        card_id="card-1",
        amount=100,
        currency="RUB",
        captured_amount=100,
        refunded_amount=0,
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return op


def test_ledger_double_entry_and_balances(session):
    acc_a = _make_account(session, owner_id=ACCOUNT_A_CLIENT_ID)
    acc_b = _make_account(session, owner_id=ACCOUNT_B_CLIENT_ID)
    operation = _make_operation(session)

    result = PostingEngine(session).apply_posting(
        operation_id=operation.id,
        posting_type=PostingBatchType.CAPTURE,
        idempotency_key="ledger-basic-1",
        lines=[
            PostingLine(account_id=acc_a.id, direction=LedgerDirection.DEBIT, amount=Decimal("100"), currency="RUB"),
            PostingLine(account_id=acc_b.id, direction=LedgerDirection.CREDIT, amount=Decimal("100"), currency="RUB"),
        ],
    )

    assert len(result.entries) == 2
    debit = sum(e.amount for e in result.entries if e.direction == LedgerDirection.DEBIT)
    credit = sum(e.amount for e in result.entries if e.direction == LedgerDirection.CREDIT)
    assert debit == credit == Decimal("100")

    balances = BalanceService(session).snapshot_balances([acc_a.id, acc_b.id])
    assert balances[acc_a.id]["current"] == Decimal("-100")
    assert balances[acc_b.id]["current"] == Decimal("100")


def test_ledger_entries_are_append_only(session):
    acc_a = _make_account(session, owner_id=ACCOUNT_A_CLIENT_ID)
    acc_b = _make_account(session, owner_id=ACCOUNT_B_CLIENT_ID)
    operation = _make_operation(session)
    PostingEngine(session).apply_posting(
        operation_id=operation.id,
        posting_type=PostingBatchType.CAPTURE,
        idempotency_key="ledger-mutation-1",
        lines=[
            PostingLine(account_id=acc_a.id, direction=LedgerDirection.DEBIT, amount=Decimal("10"), currency="RUB"),
            PostingLine(account_id=acc_b.id, direction=LedgerDirection.CREDIT, amount=Decimal("10"), currency="RUB"),
        ],
    )
    entry = session.query(LedgerEntry).first()

    entry.amount = Decimal("11")
    with pytest.raises(ValueError, match="append_only"):
        session.commit()
    session.rollback()


def test_currency_mismatch_rejected(session):
    acc_rub = _make_account(session, owner_id=ACCOUNT_RUB_CLIENT_ID, currency="RUB")
    acc_usd = _make_account(session, owner_id=ACCOUNT_USD_CLIENT_ID, currency="USD")
    operation = _make_operation(session)

    with pytest.raises(PostingInvariantError, match="ledger.currency_match"):
        PostingEngine(session).apply_posting(
            operation_id=operation.id,
            posting_type=PostingBatchType.CAPTURE,
            idempotency_key="ledger-currency-mismatch",
            lines=[
                PostingLine(account_id=acc_rub.id, direction=LedgerDirection.DEBIT, amount=Decimal("100"), currency="RUB"),
                PostingLine(account_id=acc_usd.id, direction=LedgerDirection.CREDIT, amount=Decimal("100"), currency="RUB"),
            ],
        )


def test_rounding_edge_minor_unit_supported(session):
    acc_a = _make_account(session, owner_id=ACCOUNT_A_CLIENT_ID)
    acc_b = _make_account(session, owner_id=ACCOUNT_B_CLIENT_ID)
    operation = _make_operation(session)

    result = PostingEngine(session).apply_posting(
        operation_id=operation.id,
        posting_type=PostingBatchType.CAPTURE,
        idempotency_key="ledger-rounding-001",
        lines=[
            PostingLine(account_id=acc_a.id, direction=LedgerDirection.DEBIT, amount=Decimal("0.01"), currency="RUB"),
            PostingLine(account_id=acc_b.id, direction=LedgerDirection.CREDIT, amount=Decimal("0.01"), currency="RUB"),
        ],
    )
    assert sum(e.amount for e in result.entries) == Decimal("0.02")
