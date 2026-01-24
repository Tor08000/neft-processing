from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.error_handlers import add_exception_handlers
from app.services import client_auth

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
