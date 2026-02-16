from __future__ import annotations

import os
import uuid

from jose import jwt
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ["CRM_DATABASE_URL"] = "sqlite:///./crm_test.db"

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


def _token(user_id: str, tenant_id: str, roles: list[str], subordinate_ids: list[str] | None = None) -> str:
    payload = {"sub": user_id, "tenant_id": tenant_id, "roles": roles, "subordinate_ids": subordinate_ids or []}
    return jwt.encode(payload, "dev", algorithm="HS256")


def _headers(user_id: str, tenant_id: str, roles: list[str], subordinate_ids: list[str] | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id, tenant_id, roles, subordinate_ids)}"}


def setup_module() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS clients"))
        conn.execute(text("DROP TABLE IF EXISTS partners"))
        conn.execute(text("CREATE TABLE clients (id TEXT PRIMARY KEY, tenant_id TEXT)"))
        conn.execute(text("CREATE TABLE partners (id TEXT PRIMARY KEY, tenant_id TEXT)"))


def test_crm_smoke() -> None:
    client = TestClient(app)
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    entity_id = str(uuid.uuid4())
    with SessionLocal.begin() as db:
        db.execute(text("INSERT INTO clients(id, tenant_id) VALUES (:id, :tenant_id)"), {"id": entity_id, "tenant_id": tenant_id})

    h = _headers(user_id, tenant_id, ["admin"])
    pipe = client.post("/crm/pipelines", json={"name": "Default"}, headers=h)
    assert pipe.status_code == 200
    pipeline_id = pipe.json()["id"]

    stage = client.post(
        "/crm/stages",
        json={"pipeline_id": pipeline_id, "name": "Lead", "position": 1, "probability": 20},
        headers=h,
    )
    assert stage.status_code == 200
    stage_id = stage.json()["id"]

    contact = client.post(
        "/crm/contacts",
        json={
            "entity_type": "client",
            "entity_id": entity_id,
            "first_name": "Ivan",
            "last_name": "Petrov",
            "email": "ivan@example.com",
            "owner_id": user_id,
        },
        headers=h,
    )
    assert contact.status_code == 200

    deal = client.post(
        "/crm/deals",
        json={
            "entity_type": "client",
            "entity_id": entity_id,
            "pipeline_id": pipeline_id,
            "stage_id": stage_id,
            "title": "Fuel contract",
            "amount": 1000,
            "currency": "USD",
            "owner_id": user_id,
        },
        headers=h,
    )
    assert deal.status_code == 200
    deal_id = deal.json()["id"]

    moved = client.post(f"/crm/deals/{deal_id}/move-stage", json={"stage_id": stage_id}, headers=h)
    assert moved.status_code == 200

    closed = client.post(f"/crm/deals/{deal_id}/close", json={"status": "won"}, headers=h)
    assert closed.status_code == 200

    with SessionLocal() as db:
        audit_count = db.execute(text("SELECT count(*) FROM crm_audit_log WHERE entity_id=:id"), {"id": deal_id}).scalar_one()
        outbox_count = db.execute(text("SELECT count(*) FROM outbox_events WHERE event_type='crm.deal.won'"))
        outbox_count = outbox_count.scalar_one()
    assert audit_count >= 3
    assert outbox_count == 1


def test_multi_tenant_isolation() -> None:
    client = TestClient(app)
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    entity_a = str(uuid.uuid4())
    entity_b = str(uuid.uuid4())
    with SessionLocal.begin() as db:
        db.execute(text("INSERT INTO clients(id, tenant_id) VALUES (:id, :tenant_id)"), {"id": entity_a, "tenant_id": tenant_a})
        db.execute(text("INSERT INTO clients(id, tenant_id) VALUES (:id, :tenant_id)"), {"id": entity_b, "tenant_id": tenant_b})

    ha = _headers(user_id, tenant_a, ["admin"])
    hb = _headers(user_id, tenant_b, ["admin"])

    pipe_a = client.post("/crm/pipelines", json={"name": "A"}, headers=ha).json()
    stage_a = client.post(
        "/crm/stages", json={"pipeline_id": pipe_a["id"], "name": "s", "position": 1, "probability": 10}, headers=ha
    ).json()

    pipe_b = client.post("/crm/pipelines", json={"name": "B"}, headers=hb).json()
    stage_b = client.post(
        "/crm/stages", json={"pipeline_id": pipe_b["id"], "name": "s", "position": 1, "probability": 10}, headers=hb
    ).json()

    client.post(
        "/crm/deals",
        json={
            "entity_type": "client",
            "entity_id": entity_a,
            "pipeline_id": pipe_a["id"],
            "stage_id": stage_a["id"],
            "title": "A",
            "amount": 1,
            "currency": "USD",
            "owner_id": user_id,
        },
        headers=ha,
    )
    client.post(
        "/crm/deals",
        json={
            "entity_type": "client",
            "entity_id": entity_b,
            "pipeline_id": pipe_b["id"],
            "stage_id": stage_b["id"],
            "title": "B",
            "amount": 1,
            "currency": "USD",
            "owner_id": user_id,
        },
        headers=hb,
    )

    deals_a = client.get("/crm/deals", headers=ha)
    deals_b = client.get("/crm/deals", headers=hb)
    assert deals_a.status_code == 200
    assert deals_b.status_code == 200
    assert all(item["tenant_id"] == tenant_a for item in deals_a.json())
    assert all(item["tenant_id"] == tenant_b for item in deals_b.json())
