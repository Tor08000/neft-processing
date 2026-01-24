from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.error_handlers import add_exception_handlers
from app.services import admin_auth, client_auth

os.environ.setdefault("NEFT_SKIP_DB_BOOTSTRAP", "1")


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    def protected_endpoint(_claims: dict = Depends(client_auth.verify_client_token)) -> dict:
        return {"ok": True}

    add_exception_handlers(app)
    return app


def test_invalid_token_returns_reason_code(monkeypatch):
    def fake_resolve(_token: str, *, force_refresh: bool = False):
        return "bad-key", False, False

    monkeypatch.setattr(client_auth, "_resolve_public_key", fake_resolve)

    app = _build_app()
    client = TestClient(app)
    response = client.get("/protected", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["reason_code"] == "TOKEN_REJECTED"
    assert payload["error"]["type"] == "token_rejected"


def test_wrong_portal_token_returns_reason_code(make_jwt, rsa_keys, monkeypatch):
    calls: list[bool] = []

    def fake_resolve(_token: str, *, force_refresh: bool = False):
        calls.append(force_refresh)
        return rsa_keys["public"], False, False

    monkeypatch.setattr(client_auth, "_resolve_public_key", fake_resolve)

    app = _build_app()
    client = TestClient(app)
    admin_token = make_jwt(roles=("ADMIN",))

    response = client.get("/protected", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["reason_code"] == "TOKEN_WRONG_PORTAL"
    assert payload["detail"]["error"] == "token_rejected"
    assert payload["detail"]["error_id"]
    assert calls == [False]


def test_admin_verifier_rejects_client_token(make_jwt):
    app = FastAPI()

    @app.get("/admin-protected")
    def admin_protected(_claims: dict = Depends(admin_auth.verify_admin_token)) -> dict:
        return {"ok": True}

    add_exception_handlers(app)
    client = TestClient(app)
    client_token = make_jwt(roles=("CLIENT_USER",), client_id="client-1")

    response = client.get("/admin-protected", headers={"Authorization": f"Bearer {client_token}"})

    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["reason_code"] == "TOKEN_WRONG_PORTAL"
    assert payload["detail"]["error"] == "token_rejected"
    assert payload["detail"]["error_id"]
