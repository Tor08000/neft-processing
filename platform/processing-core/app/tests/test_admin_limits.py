import os
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Ensure Celery is disabled for tests so the local evaluator is used
os.environ["DISABLE_CELERY"] = "1"

from app.api.dependencies.admin import require_admin_user
from app.api.v1.endpoints.admin_limits import router as admin_router
from app.models.fuel import FuelStation
from app.models.groups import CardGroup, CardGroupMember, ClientGroup, ClientGroupMember
from app.models.limit_rule import LimitRule
from app.models.operation import Operation
from app.services.limits import CheckAndReserveRequest, call_limits_check_and_reserve_sync
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


ADMIN_LIMITS_TEST_TABLES = (
    FuelStation.__table__,
    Operation.__table__,
    ClientGroup.__table__,
    ClientGroupMember.__table__,
    CardGroup.__table__,
    CardGroupMember.__table__,
    LimitRule.__table__,
)


@pytest.fixture()
def db_session() -> Session:
    with scoped_session_context(tables=ADMIN_LIMITS_TEST_TABLES) as session:
        yield session


@pytest.fixture()
def admin_client(db_session) -> Tuple[TestClient, Session]:
    with router_client_context(
        router=admin_router,
        prefix="/api/v1",
        db_session=db_session,
        dependency_overrides={require_admin_user: lambda: {"roles": ["ADMIN"], "sub": "admin-1"}},
    ) as client:
        yield client, db_session


def test_client_and_card_group_crud(admin_client: Tuple[TestClient, Session]):
    client, _ = admin_client

    cg_resp = client.post(
        "/api/v1/admin/client-groups",
        json={"group_id": "VIP", "name": "VIP", "description": "VIP clients"},
    )
    assert cg_resp.status_code == 201
    client_group = cg_resp.json()

    add_member_resp = client.post(
        f"/api/v1/admin/client-groups/{client_group['group_id']}/members",
        json={"client_id": "client-1"},
    )
    assert add_member_resp.status_code == 201

    update_resp = client.put(
        f"/api/v1/admin/client-groups/{client_group['group_id']}",
        json={"description": "Updated"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "Updated"

    card_group_resp = client.post(
        "/api/v1/admin/card-groups",
        json={"group_id": "DEBIT", "name": "Debit", "description": "Debit cards"},
    )
    assert card_group_resp.status_code == 201
    card_group = card_group_resp.json()

    add_card_resp = client.post(
        f"/api/v1/admin/card-groups/{card_group['group_id']}/members",
        json={"card_id": "card-1"},
    )
    assert add_card_resp.status_code == 201

    remove_card_resp = client.delete(
        f"/api/v1/admin/card-groups/{card_group['group_id']}/members/card-1"
    )
    assert remove_card_resp.status_code == 204

    delete_group_resp = client.delete(f"/api/v1/admin/card-groups/{card_group['group_id']}")
    assert delete_group_resp.status_code == 204


def test_limit_rule_crud_and_local_evaluation(admin_client: Tuple[TestClient, Session]):
    client, db_session = admin_client

    client_group_id = client.post(
        "/api/v1/admin/client-groups",
        json={"group_id": "Business", "name": "Business", "description": "Business clients"},
    ).json()["group_id"]

    card_group_id = client.post(
        "/api/v1/admin/card-groups",
        json={"group_id": "Premium", "name": "Premium", "description": "Premium cards"},
    ).json()["group_id"]

    client.post(
        f"/api/v1/admin/client-groups/{client_group_id}/members",
        json={"client_id": "client-99"},
    )
    client.post(
        f"/api/v1/admin/card-groups/{card_group_id}/members",
        json={"card_id": "card-99"},
    )

    rule_resp = client.post(
        "/api/v1/admin/limits/rules",
        json={
            "phase": "AUTH",
            "daily_limit": 2000,
            "limit_per_tx": 1500,
            "client_group_id": client_group_id,
            "card_group_id": card_group_id,
        },
    )
    assert rule_resp.status_code == 201
    rule_id = rule_resp.json()["id"]

    update_resp = client.put(
        f"/api/v1/admin/limits/rules/{rule_id}",
        json={"daily_limit": 2500},
    )
    assert update_resp.status_code == 200
    updated_rule = update_resp.json()
    assert updated_rule["daily_limit"] == 2500
    assert updated_rule["active"] is True

    success = call_limits_check_and_reserve_sync(
        CheckAndReserveRequest(
            merchant_id="m1",
            terminal_id="t1",
            client_id="client-99",
            card_id="card-99",
            client_group_id=client_group_id,
            card_group_id=card_group_id,
            amount=1200,
        ),
        db=db_session,
    )
    assert success.approved is True
    assert success.daily_limit == 2500
    assert success.limit_per_tx == 1500

    decline = call_limits_check_and_reserve_sync(
        CheckAndReserveRequest(
            merchant_id="m1",
            terminal_id="t1",
            client_id="client-99",
            card_id="card-99",
            client_group_id=client_group_id,
            card_group_id=card_group_id,
            amount=3000,
        ),
        db=db_session,
    )
    assert decline.approved is False
    assert decline.response_code == "51"

    delete_resp = client.delete(f"/api/v1/admin/limits/rules/{rule_id}")
    assert delete_resp.status_code == 200
