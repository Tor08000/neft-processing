from pathlib import Path
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies.client import client_portal_user
from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.models.service_requests import ServiceRequest
from app.routers import portal_me
from app.routers.portal_me import router as portal_me_router
from app.routers.service_requests import router as service_requests_router
from app.schemas.portal_me import PortalMeResponse, PortalMeUser
from app.security.rbac.principal import Principal, get_principal

CLIENT_1 = "11111111-1111-1111-1111-111111111111"
CLIENT_2 = "22222222-2222-2222-2222-222222222222"
PARTNER_1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PARTNER_2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
SERVICE_1 = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _sessionmaker(tmp_path: Path):
    db_path = tmp_path / "service_requests_test.sqlite"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True, connect_args={"check_same_thread": False})
    ServiceRequest.__table__.create(bind=engine, checkfirst=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _build_client(tmp_path: Path):
    maker = _sessionmaker(tmp_path)
    app = FastAPI()
    app.include_router(service_requests_router, prefix="/api/core")

    state = {
        "client": {"client_id": CLIENT_1, "tenant_id": 1, "sub": "u-1"},
        "partner": {"partner_id": PARTNER_1, "tenant_id": 1, "sub": "p-1"},
    }

    def override_db():
        session = maker()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[client_portal_user] = lambda: state["client"]
    app.dependency_overrides[partner_portal_user] = lambda: state["partner"]
    return TestClient(app), state


def test_portal_me_accepts_client_token(monkeypatch, tmp_path):
    maker = _sessionmaker(tmp_path)
    app = FastAPI()
    app.include_router(portal_me_router, prefix="/api/core")

    def override_db():
        session = maker()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id=UUID(CLIENT_1),
        roles={"client_user"},
        scopes=set(),
        client_id=UUID(CLIENT_1),
        partner_id=None,
        is_admin=False,
        raw_claims={"sub": CLIENT_1, "portal": "client", "client_id": CLIENT_1, "tenant_id": 1, "roles": ["CLIENT_USER"]},
    )
    monkeypatch.setattr(
        portal_me,
        "build_portal_me",
        lambda db, token, request_id=None: PortalMeResponse(
            actor_type="client",
            context="client",
            user=PortalMeUser(id=CLIENT_1, email="client@neft.local", subject_type="client_user"),
            org=None,
            org_status="NONE",
            org_roles=[],
            user_roles=["CLIENT_USER"],
            memberships=[],
            flags={},
            legal=None,
            modules=None,
            features=None,
            subscription=None,
            entitlements_snapshot=None,
            capabilities=[],
            nav_sections=None,
            access_state="ACTIVE",
            access_reason=None,
        ),
    )

    client = TestClient(app)
    response = client.get("/api/core/portal/me")
    assert response.status_code == 200


def test_service_request_client_can_create_and_list_own(tmp_path):
    client, _state = _build_client(tmp_path)
    created = client.post("/api/core/services/requests", json={"partner_id": PARTNER_1, "service_id": SERVICE_1, "payload": {"description": "need help"}})
    assert created.status_code == 201
    req_id = created.json()["id"]

    listed = client.get("/api/core/services/requests")
    assert listed.status_code == 200
    assert any(item["id"] == req_id for item in listed.json())

    details = client.get(f"/api/core/services/requests/{req_id}")
    assert details.status_code == 200
    assert details.json()["id"] == req_id


def test_service_request_other_client_cannot_access(tmp_path):
    client, state = _build_client(tmp_path)
    created = client.post("/api/core/services/requests", json={"partner_id": PARTNER_1, "service_id": SERVICE_1, "payload": {}})
    req_id = created.json()["id"]

    state["client"] = {"client_id": CLIENT_2, "tenant_id": 1, "sub": "u-2"}
    denied = client.get(f"/api/core/services/requests/{req_id}")
    assert denied.status_code == 404


def test_service_request_partner_sees_only_assigned(tmp_path):
    client, state = _build_client(tmp_path)
    client.post("/api/core/services/requests", json={"partner_id": PARTNER_1, "service_id": SERVICE_1, "payload": {}})
    client.post("/api/core/services/requests", json={"partner_id": PARTNER_2, "service_id": SERVICE_1, "payload": {}})

    partner_list = client.get("/api/core/partner/services/requests")
    assert partner_list.status_code == 200
    assert all(item["partner_id"] == PARTNER_1 for item in partner_list.json())

    state["partner"] = {"partner_id": PARTNER_2, "tenant_id": 1, "sub": "p-2"}
    partner2_list = client.get("/api/core/partner/services/requests")
    assert partner2_list.status_code == 200
    assert all(item["partner_id"] == PARTNER_2 for item in partner2_list.json())


def test_service_request_status_transitions_enforced(tmp_path):
    client, state = _build_client(tmp_path)
    created = client.post("/api/core/services/requests", json={"partner_id": PARTNER_1, "service_id": SERVICE_1, "payload": {}})
    req_id = created.json()["id"]

    direct_done = client.post(f"/api/core/partner/services/requests/{req_id}/complete")
    assert direct_done.status_code == 409

    accepted = client.post(f"/api/core/partner/services/requests/{req_id}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    done_without_start = client.post(f"/api/core/partner/services/requests/{req_id}/complete")
    assert done_without_start.status_code == 409

    started = client.post(f"/api/core/partner/services/requests/{req_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    done = client.post(f"/api/core/partner/services/requests/{req_id}/complete")
    assert done.status_code == 200
    assert done.json()["status"] == "done"

    state["partner"] = {"partner_id": PARTNER_2, "tenant_id": 2, "sub": "p-2"}
    cross_tenant = client.post(f"/api/core/partner/services/requests/{req_id}/reject")
    assert cross_tenant.status_code == 404
