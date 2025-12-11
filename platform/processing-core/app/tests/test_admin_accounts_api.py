from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.account import AccountType
from app.models.ledger_entry import LedgerDirection
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.ledger_repository import LedgerRepository


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_list_accounts_returns_balances(client, session, make_jwt):
    repo = AccountsRepository(session)
    account = repo.get_or_create_account(client_id="client-1", currency="RUB", account_type=AccountType.CLIENT_MAIN)
    LedgerRepository(session).post_entry(
        account_id=account.id,
        operation_id=None,
        direction=LedgerDirection.CREDIT,
        amount=500,
        currency="RUB",
    )

    token = make_jwt()
    response = client.get(
        "/api/v1/admin/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert float(payload["items"][0]["balance"]) == 500.0


def test_statement_endpoint(client, session, make_jwt):
    repo = AccountsRepository(session)
    ledger = LedgerRepository(session)
    account = repo.get_or_create_account(client_id="client-1", currency="RUB", account_type=AccountType.CLIENT_MAIN)
    entry = ledger.post_entry(
        account_id=account.id,
        operation_id=None,
        direction=LedgerDirection.DEBIT,
        amount=100,
        currency="RUB",
        posted_at=datetime.now(timezone.utc),
    )

    token = make_jwt()
    response = client.get(
        f"/api/v1/admin/accounts/{account.id}/statement",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == account.id
    assert len(data["entries"]) == 1
    assert data["entries"][0]["id"] == entry.id


def test_client_balance_aggregation(client, session, make_jwt):
    repo = AccountsRepository(session)
    ledger = LedgerRepository(session)
    a1 = repo.get_or_create_account(client_id="client-1", currency="RUB", account_type=AccountType.CLIENT_MAIN)
    a2 = repo.get_or_create_account(client_id="client-1", currency="USD", account_type=AccountType.CLIENT_MAIN)
    ledger.post_entry(account_id=a1.id, operation_id=None, direction=LedgerDirection.CREDIT, amount=200, currency="RUB")
    ledger.post_entry(account_id=a2.id, operation_id=None, direction=LedgerDirection.CREDIT, amount=300, currency="USD")

    token = make_jwt()
    response = client.get(
        "/api/v1/admin/clients/client-1/balances",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    balances = response.json()
    assert len(balances) == 2
    assert {b["currency"] for b in balances} == {"RUB", "USD"}
