from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.partner import Partner
from app.models.partner_management import PartnerLocation, PartnerTerms, PartnerUserRole
from app.routers.partner_management import router as partner_router


def _make_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    Partner.__table__.create(bind=engine)
    PartnerLocation.__table__.create(bind=engine)
    PartnerTerms.__table__.create(bind=engine)
    PartnerUserRole.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(partner_router, prefix="/api/core")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[partner_portal_user] = lambda: {"user_id": "partner-owner-1", "portal": "partner"}

    return TestClient(app), testing_session_local


def _seed_partner(session_factory: sessionmaker) -> str:
    db = session_factory()
    try:
        partner = Partner(
            code="demo-partner",
            legal_name="Demo Partner",
            partner_type="OTHER",
            status="ACTIVE",
            contacts={},
        )
        db.add(partner)
        db.flush()
        db.add(PartnerTerms(partner_id=partner.id, version=1, status="DRAFT", terms={}))
        db.add(PartnerUserRole(partner_id=partner.id, user_id="partner-owner-1", roles=["PARTNER_OWNER"]))
        db.commit()
        return str(partner.id)
    finally:
        db.close()


def test_partner_me_for_linked_user() -> None:
    client, session_factory = _make_client()
    _seed_partner(session_factory)

    me = client.get("/api/core/partner/me")
    assert me.status_code == 200
    body = me.json()
    assert body["partner"]["code"] == "demo-partner"
    assert "PARTNER_OWNER" in body["my_roles"]


def test_partner_me_denies_unlinked_user() -> None:
    client, _ = _make_client()
    response = client.get("/api/core/partner/me")
    assert response.status_code == 403
    assert response.json()["detail"] == "partner_not_linked"


def test_locations_crud_with_soft_delete_and_no_cross_tenant_access() -> None:
    client, session_factory = _make_client()
    partner_id = _seed_partner(session_factory)

    created = client.post("/api/core/partner/locations", json={"title": "АЗС №1", "address": "Москва"})
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

    db = session_factory()
    try:
        second_partner = Partner(code="other", legal_name="Other", partner_type="OTHER", status="ACTIVE", contacts={})
        db.add(second_partner)
        db.flush()
        alien = PartnerLocation(partner_id=second_partner.id, title="Alien", address="Alien street", status="ACTIVE")
        db.add(alien)
        db.add(PartnerUserRole(partner_id=second_partner.id, user_id="other-user", roles=["PARTNER_OWNER"]))
        db.commit()
        alien_id = str(alien.id)
    finally:
        db.close()

    denied = client.patch(f"/api/core/partner/locations/{alien_id}", json={"city": "Nope"})
    assert denied.status_code == 404


def test_partner_users_owner_can_add_remove_non_owner_forbidden() -> None:
    client, session_factory = _make_client()
    _seed_partner(session_factory)

    added = client.post("/api/core/partner/users", json={"user_id": "manager-1", "roles": ["PARTNER_MANAGER"]})
    assert added.status_code == 201

    removed = client.delete("/api/core/partner/users/manager-1")
    assert removed.status_code == 200

    client.app.dependency_overrides[partner_portal_user] = lambda: {"user_id": "partner-manager-1", "portal": "partner"}
    db = session_factory()
    try:
        partner_id = str(db.query(Partner).first().id)
        db.add(PartnerUserRole(partner_id=partner_id, user_id="partner-manager-1", roles=["PARTNER_MANAGER"]))
        db.commit()
    finally:
        db.close()

    forbidden = client.post("/api/core/partner/users", json={"user_id": "viewer-1", "roles": ["PARTNER_VIEWER"]})
    assert forbidden.status_code == 403


def test_guard_rejects_non_partner_token() -> None:
    client, session_factory = _make_client()
    _seed_partner(session_factory)
    client.app.dependency_overrides[partner_portal_user] = lambda: (_ for _ in ()).throw(HTTPException(status_code=403, detail="wrong_portal"))
    response = client.get("/api/core/partner/me")
    assert response.status_code == 403
