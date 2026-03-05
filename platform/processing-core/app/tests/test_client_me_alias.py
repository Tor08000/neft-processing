from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import client_me
from app.schemas.portal_me import PortalMeResponse, PortalMeUser


def test_client_me_alias_returns_200_without_redirect(monkeypatch):
    app = FastAPI()
    app.include_router(client_me.router, prefix="/api/core")
    app.dependency_overrides[client_me.require_onboarding_user] = lambda: {"client_id": "1", "sub": "u-1", "portal": "client"}
    app.dependency_overrides[client_me.get_db] = lambda: None

    payload = PortalMeResponse(
        actor_type="client",
        context="client",
        user=PortalMeUser(id="u-1", email="client@neft.local", subject_type="client_user"),
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
    )
    monkeypatch.setattr(client_me, "build_portal_me", lambda db, token, request_id=None: payload)

    client = TestClient(app)
    response = client.get("/api/core/client/me")

    assert response.status_code == 200
    assert "location" not in response.headers
    assert response.json()["user"]["email"] == "client@neft.local"
