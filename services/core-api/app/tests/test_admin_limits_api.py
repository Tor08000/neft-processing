import os

import pytest
from fastapi.testclient import TestClient


os.environ["NEFT_DB_URL"] = "sqlite+pysqlite:///:memory:"

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.limits import CheckAndReserveRequest, evaluate_limits_locally  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_create_limit_rule_and_list_with_filter(client: TestClient):
    payload = {
        "phase": "AUTH",
        "client_id": "C1",
        "daily_limit": 1_000,
        "limit_per_tx": 500,
    }
    resp = client.post("/api/v1/admin/limits/rules", json=payload)
    assert resp.status_code == 201

    list_resp = client.get("/api/v1/admin/limits/rules", params={"client_id": "C1"})
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    assert data["items"][0]["client_id"] == "C1"


def test_update_limit_rule(client: TestClient):
    payload = {
        "phase": "AUTH",
        "client_id": "C2",
        "daily_limit": 2_000,
        "limit_per_tx": 600,
    }
    created = client.post("/api/v1/admin/limits/rules", json=payload).json()

    update_resp = client.put(
        f"/api/v1/admin/limits/rules/{created['id']}",
        json={"active": False, "limit_per_tx": 700},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["active"] is False
    assert updated["limit_per_tx"] == 700


def test_delete_limit_rule_soft_and_hard(client: TestClient):
    payload = {
        "phase": "AUTH",
        "client_id": "C3",
        "daily_limit": 3_000,
        "limit_per_tx": 800,
    }
    created = client.post("/api/v1/admin/limits/rules", json=payload).json()

    soft_resp = client.delete(f"/api/v1/admin/limits/rules/{created['id']}")
    assert soft_resp.status_code == 200
    assert soft_resp.json()["active"] is False

    hard_resp = client.delete(
        f"/api/v1/admin/limits/rules/{created['id']}", params={"force": True}
    )
    assert hard_resp.status_code == 200

    list_resp = client.get("/api/v1/admin/limits/rules", params={"client_id": "C3"})
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 0


def test_client_group_crud_and_membership(client: TestClient):
    create_resp = client.post(
        "/api/v1/admin/client-groups",
        json={"group_id": "VIP", "name": "VIP", "description": "vip"},
    )
    assert create_resp.status_code == 201

    member1 = client.post(
        "/api/v1/admin/client-groups/VIP/members", json={"client_id": "c1"}
    )
    member2 = client.post(
        "/api/v1/admin/client-groups/VIP/members", json={"client_id": "c2"}
    )
    assert member1.status_code == 201
    assert member2.status_code == 201

    members = client.get("/api/v1/admin/client-groups/VIP/members")
    assert members.status_code == 200
    assert len(members.json()) == 2

    delete_resp = client.delete("/api/v1/admin/client-groups/VIP/members/c1")
    assert delete_resp.status_code == 204

    members_after = client.get("/api/v1/admin/client-groups/VIP/members")
    assert members_after.status_code == 200
    assert len(members_after.json()) == 1


def test_card_group_crud(client: TestClient):
    create_resp = client.post(
        "/api/v1/admin/card-groups",
        json={"group_id": "CARD-VIP", "name": "Cards", "description": "cards"},
    )
    assert create_resp.status_code == 201

    member_resp = client.post(
        "/api/v1/admin/card-groups/CARD-VIP/members", json={"card_id": "card-1"}
    )
    assert member_resp.status_code == 201

    members = client.get("/api/v1/admin/card-groups/CARD-VIP/members")
    assert members.status_code == 200
    assert len(members.json()) == 1

    delete_resp = client.delete("/api/v1/admin/card-groups/CARD-VIP/members/card-1")
    assert delete_resp.status_code == 204

    members_after = client.get("/api/v1/admin/card-groups/CARD-VIP/members")
    assert members_after.status_code == 200
    assert len(members_after.json()) == 0


def test_limits_engine_works_with_created_rules(client: TestClient):
    payload = {
        "phase": "AUTH",
        "client_id": "ENG-CLIENT",
        "card_id": "ENG-CARD",
        "daily_limit": 1_000,
        "limit_per_tx": 200,
    }
    create_resp = client.post("/api/v1/admin/limits/rules", json=payload)
    assert create_resp.status_code == 201

    req = CheckAndReserveRequest(
        merchant_id="M-1",
        terminal_id="T-1",
        client_id="ENG-CLIENT",
        card_id="ENG-CARD",
        amount=150,
    )

    result = evaluate_limits_locally(req)
    assert result.approved is True
    assert result.limit_per_tx == 200
    assert result.daily_limit == 1_000
