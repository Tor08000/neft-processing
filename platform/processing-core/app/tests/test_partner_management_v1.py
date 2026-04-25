from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.partner import Partner
from app.models.partner_management import PartnerLocation, PartnerTerms, PartnerUserRole
from app.routers.admin_partners import router as admin_partners_router
from app.routers.partner_management import router as partner_router


def _make_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    Partner.__table__.create(bind=engine)
    PartnerLocation.__table__.create(bind=engine)
    PartnerTerms.__table__.create(bind=engine)
    PartnerUserRole.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(admin_partners_router, prefix="/api/core")
    app.include_router(partner_router, prefix="/api/core")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_user] = lambda: {"user_id": "admin-1", "role": "admin"}
    app.dependency_overrides[partner_portal_user] = lambda: {"user_id": "partner-owner-1", "portal": "partner"}

    return TestClient(app), testing_session_local


def test_admin_can_create_partner_and_assign_owner() -> None:
    client, _ = _make_client()
    response = client.post(
        "/api/core/admin/partners",
        json={
            "code": "gazprom",
            "legal_name": "Gazprom Neft",
            "partner_type": "FUEL_NETWORK",
            "owner_user_id": "partner-owner-1",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["code"] == "gazprom"

    users = client.get(f"/api/core/admin/partners/{payload['id']}/users")
    assert users.status_code == 200
    assert users.json()[0]["roles"] == ["PARTNER_OWNER"]


def test_partner_me_returns_partner_for_linked_user() -> None:
    client, _ = _make_client()
    create = client.post(
        "/api/core/admin/partners",
        json={
            "code": "partner-001",
            "legal_name": "Partner 001",
            "partner_type": "OTHER",
            "status": "ACTIVE",
            "owner_user_id": "partner-owner-1",
        },
    )
    assert create.status_code == 201

    me = client.get("/api/core/partner/self-profile")
    assert me.status_code == 200
    assert me.json()["partner"]["code"] == "partner-001"


def test_partner_locations_crud() -> None:
    client, _ = _make_client()
    create = client.post(
        "/api/core/admin/partners",
        json={
            "code": "partner-loc",
            "legal_name": "Partner locations",
            "partner_type": "OTHER",
            "status": "ACTIVE",
            "owner_user_id": "partner-owner-1",
        },
    )
    assert create.status_code == 201

    created = client.post("/api/core/partner/locations", json={"title": "АЗС №12", "address": "Москва"})
    assert created.status_code == 201
    location_id = created.json()["id"]

    listed = client.get("/api/core/partner/locations")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    patched = client.patch(f"/api/core/partner/locations/{location_id}", json={"city": "Москва"})
    assert patched.status_code == 200
    assert patched.json()["city"] == "Москва"

    deleted = client.delete(f"/api/core/partner/locations/{location_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "INACTIVE"


def test_partner_terms_get() -> None:
    client, _ = _make_client()
    create = client.post(
        "/api/core/admin/partners",
        json={
            "code": "partner-terms",
            "legal_name": "Partner terms",
            "partner_type": "OTHER",
            "status": "ACTIVE",
            "owner_user_id": "partner-owner-1",
        },
    )
    assert create.status_code == 201
    response = client.get("/api/core/partner/terms")
    assert response.status_code == 200
    assert response.json()["status"] == "DRAFT"


def test_partner_guard_rejects_client_token() -> None:
    client, _ = _make_client()
    client.app.dependency_overrides[partner_portal_user] = lambda: (_ for _ in ()).throw(HTTPException(status_code=403, detail="forbidden"))
    response = client.get("/api/core/partner/self-profile")
    assert response.status_code == 403


def test_admin_guard_rejects_partner_token() -> None:
    client, _ = _make_client()
    client.app.dependency_overrides[require_admin_user] = lambda: (_ for _ in ()).throw(HTTPException(status_code=403, detail="forbidden"))
    response = client.get("/api/core/admin/partners")
    assert response.status_code == 403
