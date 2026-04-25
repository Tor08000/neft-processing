from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.account import AccountType
from app.models.ledger_entry import LedgerDirection
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.ledger_repository import LedgerRepository
from app.services.posting_engine import (
    PostingContext,
    PostingEngine,
    PostingOperationType,
    REVENUE_TARIFF_ID,
    SETTLEMENT_TARIFF_ID,
    TECHNICAL_CLIENT_ID,
)
from ._money_router_harness import ACCOUNT_LEDGER_TEST_TABLES, money_session_context


@pytest.fixture
def session():
    with money_session_context(tables=ACCOUNT_LEDGER_TEST_TABLES) as db:
        yield db


@pytest.fixture
def accounts_repo(session):
    return AccountsRepository(session)


@pytest.fixture
def ledger_repo(session):
    return LedgerRepository(session)


@pytest.fixture
def posting_engine(accounts_repo, ledger_repo):
    return PostingEngine(accounts_repo, ledger_repo)


def test_fuel_purchase_posting_creates_expected_entries(
    posting_engine: PostingEngine, accounts_repo: AccountsRepository
):
    context = PostingContext(
        client_id="11111111-1111-1111-1111-111111111123",
        card_id="card-1",
        amount=Decimal("150.50"),
        currency="RUB",
        operation_id=None,
    )

    result = posting_engine.post(PostingOperationType.FUEL_PURCHASE, context)

    assert len(result.entries) == 2
    assert [entry.direction for entry in result.entries] == [
        LedgerDirection.DEBIT,
        LedgerDirection.CREDIT,
    ]

    client_account = accounts_repo.get_or_create_account(
        client_id=context.client_id,
        card_id=context.card_id,
        currency=context.currency,
        account_type=AccountType.CLIENT_MAIN,
    )
    revenue_account = accounts_repo.get_or_create_account(
        client_id=TECHNICAL_CLIENT_ID,
        card_id=None,
        currency=context.currency,
        account_type=AccountType.TECHNICAL,
        tariff_id=REVENUE_TARIFF_ID,
    )

    assert result.balances[client_account.id] == Decimal("-150.50")
    assert result.balances[revenue_account.id] == Decimal("150.50")


def test_topup_and_refund_update_balances(
    posting_engine: PostingEngine, accounts_repo: AccountsRepository
):
    topup_context = PostingContext(
        client_id="22222222-2222-2222-2222-222222222222",
        card_id=None,
        amount=Decimal("200.00"),
        currency="USD",
        operation_id=None,
    )
    topup_result = posting_engine.post(PostingOperationType.TOPUP, topup_context)

    client_account = accounts_repo.get_or_create_account(
        client_id=topup_context.client_id,
        card_id=None,
        currency=topup_context.currency,
        account_type=AccountType.CLIENT_MAIN,
    )
    settlement_account = accounts_repo.get_or_create_account(
        client_id=TECHNICAL_CLIENT_ID,
        card_id=None,
        currency=topup_context.currency,
        account_type=AccountType.TECHNICAL,
        tariff_id=SETTLEMENT_TARIFF_ID,
    )

    assert topup_result.balances[client_account.id] == Decimal("200.00")
    assert topup_result.balances[settlement_account.id] == Decimal("-200.00")

    refund_context = PostingContext(
        client_id=topup_context.client_id,
        card_id=None,
        amount=Decimal("50.00"),
        currency=topup_context.currency,
        operation_id=None,
    )
    posting_engine.post(PostingOperationType.REFUND, refund_context)

    client_balance = accounts_repo.get_balance(client_account.id)
    revenue_account = accounts_repo.get_or_create_account(
        client_id=TECHNICAL_CLIENT_ID,
        card_id=None,
        currency=topup_context.currency,
        account_type=AccountType.TECHNICAL,
        tariff_id=REVENUE_TARIFF_ID,
    )
    revenue_balance = accounts_repo.get_balance(revenue_account.id)

    assert Decimal(client_balance.current_balance) == Decimal("250.00")
    assert Decimal(revenue_balance.current_balance) == Decimal("-50.00")


def test_posting_separates_accounts_by_currency(
    posting_engine: PostingEngine, accounts_repo: AccountsRepository
):
    rub_context = PostingContext(
        client_id="33333333-3333-3333-3333-333333333333",
        card_id="card-multi",
        amount=Decimal("100.00"),
        currency="RUB",
        operation_id=None,
    )
    usd_context = PostingContext(
        client_id="33333333-3333-3333-3333-333333333333",
        card_id="card-multi",
        amount=Decimal("75.00"),
        currency="USD",
        operation_id=None,
    )

    posting_engine.post(PostingOperationType.FUEL_PURCHASE, rub_context)
    posting_engine.post(PostingOperationType.FUEL_PURCHASE, usd_context)

    rub_account = accounts_repo.get_or_create_account(
        client_id=rub_context.client_id,
        card_id=rub_context.card_id,
        currency="RUB",
        account_type=AccountType.CLIENT_MAIN,
    )
    usd_account = accounts_repo.get_or_create_account(
        client_id=usd_context.client_id,
        card_id=usd_context.card_id,
        currency="USD",
        account_type=AccountType.CLIENT_MAIN,
    )

    assert rub_account.id != usd_account.id
    assert Decimal(accounts_repo.get_balance(rub_account.id).current_balance) == Decimal(
        "-100.00"
    )
    assert Decimal(accounts_repo.get_balance(usd_account.id).current_balance) == Decimal(
        "-75.00"
    )
