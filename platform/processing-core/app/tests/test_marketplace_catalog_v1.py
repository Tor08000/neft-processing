from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.cases import CaseEvent
from app.models.decision_memory import DecisionMemoryRecord
from app.models.marketplace_catalog import MarketplaceProduct, PartnerProfile
from app.routers.admin.marketplace_catalog import router as admin_router
from app.routers.client_marketplace import router as client_router
from app.routers.partner.marketplace_catalog import router as partner_router
from app.security.client_auth import require_client_user
from app.security.rbac.principal import Principal, get_principal

CURRENT_PRINCIPAL: Principal | None = None
CURRENT_ADMIN_TOKEN: dict = {"user_id": str(uuid4()), "roles": ["admin"]}
CURRENT_CLIENT_TOKEN: dict = {"client_id": str(uuid4())}


def _build_principal(partner_id: str) -> Principal:
    return Principal(
        user_id=UUID(str(uuid4())),
        roles={"partner_user"},
        scopes=set(),
        client_id=None,
        partner_id=UUID(partner_id),
        is_admin=False,
        raw_claims={"user_id": str(uuid4()), "roles": ["partner_user"], "partner_id": partner_id},
    )


@pytest.fixture()
def api_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        AuditLog.__table__,
        CaseEvent.__table__,
        DecisionMemoryRecord.__table__,
        PartnerProfile.__table__,
        MarketplaceProduct.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    app = FastAPI()
    app.include_router(partner_router, prefix="/api")
    app.include_router(client_router, prefix="/api")
    app.include_router(admin_router, prefix="/api/admin")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_principal() -> Principal:
        if CURRENT_PRINCIPAL is None:
            raise RuntimeError("principal_not_set")
        return CURRENT_PRINCIPAL

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_principal] = override_get_principal
    app.dependency_overrides[require_admin_user] = lambda: CURRENT_ADMIN_TOKEN
    app.dependency_overrides[require_client_user] = lambda: CURRENT_CLIENT_TOKEN

    with TestClient(app) as client:
        yield client, SessionLocal

    for table in reversed(tables):
        table.drop(bind=engine)
    engine.dispose()


def _create_product_payload() -> dict:
    return {
        "type": "SERVICE",
        "title": "Diagnostics",
        "description": "Full engine diagnostics",
        "category": "Auto",
        "price_model": "FIXED",
        "price_config": {"amount": 1500, "currency": "RUB"},
    }


def test_partner_profile_create_update_audited(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post(
        "/api/partner/profile",
        json={"company_name": "Acme", "description": "Fleet services"},
    )
    assert response.status_code == 200

    update_response = client.post(
        "/api/partner/profile",
        json={"company_name": "Acme", "description": "Updated"},
    )
    assert update_response.status_code == 200

    with SessionLocal() as db:
        audit_records = db.query(AuditLog).filter(AuditLog.event_type == "PARTNER_PROFILE_CREATED").all()
        assert audit_records
        update_records = db.query(AuditLog).filter(AuditLog.event_type == "PARTNER_PROFILE_UPDATED").all()
        assert update_records


def test_product_create_update(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    assert response.status_code == 201
    product_id = response.json()["id"]

    update_payload = {"title": "Diagnostics+", "price_config": {"amount": 1800, "currency": "RUB"}}
    update_response = client.patch(f"/api/partner/products/{product_id}", json=update_payload)
    assert update_response.status_code == 200

    with SessionLocal() as db:
        audit_records = db.query(AuditLog).filter(AuditLog.event_type == "PRODUCT_UPDATED").all()
        assert audit_records


def test_publish_visible_in_client_list(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    product_id = response.json()["id"]

    publish_response = client.post(f"/api/partner/products/{product_id}/publish")
    assert publish_response.status_code == 200

    client_list_response = client.get("/api/client/marketplace/products")
    assert client_list_response.status_code == 200
    items = client_list_response.json()["items"]
    assert any(item["id"] == product_id for item in items)


def test_partner_cannot_update_foreign_product(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    other_partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    product_id = response.json()["id"]

    CURRENT_PRINCIPAL = _build_principal(other_partner_id)
    update_response = client.patch(
        f"/api/partner/products/{product_id}",
        json={"title": "Hack"},
    )
    assert update_response.status_code == 403


def test_admin_verify_partner(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    create_response = client.post(
        "/api/partner/profile",
        json={"company_name": "Acme", "description": "Fleet services"},
    )
    assert create_response.status_code == 200

    verify_response = client.post(f"/api/admin/partners/{partner_id}/verify", json={"status": "VERIFIED"})
    assert verify_response.status_code == 200

    with SessionLocal() as db:
        audit_records = db.query(AuditLog).filter(AuditLog.event_type == "PARTNER_VERIFIED").all()
        assert audit_records


def test_admin_can_force_product_status(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    product_id = response.json()["id"]

    admin_response = client.post(
        f"/api/admin/products/{product_id}/status",
        json={"status": "ARCHIVED", "reason": "policy"},
    )
    assert admin_response.status_code == 200
    assert admin_response.json()["status"] == "ARCHIVED"
