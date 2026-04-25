from datetime import datetime, timezone

import pytest
from app.models.account import AccountType
from app.models.ledger_entry import LedgerDirection
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.ledger_repository import LedgerRepository
from ._money_router_harness import ACCOUNT_LEDGER_TEST_TABLES, admin_accounts_client_context, money_session_context

CLIENT_ID = "11111111-1111-1111-1111-111111111111"

@pytest.fixture
def session():
    with money_session_context(tables=ACCOUNT_LEDGER_TEST_TABLES) as db:
        yield db


@pytest.fixture
def client(session):
    with admin_accounts_client_context(db_session=session) as api_client:
        yield api_client


def test_list_accounts_returns_balances(client, session):
    repo = AccountsRepository(session)
    account = repo.get_or_create_account(client_id=CLIENT_ID, currency="RUB", account_type=AccountType.CLIENT_MAIN)
    LedgerRepository(session).post_entry(
        account_id=account.id,
        operation_id=None,
        direction=LedgerDirection.CREDIT,
        amount=500,
        currency="RUB",
    )

    response = client.get("/api/v1/admin/accounts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert float(payload["items"][0]["balance"]) == 500.0


def test_statement_endpoint(client, session):
    repo = AccountsRepository(session)
    ledger = LedgerRepository(session)
    account = repo.get_or_create_account(client_id=CLIENT_ID, currency="RUB", account_type=AccountType.CLIENT_MAIN)
    entry = ledger.post_entry(
        account_id=account.id,
        operation_id=None,
        direction=LedgerDirection.DEBIT,
        amount=100,
        currency="RUB",
        posted_at=datetime.now(timezone.utc),
    )

    response = client.get(f"/api/v1/admin/accounts/{account.id}/statement")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == account.id
    assert len(data["entries"]) == 1
    assert data["entries"][0]["id"] == entry.id


def test_client_balance_aggregation(client, session):
    repo = AccountsRepository(session)
    ledger = LedgerRepository(session)
    a1 = repo.get_or_create_account(client_id=CLIENT_ID, currency="RUB", account_type=AccountType.CLIENT_MAIN)
    a2 = repo.get_or_create_account(client_id=CLIENT_ID, currency="USD", account_type=AccountType.CLIENT_MAIN)
    ledger.post_entry(account_id=a1.id, operation_id=None, direction=LedgerDirection.CREDIT, amount=200, currency="RUB")
    ledger.post_entry(account_id=a2.id, operation_id=None, direction=LedgerDirection.CREDIT, amount=300, currency="USD")

    response = client.get(f"/api/v1/admin/clients/{CLIENT_ID}/balances")
    assert response.status_code == 200
    balances = response.json()
    assert len(balances) == 2
    assert {b["currency"] for b in balances} == {"RUB", "USD"}
