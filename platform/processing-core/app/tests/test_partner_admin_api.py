from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.partner import Partner
from app.models.partner_management import PartnerLocation, PartnerTerms, PartnerUserRole
from app.routers.admin_partners import router as admin_partners_router


def _make_client() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    Partner.__table__.create(bind=engine)
    PartnerLocation.__table__.create(bind=engine)
    PartnerTerms.__table__.create(bind=engine)
    PartnerUserRole.__table__.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(admin_partners_router, prefix="/api/core")

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_user] = lambda: {"user_id": "admin-1", "role": "admin"}

    return TestClient(app)


def test_admin_create_partner_creates_terms_and_owner_role() -> None:
    client = _make_client()
    response = client.post(
        "/api/core/admin/partners",
        json={
            "code": "partner-001",
            "legal_name": "ООО Ромашка",
            "partner_type": "FUEL_NETWORK",
            "owner_user_id": "partner-owner-1",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["code"] == "partner-001"

    users = client.get(f"/api/core/admin/partners/{payload['id']}/users")
    assert users.status_code == 200
    assert users.json()[0]["roles"] == ["PARTNER_OWNER"]


def test_admin_list_partners_has_pagination() -> None:
    client = _make_client()
    for idx in range(3):
        created = client.post(
            "/api/core/admin/partners",
            json={
                "code": f"partner-{idx}",
                "legal_name": f"Partner {idx}",
                "partner_type": "OTHER",
            },
        )
        assert created.status_code == 201

    listed = client.get("/api/core/admin/partners?page=1&page_size=2")
    assert listed.status_code == 200
    body = listed.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 3
    assert len(body["items"]) == 2
