from __future__ import annotations

import pytest
from jose import jwt
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes import auth
from app.main import app
from app.models import User
from app.schemas.auth import LoginRequest
from app.security import hash_password
from app.services.keys import InvalidRSAKeyError


def _client() -> TestClient:
    return TestClient(app)


def test_login_request_normalizes_email():
    request = LoginRequest(email=" Client@Example.COM 	", password="secret")

    assert request.email == "client@example.com"


def test_login_request_accepts_username():
    request = LoginRequest(username=" Admin ", password="secret")

    assert request.username == "admin"


def test_login_request_rejects_missing_identifier():
    with pytest.raises(ValidationError):
        LoginRequest(password="secret")


def test_login_request_accepts_legacy_login_email():
    request = LoginRequest(login=" Admin@Example.com ", password="secret")

    assert request.email == "admin@example.com"
    assert request.username is None


def test_login_request_accepts_legacy_login_username():
    request = LoginRequest(login=" Admin ", password="secret")

    assert request.username == "admin"
    assert request.email is None


def test_client_demo_login_local_domain_ok(monkeypatch):
    password_hash = hash_password("client")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000001",
        email="client@neft.local",
        full_name="Demo Client",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == "client@neft.local":
            return demo_user
        return None

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    async def fake_get_roles(_user_id: str):
        return ["CLIENT_OWNER"]

    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "client", "portal": "client"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["subject_type"] == "client_user"
    assert data["roles"] == ["CLIENT_OWNER"]


def test_client_login_invalid_password(monkeypatch):
    password_hash = hash_password("correct")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000002",
        email="client@neft.local",
        full_name="Demo Client",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == "client@neft.local":
            return demo_user
        return None

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    async def fake_get_roles(_user_id: str):
        return ["CLIENT_OWNER"]

    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "wrong", "portal": "client"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}




def test_admin_login_accepts_username(monkeypatch):
    password_hash = hash_password("admin123")
    demo_user = User(
        id="00000000-0000-0000-0000-00000000000a",
        email="admin@example.com",
        username="admin",
        full_name="Demo Admin",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == "admin":
            return demo_user
        return None

    async def fake_get_roles(_user_id: str):
        return ["ADMIN", "PLATFORM_ADMIN"]

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)

    response = _client().post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123", "portal": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"

def test_login_returns_503_when_rsa_invalid(monkeypatch):
    password_hash = hash_password("client")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000003",
        email="client@neft.local",
        full_name="Demo Client",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == "client@neft.local":
            return demo_user
        return None

    async def fake_get_roles(_user_id: str):
        return ["CLIENT_OWNER"]

    def raise_invalid_key(*_args, **_kwargs):
        raise InvalidRSAKeyError("invalid_rsa_keys")

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)
    monkeypatch.setattr(auth, "create_access_token", raise_invalid_key)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "client", "portal": "client"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "rsa_keys_unavailable"}


def test_login_requires_portal(monkeypatch):
    password_hash = hash_password("client")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000004",
        email="client@neft.local",
        full_name="Demo Client",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == "client@neft.local":
            return demo_user
        return None

    async def fake_get_roles(_user_id: str):
        return ["CLIENT_OWNER"]

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "client"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": {"error": "portal_required", "reason_code": "PORTAL_REQUIRED"}}


def _decode_claims(token: str) -> dict:
    return jwt.get_unverified_claims(token)


def test_login_sets_client_portal_claims(monkeypatch):
    password_hash = hash_password("client")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000005",
        email="client@neft.local",
        full_name="Demo Client",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == "client@neft.local":
            return demo_user
        return None

    async def fake_get_roles(_user_id: str):
        return ["CLIENT_OWNER"]

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)
    monkeypatch.setenv("NEFT_ENV", "local")

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "client", "portal": "client"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    claims = _decode_claims(token)
    settings = auth.get_settings()
    assert claims["iss"] == settings.auth_client_issuer
    assert claims["aud"] == settings.auth_client_audience
    assert claims.get("client_id") == settings.demo_client_uuid
    assert claims.get("org_id") == settings.demo_org_id
    assert claims.get("user_id") == str(demo_user.id)


def test_login_sets_admin_portal_claims(monkeypatch):
    password_hash = hash_password("admin123")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000006",
        email="admin@neft.local",
        full_name="Demo Admin",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == "admin@neft.local":
            return demo_user
        return None

    async def fake_get_roles(_user_id: str):
        return ["ADMIN"]

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "admin@neft.local", "password": "admin123", "portal": "admin"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    claims = _decode_claims(token)
    settings = auth.get_settings()
    assert claims["iss"] == settings.auth_issuer
    assert claims["aud"] == settings.auth_audience


def test_login_omits_demo_org_in_prod(monkeypatch):
    password_hash = hash_password("client")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000007",
        email="client@neft.local",
        full_name="Demo Client",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == "client@neft.local":
            return demo_user
        return None

    async def fake_get_roles(_user_id: str):
        return ["CLIENT_OWNER"]

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)
    monkeypatch.setenv("NEFT_ENV", "prod")

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "client", "portal": "client"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    claims = _decode_claims(token)
    assert "org_id" not in claims
    assert "client_id" not in claims
