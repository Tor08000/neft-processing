from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes import auth
from app.main import app
from app.models import User
from app.schemas.auth import LoginRequest
from app.security import hash_password


def _client() -> TestClient:
    return TestClient(app)


def test_login_request_normalizes_email():
    request = LoginRequest(email=" Client@Example.COM \t", password="secret")

    assert request.email == "client@example.com"


def test_login_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        LoginRequest(email="invalid", password="secret")


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

    async def fake_get_user(email: str):
        if email.lower() == "client@neft.local":
            return demo_user
        return None

    async def fake_find_client_id(email: str):
        return "demo-client-id", "Demo Client"

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_find_client_id", fake_find_client_id)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "client"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["client_id"] == "demo-client-id"
    assert data["subject_type"] == "client_user"


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

    async def fake_get_user(email: str):
        if email.lower() == "client@neft.local":
            return demo_user
        return None

    async def fake_find_client_id(email: str):
        return None, None

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_find_client_id", fake_find_client_id)

    response = _client().post(
        "/api/v1/auth/login",
        json={"email": "client@neft.local", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
