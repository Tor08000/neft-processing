import os
from typing import Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure Celery is disabled for tests so the local evaluator is used
os.environ["DISABLE_CELERY"] = "1"

from app import models  # noqa: F401
from app.api.v1.endpoints.admin_limits import router as admin_router
from app.db import Base, get_db
from app.models import groups as group_models  # noqa: F401
from app.services.limits import (
    CheckAndReserveRequest,
    call_limits_check_and_reserve_sync,
)


@pytest.fixture()
def admin_client(admin_auth_headers: dict) -> Tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(admin_router, prefix="/api/v1")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    client.headers.update(admin_auth_headers)
    return client, TestingSessionLocal


def test_client_and_card_group_crud(admin_client: Tuple[TestClient, sessionmaker]):
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

    delete_group_resp = client.delete(
        f"/api/v1/admin/card-groups/{card_group['group_id']}"
    )
    assert delete_group_resp.status_code == 204


def test_limit_rule_crud_and_local_evaluation(
    admin_client: Tuple[TestClient, sessionmaker]
):
    client, SessionLocal = admin_client

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

    with SessionLocal() as db:
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
            db=db,
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
            db=db,
        )
        assert decline.approved is False
        assert decline.response_code == "51"

    delete_resp = client.delete(f"/api/v1/admin/limits/rules/{rule_id}")
    assert delete_resp.status_code == 200
