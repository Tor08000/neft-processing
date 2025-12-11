from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from app.db import Base, SessionLocal, engine
from app.models.account import AccountStatus, AccountType
from app.models.ledger_entry import LedgerDirection
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.ledger_repository import LedgerRepository


@pytest.fixture(autouse=True)
def _prepare_db():
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


@pytest.fixture
def accounts_repo(session):
    return AccountsRepository(session)


@pytest.fixture
def ledger_repo(session):
    return LedgerRepository(session)


def test_migration_tables_created():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {"accounts", "ledger_entries", "account_balances"}.issubset(tables)

    account_indexes = {index["name"] for index in inspector.get_indexes("accounts")}
    assert {
        "ix_accounts_client_id",
        "ix_accounts_card_id",
        "ix_accounts_type",
        "ix_accounts_status",
    }.issubset(account_indexes)

    ledger_indexes = {index["name"] for index in inspector.get_indexes("ledger_entries")}
    assert {
        "ix_ledger_entries_account_id",
        "ix_ledger_entries_operation_id",
    }.issubset(ledger_indexes)


def test_account_crud(accounts_repo: AccountsRepository):
    account = accounts_repo.get_or_create_account(
        client_id="client-1",
        currency="RUB",
        account_type=AccountType.CLIENT_MAIN,
    )
    assert account.id is not None

    same = accounts_repo.get_or_create_account(
        client_id="client-1",
        currency="RUB",
        account_type=AccountType.CLIENT_MAIN,
    )
    assert same.id == account.id

    frozen = accounts_repo.freeze_account(account.id)
    assert frozen.status == AccountStatus.FROZEN

    closed = accounts_repo.close_account(account.id)
    assert closed.status == AccountStatus.CLOSED


def test_posting_and_balances(accounts_repo: AccountsRepository, ledger_repo: LedgerRepository):
    account = accounts_repo.get_or_create_account(
        client_id="client-2",
        currency="USD",
        account_type=AccountType.CLIENT_MAIN,
    )

    op_id = uuid4()
    first = ledger_repo.post_entry(
        account_id=account.id,
        operation_id=op_id,
        direction=LedgerDirection.CREDIT,
        amount=Decimal("100.00"),
        currency="USD",
    )
    balance = accounts_repo.get_balance(account.id)
    assert Decimal(balance.current_balance) == Decimal("100.00")
    assert Decimal(first.balance_after) == Decimal("100.00")

    later = datetime.now(timezone.utc) + timedelta(hours=1)
    second = ledger_repo.post_entry(
        account_id=account.id,
        operation_id=op_id,
        direction=LedgerDirection.DEBIT,
        amount=Decimal("40.50"),
        currency="USD",
        posted_at=later,
    )
    balance = accounts_repo.get_balance(account.id)
    assert Decimal(balance.current_balance) == Decimal("59.50")
    assert Decimal(second.balance_after) == Decimal("59.50")

    entries = ledger_repo.get_entries(account.id)
    assert [entry.id for entry in entries] == [first.id, second.id]
    assert [Decimal(entry.amount) for entry in entries] == [Decimal("100.00"), Decimal("40.50")]
