import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.account import AccountType
from app.models.card import Card
from app.models.client import Client
from app.models.contract_limits import LimitConfig, LimitScope, LimitType, LimitWindow
from app.models.operation import Operation, OperationStatus, OperationType, RiskResult
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.ledger_repository import LedgerRepository
from app.models.ledger_entry import LedgerDirection


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_clients(session, client_id, other_client_id):
    session.add(
        Client(
            id=client_id,
            name="Client One",
            inn="7700",
            tariff_plan="STANDARD",
            account_manager="Manager",
            status="ACTIVE",
        )
    )
    session.add(Client(id=other_client_id, name="Client Two", status="ACTIVE"))
    session.add(Card(id="card-1", client_id=str(client_id), status="ACTIVE", pan_masked="1111"))
    session.add(Card(id="card-2", client_id=str(other_client_id), status="ACTIVE", pan_masked="2222"))
    session.add(
        LimitConfig(
            scope=LimitScope.CARD,
            subject_ref="card-1",
            limit_type=LimitType.DAILY_AMOUNT,
            value=1000,
            window=LimitWindow.DAY,
            enabled=True,
        )
    )
    session.commit()


def test_client_profile_and_cards_filtered_by_client(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        profile = api_client.get("/api/v1/client/me")
        assert profile.status_code == 200
        body = profile.json()
        assert body["id"] == str(client_id)
        assert body["inn"] == "7700"
        assert body["tariff_plan"] == "STANDARD"

        cards = api_client.get("/api/v1/client/cards").json()
        assert len(cards["items"]) == 1
        assert cards["items"][0]["id"] == "card-1"
        assert cards["items"][0]["limits"][0]["type"] == "DAILY_AMOUNT"

        other_card = api_client.get("/api/v1/client/cards/card-2")
        assert other_card.status_code == 404


def test_client_operations_and_rbac(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)
    db_session.add(
        Operation(
            operation_id="op-1",
            operation_type=OperationType.AUTH,
            status=OperationStatus.APPROVED,
            merchant_id="m1",
            terminal_id="t1",
            client_id=str(client_id),
            card_id="card-1",
            amount=100,
            currency="RUB",
        )
    )
    db_session.add(
        Operation(
            operation_id="op-2",
            operation_type=OperationType.AUTH,
            status=OperationStatus.APPROVED,
            merchant_id="m2",
            terminal_id="t2",
            client_id=str(other_client_id),
            card_id="card-2",
            amount=200,
            currency="RUB",
        )
    )
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        ops = api_client.get("/api/v1/client/operations").json()
        assert ops["total"] == 1
        assert ops["items"][0]["id"] == "op-1"

        details = api_client.get("/api/v1/client/operations/op-1")
        assert details.status_code == 200
        assert details.json()["id"] == "op-1"

        foreign = api_client.get("/api/v1/client/operations/op-2")
        assert foreign.status_code == 404

        # Client roles should not access admin endpoints
        from app.api.dependencies.admin import require_admin_user
        from app import services

        app.dependency_overrides[require_admin_user] = services.admin_auth.require_admin
        client_token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
        admin_resp = api_client.get(
            "/api/v1/admin/merchants",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert admin_resp.status_code == 403

        # Missing client_id in token must be rejected
        bad_token = make_jwt(roles=("CLIENT_USER",))
        resp = api_client.get(
            "/api/v1/client/cards",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 403


def test_balances_and_statements(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)
    repo = AccountsRepository(db_session)
    ledger = LedgerRepository(db_session)

    account = repo.get_or_create_account(
        client_id=str(client_id),
        currency="RUB",
        account_type=AccountType.CLIENT_MAIN,
    )
    ledger.post_entry(
        account_id=account.id,
        operation_id=None,
        direction=LedgerDirection.CREDIT,
        amount=500,
        currency="RUB",
        posted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    ledger.post_entry(
        account_id=account.id,
        operation_id=None,
        direction=LedgerDirection.DEBIT,
        amount=100,
        currency="RUB",
        posted_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        balances = api_client.get("/api/v1/client/balances").json()
        assert len(balances["items"]) == 1
        assert float(balances["items"][0]["current"]) == 400

        statement = api_client.get(
            "/api/v1/client/statements",
            params={
                "from": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
                "to": datetime(2024, 1, 3, tzinfo=timezone.utc).isoformat(),
            },
        )
        assert statement.status_code == 200
        data = statement.json()[0]
        assert data["start_balance"] == "0"
        assert data["credits"] in ("500", "500.0000")
        assert data["debits"] in ("100", "100.0000")
        assert data["end_balance"] in ("400", "400.0000")


def test_client_operations_response_is_sanitized(db_session, make_jwt):
    client_id = uuid4()
    other_client_id = uuid4()
    _seed_clients(db_session, client_id, other_client_id)

    db_session.add(
        Operation(
            operation_id="op-3",
            operation_type=OperationType.AUTH,
            status=OperationStatus.DECLINED,
            merchant_id="m3",
            terminal_id="t3",
            client_id=str(client_id),
            card_id="card-1",
            amount=300,
            currency="RUB",
            reason="AI_RISK_DECLINE_INTERNAL",
            risk_result=RiskResult.HIGH,
            limit_profile_id="lp-1",
            quantity=Decimal("42"),
        )
    )
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id=str(client_id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        ops = api_client.get("/api/v1/client/operations").json()
        payload = ops["items"][0]
        assert "limit_profile_id" not in payload
        assert "risk_result" not in payload
        assert payload["reason"] == "Операция отклонена службой безопасности"
        assert Decimal(str(payload["quantity"])) == Decimal("42")

        details = api_client.get("/api/v1/client/operations/op-3").json()
        assert "limit_profile_id" not in details
        assert "risk_result" not in details
        assert details["reason"] == "Операция отклонена службой безопасности"
