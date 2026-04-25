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
    password_hash = hash_password("Neft123!")
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
        json={"email": "client@neft.local", "password": "Neft123!", "portal": "client"},
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
    assert response.json() == {"detail": "invalid_password"}


def test_client_login_user_not_found(monkeypatch):
    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        return None

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "wrong", "portal": "client"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "user_not_found"}


def test_client_login_db_unreachable(monkeypatch):
    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        raise RuntimeError("db down")

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "wrong", "portal": "client"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "db_unreachable"}


def test_admin_login_accepts_username(monkeypatch):
    password_hash = hash_password("Neft123!")
    demo_user = User(
        id="00000000-0000-0000-0000-00000000000a",
        email="admin@neft.local",
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
        json={"username": "admin", "password": "Neft123!", "portal": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "admin@neft.local"

def test_login_returns_503_when_rsa_invalid(monkeypatch):
    password_hash = hash_password("Neft123!")
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
        json={"email": "client@neft.local", "password": "Neft123!", "portal": "client"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "rsa_keys_unavailable"}


def test_login_requires_portal(monkeypatch):
    password_hash = hash_password("Neft123!")
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
        json={"email": "client@neft.local", "password": "Neft123!"},
    )

    assert response.status_code == 200
    assert response.json()["subject_type"] == "client_user"


def _decode_claims(token: str) -> dict:
    return jwt.get_unverified_claims(token)


def test_login_sets_client_portal_claims(monkeypatch):
    password_hash = hash_password("Neft123!")
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
        json={"email": "client@neft.local", "password": "Neft123!", "portal": "client"},
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
    assert claims.get("portal") == "client"


def test_login_sets_admin_portal_claims(monkeypatch):
    password_hash = hash_password("Neft123!")
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
        json={"email": "admin@neft.local", "password": "Neft123!", "portal": "admin"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    claims = _decode_claims(token)
    settings = auth.get_settings()
    assert claims["iss"] == settings.auth_issuer
    assert claims["aud"] == settings.auth_audience
    assert claims.get("portal") == "admin"




def test_login_sets_partner_portal_claims(monkeypatch):
    password_hash = hash_password("Partner123!")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000008",
        email="partner@neft.local",
        full_name="Demo Partner",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(*, email: str | None = None, username: str | None = None):
        candidate = email or username
        if candidate and candidate.lower() == "partner@neft.local":
            return demo_user
        return None

    async def fake_get_roles(_user_id: str):
        return ["PARTNER_OWNER"]

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)
    monkeypatch.setenv("NEFT_ENV", "local")

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "partner@neft.local", "password": "Partner123!", "portal": "partner"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    claims = _decode_claims(token)
    settings = auth.get_settings()
    assert claims["iss"] == settings.auth_partner_issuer
    assert claims["aud"] == settings.auth_partner_audience
    assert claims.get("subject_type") == "partner_user"
    assert claims.get("portal") == "partner"

def test_login_omits_demo_org_in_prod(monkeypatch):
    password_hash = hash_password("Neft123!")
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
        json={"email": "client@neft.local", "password": "Neft123!", "portal": "client"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    claims = _decode_claims(token)
    assert "org_id" not in claims
    assert "client_id" not in claims

def test_login_blocked_when_force_sso_and_password_disabled(monkeypatch):
    monkeypatch.setenv("FORCE_SSO", "1")
    monkeypatch.setenv("DISABLE_PASSWORD_LOGIN", "1")

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "Neft123!", "portal": "client"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "password_login_disabled"}


def test_oauth_start_returns_503_when_oidc_disabled(monkeypatch):
    monkeypatch.setenv("OIDC_ENABLED", "0")

    response = _client().get("/api/v1/auth/oauth/start?provider=corp&portal=client")

    assert response.status_code == 503
    assert response.json() == {"detail": "oidc_disabled"}


def test_login_access_token_contains_sid(monkeypatch):
    password_hash = hash_password("Neft123!")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000099",
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

    async def fake_create_session(**_kwargs):
        return "11111111-1111-1111-1111-111111111111"

    async def fake_persist_refresh(**_kwargs):
        return "22222222-2222-2222-2222-222222222222"

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)
    monkeypatch.setattr(auth, "_create_session", fake_create_session)
    monkeypatch.setattr(auth, "_persist_refresh_token", fake_persist_refresh)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "Neft123!", "portal": "client"},
    )

    assert response.status_code == 200
    claims = _decode_claims(response.json()["access_token"])
    assert claims.get("sid") == "11111111-1111-1111-1111-111111111111"
    assert claims.get("jti")


def test_login_omits_sid_and_refresh_token_when_session_persistence_skipped(monkeypatch):
    password_hash = hash_password("Neft123!")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000100",
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

    async def fail_create_session(**_kwargs):
        raise RuntimeError("session store unavailable")

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)
    monkeypatch.setattr(auth, "_create_session", fail_create_session)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "Neft123!", "portal": "client"},
    )

    assert response.status_code == 200
    claims = _decode_claims(response.json()["access_token"])
    assert "sid" not in claims
    assert response.json()["refresh_token"] is None
