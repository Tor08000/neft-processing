import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.models.card import Card
from app.models.client import Client
from app.models.fuel import FleetOfflineProfile, FuelStation
from app.models.operation import Operation
from app.api.dependencies.admin import require_admin_user
from app.routers.admin.dashboard import router as admin_dashboard_router
from app.routers.admin.operations import router as admin_operations_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


ADMIN_DASHBOARD_TEST_TABLES = (
    FleetOfflineProfile.__table__,
    FuelStation.__table__,
    Client.__table__,
    Card.__table__,
    Operation.__table__,
)


def _admin_dashboard_test_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin_user)])
    router.include_router(admin_dashboard_router)
    router.include_router(admin_operations_router)
    return router


@pytest.fixture
def db_session():
    with scoped_session_context(tables=ADMIN_DASHBOARD_TEST_TABLES) as session:
        yield session


@pytest.fixture
def client(db_session):
    with router_client_context(
        router=_admin_dashboard_test_router(),
        db_session=db_session,
        dependency_overrides={require_admin_user: lambda: {"roles": ["ADMIN"], "sub": "admin-1"}},
    ) as api_client:
        yield api_client


def test_admin_clients_list_and_filters(client: TestClient, db_session):
    resp = client.get("/api/v1/admin/clients")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    db_session.add_all(
        [
            Client(id=first_id, name="Alice"),
            Client(id=second_id, name="Bob"),
        ]
    )
    db_session.commit()

    all_resp = client.get("/api/v1/admin/clients")
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] == 2

    filtered = client.get("/api/v1/admin/clients", params={"client_id": str(first_id)})
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] == 1
    assert body["items"][0]["client_id"] == str(first_id)

    name_filtered = client.get("/api/v1/admin/clients", params={"name": "ali"})
    assert name_filtered.status_code == 200
    assert name_filtered.json()["total"] == 1


def test_admin_cards_list_and_filters(client: TestClient, db_session):
    now = datetime.utcnow()
    db_session.add_all(
        [
            Card(id="card-1", client_id="c1", status="ACTIVE", created_at=now),
            Card(id="card-2", client_id="c2", status="BLOCKED", created_at=now),
        ]
    )
    db_session.commit()

    all_resp = client.get("/api/v1/admin/cards")
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] == 2

    filtered = client.get("/api/v1/admin/cards", params={"client_id": "c1"})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["card_id"] == "card-1"

    filtered_card = client.get("/api/v1/admin/cards", params={"card_id": "card-2"})
    assert filtered_card.status_code == 200
    assert filtered_card.json()["total"] == 1
    assert filtered_card.json()["items"][0]["status"] == "BLOCKED"


def test_admin_operations_list_filters(client: TestClient, db_session):
    resp = client.get("/api/v1/admin/operations")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    now = datetime.utcnow()
    op1 = Operation(
        operation_id="op-auth",
        operation_type="AUTH",
        status="AUTHORIZED",
        merchant_id="m1",
        terminal_id="t1",
        client_id="c1",
        card_id="card-1",
        amount=100,
        currency="RUB",
        created_at=now,
    )
    op2 = Operation(
        operation_id="op-cap",
        operation_type="CAPTURE",
        status="CAPTURED",
        merchant_id="m1",
        terminal_id="t1",
        client_id="c1",
        card_id="card-1",
        amount=100,
        currency="RUB",
        parent_operation_id="op-auth",
        created_at=now + timedelta(minutes=1),
    )
    op3 = Operation(
        operation_id="op-ref",
        operation_type="REFUND",
        status="REFUNDED",
        merchant_id="m2",
        terminal_id="t2",
        client_id="c2",
        card_id="card-2",
        amount=50,
        currency="RUB",
        parent_operation_id="op-cap",
        created_at=now + timedelta(minutes=2),
        product_category="FUEL",
    )
    db_session.add_all([op1, op2, op3])
    db_session.commit()

    by_type = client.get("/api/v1/admin/operations", params={"operation_type": "REFUND"})
    assert by_type.status_code == 200
    assert by_type.json()["total"] == 1
    assert by_type.json()["items"][0]["operation_id"] == "op-ref"

    by_client = client.get("/api/v1/admin/operations", params={"client_id": "c1"})
    assert by_client.status_code == 200
    assert by_client.json()["total"] == 2

    by_range = client.get(
        "/api/v1/admin/operations",
        params={
            "from_created_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "client_id": "c1",
        },
    )
    assert by_range.status_code == 200
    assert by_range.json()["total"] == 0


def test_admin_transactions_filters(client: TestClient, db_session):
    base_time = datetime.utcnow()
    auth1 = Operation(
        operation_id="auth-1",
        operation_type="AUTH",
        status="AUTHORIZED",
        merchant_id="m1",
        terminal_id="t1",
        client_id="c1",
        card_id="card-1",
        amount=100,
        currency="RUB",
        created_at=base_time,
        product_category="FUEL",
        tx_type="FUEL",
    )
    capture1 = Operation(
        operation_id="cap-1",
        operation_type="CAPTURE",
        status="CAPTURED",
        merchant_id="m1",
        terminal_id="t1",
        client_id="c1",
        card_id="card-1",
        amount=100,
        currency="RUB",
        parent_operation_id="auth-1",
        created_at=base_time + timedelta(minutes=1),
        product_category="FUEL",
        tx_type="FUEL",
    )
    auth2 = Operation(
        operation_id="auth-2",
        operation_type="AUTH",
        status="AUTHORIZED",
        merchant_id="m2",
        terminal_id="t2",
        client_id="c2",
        card_id="card-2",
        amount=200,
        currency="RUB",
        created_at=base_time + timedelta(minutes=2),
        product_category="OTHER",
        tx_type="OTHER",
    )
    db_session.add_all([auth1, capture1, auth2])
    db_session.commit()

    resp = client.get("/api/v1/admin/transactions")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2

    by_client = client.get(
        "/api/v1/admin/transactions", params={"client_id": "c1", "status": "CAPTURED"}
    )
    assert by_client.status_code == 200
    assert by_client.json()["total"] == 1
    assert by_client.json()["items"][0]["transaction_id"] == "auth-1"

    by_category = client.get(
        "/api/v1/admin/transactions", params={"product_category": "OTHER"}
    )
    assert by_category.status_code == 200
    assert by_category.json()["total"] == 1
    assert by_category.json()["items"][0]["transaction_id"] == "auth-2"

    by_tx_type = client.get(
        "/api/v1/admin/transactions", params={"tx_type": "FUEL", "client_id": "c1"}
    )
    assert by_tx_type.status_code == 200
    assert by_tx_type.json()["total"] == 1
    assert by_tx_type.json()["items"][0]["transaction_id"] == "auth-1"
