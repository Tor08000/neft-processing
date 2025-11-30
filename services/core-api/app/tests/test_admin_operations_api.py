from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine

from app.main import app
from app.models.operation import Operation


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as api_client:
        yield api_client


@pytest.fixture
def admin_client(admin_auth_headers: dict):
    with TestClient(app) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


def test_admin_access_control(client: TestClient, admin_token: str, user_token: str):
    missing = client.get("/api/v1/admin/operations")
    assert missing.status_code == 401
    assert missing.json() == {"detail": "Missing bearer token"}

    invalid = client.get(
        "/api/v1/admin/operations", headers={"Authorization": "Bearer garbage"}
    )
    assert invalid.status_code == 401
    assert invalid.json() == {"detail": "Invalid token"}

    forbidden = client.get(
        "/api/v1/admin/operations", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "Forbidden"}

    allowed = client.get(
        "/api/v1/admin/operations", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert allowed.status_code == 200
    assert allowed.json()["items"] == []

    allowed_tx = client.get(
        "/api/v1/admin/transactions", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert allowed_tx.status_code == 200
    assert allowed_tx.json()["items"] == []


def test_operations_filters_and_pagination(admin_client: TestClient):
    session = SessionLocal()
    try:
        base_time = datetime.utcnow()
        operations = [
            Operation(
                operation_id="op-auth",
                operation_type="AUTH",
                status="AUTHORIZED",
                merchant_id="m1",
                terminal_id="t1",
                client_id="c1",
                card_id="card-1",
                amount=100,
                currency="RUB",
                created_at=base_time,
            ),
            Operation(
                operation_id="op-cap",
                operation_type="CAPTURE",
                status="CAPTURED",
                merchant_id="m1",
                terminal_id="t1",
                client_id="c1",
                card_id="card-1",
                amount=200,
                currency="RUB",
                parent_operation_id="op-auth",
                created_at=base_time + timedelta(minutes=1),
            ),
            Operation(
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
                created_at=base_time + timedelta(minutes=2),
            ),
        ]
        session.add_all(operations)
        session.commit()
    finally:
        session.close()

    by_type = admin_client.get(
        "/api/v1/admin/operations", params={"operation_type": "REFUND"}
    )
    assert by_type.status_code == 200
    assert by_type.json()["total"] == 1
    assert by_type.json()["items"][0]["operation_id"] == "op-ref"

    by_merch = admin_client.get(
        "/api/v1/admin/operations",
        params={"merchant_id": "m1", "terminal_id": "t1"},
    )
    assert by_merch.status_code == 200
    assert by_merch.json()["total"] == 2

    date_filtered = admin_client.get(
        "/api/v1/admin/operations",
        params={
            "from_created_at": (base_time + timedelta(minutes=1, seconds=30)).isoformat(),
            "to_created_at": (base_time + timedelta(minutes=3)).isoformat(),
        },
    )
    assert date_filtered.status_code == 200
    assert date_filtered.json()["total"] == 1
    assert date_filtered.json()["items"][0]["operation_id"] == "op-ref"

    by_amount = admin_client.get(
        "/api/v1/admin/operations", params={"min_amount": 150, "max_amount": 250}
    )
    assert by_amount.status_code == 200
    assert by_amount.json()["total"] == 1
    assert by_amount.json()["items"][0]["operation_id"] == "op-cap"

    first_page = admin_client.get(
        "/api/v1/admin/operations", params={"limit": 1, "offset": 0}
    )
    assert first_page.status_code == 200
    assert first_page.json()["limit"] == 1
    assert first_page.json()["total"] == 3

    second_page = admin_client.get(
        "/api/v1/admin/operations", params={"limit": 1, "offset": 1}
    )
    assert second_page.status_code == 200
    assert second_page.json()["limit"] == 1
    assert second_page.json()["total"] == 3
    assert second_page.json()["items"][0]["operation_id"] != first_page.json()["items"][0]["operation_id"]


def test_operations_sorting(admin_client: TestClient):
    session = SessionLocal()
    try:
        earlier = datetime.utcnow()
        later = earlier + timedelta(minutes=5)
        session.add_all(
            [
                Operation(
                    operation_id="op-a",
                    operation_type="AUTH",
                    status="AUTHORIZED",
                    merchant_id="m1",
                    terminal_id="t1",
                    client_id="c1",
                    card_id="card-1",
                    amount=100,
                    currency="RUB",
                    created_at=later,
                ),
                Operation(
                    operation_id="op-b",
                    operation_type="AUTH",
                    status="AUTHORIZED",
                    merchant_id="m2",
                    terminal_id="t2",
                    client_id="c2",
                    card_id="card-2",
                    amount=200,
                    currency="RUB",
                    created_at=earlier,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    asc = admin_client.get(
        "/api/v1/admin/operations", params={"order_by": "created_at_asc"}
    )
    assert asc.status_code == 200
    assert [item["operation_id"] for item in asc.json()["items"]] == ["op-b", "op-a"]

    desc = admin_client.get(
        "/api/v1/admin/operations", params={"order_by": "created_at_desc"}
    )
    assert desc.status_code == 200
    assert [item["operation_id"] for item in desc.json()["items"]] == ["op-a", "op-b"]

    amount_desc = admin_client.get(
        "/api/v1/admin/operations", params={"order_by": "amount_desc"}
    )
    assert amount_desc.status_code == 200
    assert [item["operation_id"] for item in amount_desc.json()["items"]] == [
        "op-b",
        "op-a",
    ]


def test_transactions_filters_sort_and_pagination(admin_client: TestClient):
    session = SessionLocal()
    try:
        base_time = datetime.utcnow()
        auth1 = Operation(
            operation_id="auth-1",
            operation_type="AUTH",
            status="AUTHORIZED",
            merchant_id="m1",
            terminal_id="t1",
            client_id="c1",
            card_id="card-1",
            amount=200,
            currency="RUB",
            created_at=base_time,
        )
        capture1 = Operation(
            operation_id="cap-1",
            operation_type="CAPTURE",
            status="CAPTURED",
            merchant_id="m1",
            terminal_id="t1",
            client_id="c1",
            card_id="card-1",
            amount=200,
            currency="RUB",
            parent_operation_id="auth-1",
            created_at=base_time + timedelta(minutes=1),
        )
        refund1 = Operation(
            operation_id="ref-1",
            operation_type="REFUND",
            status="REFUNDED",
            merchant_id="m1",
            terminal_id="t1",
            client_id="c1",
            card_id="card-1",
            amount=50,
            currency="RUB",
            parent_operation_id="cap-1",
            created_at=base_time + timedelta(minutes=2),
        )
        auth2 = Operation(
            operation_id="auth-2",
            operation_type="AUTH",
            status="AUTHORIZED",
            merchant_id="m2",
            terminal_id="t2",
            client_id="c2",
            card_id="card-2",
            amount=100,
            currency="RUB",
            created_at=base_time + timedelta(minutes=3),
        )
        refund2 = Operation(
            operation_id="ref-2",
            operation_type="REFUND",
            status="REFUNDED",
            merchant_id="m2",
            terminal_id="t2",
            client_id="c2",
            card_id="card-2",
            amount=100,
            currency="RUB",
            parent_operation_id="auth-2",
            created_at=base_time + timedelta(minutes=4),
        )
        session.add_all([auth1, capture1, refund1, auth2, refund2])
        session.commit()
    finally:
        session.close()

    all_tx = admin_client.get("/api/v1/admin/transactions")
    assert all_tx.status_code == 200
    assert all_tx.json()["total"] == 2

    by_client = admin_client.get(
        "/api/v1/admin/transactions", params={"client_id": "c1"}
    )
    assert by_client.status_code == 200
    assert by_client.json()["total"] == 1
    assert by_client.json()["items"][0]["transaction_id"] == "auth-1"

    refunded = admin_client.get(
        "/api/v1/admin/transactions",
        params={"transaction_status": "REFUNDED"},
    )
    assert refunded.status_code == 200
    assert refunded.json()["total"] == 1
    assert refunded.json()["items"][0]["transaction_id"] == "auth-2"

    amount_filtered = admin_client.get(
        "/api/v1/admin/transactions", params={"min_amount": 150}
    )
    assert amount_filtered.status_code == 200
    assert amount_filtered.json()["total"] == 1
    assert amount_filtered.json()["items"][0]["transaction_id"] == "auth-1"

    amount_sorted = admin_client.get(
        "/api/v1/admin/transactions", params={"order_by": "amount_asc"}
    )
    assert amount_sorted.status_code == 200
    assert [item["transaction_id"] for item in amount_sorted.json()["items"]] == [
        "auth-2",
        "auth-1",
    ]

    paginated = admin_client.get(
        "/api/v1/admin/transactions", params={"limit": 1, "offset": 1}
    )
    assert paginated.status_code == 200
    assert paginated.json()["limit"] == 1
    assert paginated.json()["total"] == 2
    assert len(paginated.json()["items"]) == 1
