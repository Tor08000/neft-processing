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
    password_hash = hash_password("secret")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000010",
        email=user_email,
        full_name="Demo User",
        password_hash=password_hash,
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
    return demo_user


def test_login_requires_portal(monkeypatch):
    _seed_user(monkeypatch, user_email="client@neft.local", roles=["CLIENT_OWNER"])
    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "secret"},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": {"error": "portal_required", "reason_code": "PORTAL_REQUIRED"}}


def test_portal_resolution_from_body(monkeypatch):
    _seed_user(monkeypatch, user_email="client@neft.local", roles=["CLIENT_OWNER"])
    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "secret", "portal": "client"},
    )
    assert response.status_code == 200
    settings = auth.get_settings()
    claims = _decode_claims(response.json()["access_token"])
    assert claims["iss"] == settings.auth_client_issuer
    assert claims["aud"] == settings.auth_client_audience


def test_portal_resolution_from_header(monkeypatch):
    _seed_user(monkeypatch, user_email="admin@neft.local", roles=["ADMIN"])
    response = _client().post(
        "/api/v1/auth/login",
        headers={"X-Portal": "admin"},
        json={"email": "admin@neft.local", "password": "secret"},
    )
    assert response.status_code == 200
    settings = auth.get_settings()
    claims = _decode_claims(response.json()["access_token"])
    assert claims["iss"] == settings.auth_issuer
    assert claims["aud"] == settings.auth_audience


def test_portal_resolution_from_query(monkeypatch):
    _seed_user(monkeypatch, user_email="partner@neft.local", roles=["PARTNER_OWNER"])
    response = _client().post(
        "/api/v1/auth/login?portal=partner",
        json={"email": "partner@neft.local", "password": "secret"},
    )
    assert response.status_code == 200
    settings = auth.get_settings()
    claims = _decode_claims(response.json()["access_token"])
    assert claims["iss"] == settings.auth_issuer
    assert claims["aud"] == settings.auth_audience


def test_demo_claims_only_in_dev(monkeypatch):
    _seed_user(monkeypatch, user_email="client@neft.local", roles=["CLIENT_OWNER"])
    monkeypatch.setenv("NEFT_ENV", "local")
    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "secret", "portal": "client"},
    )
    assert response.status_code == 200
    settings = auth.get_settings()
    claims = _decode_claims(response.json()["access_token"])
    assert claims.get("client_id") == settings.demo_client_uuid
    assert claims.get("org_id") == settings.demo_org_id

    monkeypatch.setenv("NEFT_ENV", "prod")
    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "secret", "portal": "client"},
    )
    assert response.status_code == 200
    claims = _decode_claims(response.json()["access_token"])
    assert "client_id" not in claims
    assert "org_id" not in claims
