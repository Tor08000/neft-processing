from __future__ import annotations

from jose import jwt
from fastapi.testclient import TestClient

from app.api.routes import auth
from app.main import app
from app.models import User
from app.security import hash_password


def _client() -> TestClient:
    return TestClient(app)


def _decode_claims(token: str) -> dict:
    return jwt.get_unverified_claims(token)


def _seed_user(monkeypatch, *, user_email: str, roles: list[str]):
    demo_user = User(
        id="00000000-0000-0000-0000-000000000010",
        email=user_email,
        full_name="Demo User",
        password_hash=hash_password("secret"),
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == user_email.lower():
            return demo_user
        return None

    async def fake_get_roles(_user_id: str):
        return roles

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)


def test_login_portal_client_issues_neft_client_audience(monkeypatch):
    _seed_user(monkeypatch, user_email="client@neft.local", roles=["CLIENT_OWNER"])
    response = _client().post("/api/v1/auth/login", json={"email": "client@neft.local", "password": "secret", "portal": "client"})
    assert response.status_code == 200
    claims = _decode_claims(response.json()["access_token"])
    settings = auth.get_settings()
    assert claims["aud"] == settings.auth_client_audience
    assert claims["iss"] == settings.auth_client_issuer
    assert claims["portal"] == "client"


def test_login_portal_admin_issues_neft_admin_audience(monkeypatch):
    _seed_user(monkeypatch, user_email="admin@neft.local", roles=["ADMIN"])
    response = _client().post("/api/v1/auth/login", json={"email": "admin@neft.local", "password": "secret", "portal": "admin"})
    assert response.status_code == 200
    claims = _decode_claims(response.json()["access_token"])
    settings = auth.get_settings()
    assert claims["aud"] == settings.auth_audience
    assert claims["iss"] == settings.auth_issuer
    assert claims["portal"] == "admin"


def test_login_portal_partner_issues_neft_partner_audience(monkeypatch):
    _seed_user(monkeypatch, user_email="partner@neft.local", roles=["PARTNER_OWNER"])
    response = _client().post("/api/v1/auth/login", json={"email": "partner@neft.local", "password": "secret", "portal": "partner"})
    assert response.status_code == 200
    claims = _decode_claims(response.json()["access_token"])
    settings = auth.get_settings()
    assert claims["aud"] == settings.auth_partner_audience
    assert claims["iss"] == settings.auth_partner_issuer
    assert claims["portal"] == "partner"
