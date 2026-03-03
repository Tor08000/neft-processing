from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.error_handlers import add_exception_handlers
from app.services import client_auth

os.environ.setdefault("NEFT_SKIP_DB_BOOTSTRAP", "1")


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.post("/api/core/client/onboarding/profile")
    def onboarding_profile(_: dict = Depends(client_auth.require_onboarding_user)) -> dict:
        return {"ok": True}

    add_exception_handlers(app)
    return app


def _issue_token(private_key: str, *, aud: str, portal: str) -> str:
    payload = {
        "sub": "client-user-1",
        "iss": "neft-auth",
        "aud": aud,
        "portal": portal,
        "role": "CLIENT_OWNER",
        "roles": ["CLIENT_OWNER"],
        "subject_type": "client_user",
        "client_id": "client-1",
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_client_onboarding_accepts_client_audience(monkeypatch, rsa_keys):
    monkeypatch.setattr(client_auth, "EXPECTED_ISSUER", "neft-auth")
    monkeypatch.setattr(client_auth, "EXPECTED_AUDIENCE", "neft-client")
    monkeypatch.setattr(client_auth, "_resolve_public_key", lambda *_args, **_kwargs: (rsa_keys["public"], False, False))

    app = _build_app()
    client = TestClient(app)

    token = _issue_token(rsa_keys["private"], aud="neft-client", portal="client")
    response = client.post("/api/core/client/onboarding/profile", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_client_onboarding_rejects_admin_audience(monkeypatch, rsa_keys):
    monkeypatch.setattr(client_auth, "EXPECTED_ISSUER", "neft-auth")
    monkeypatch.setattr(client_auth, "EXPECTED_AUDIENCE", "neft-client")
    monkeypatch.setattr(client_auth, "_resolve_public_key", lambda *_args, **_kwargs: (rsa_keys["public"], False, False))

    app = _build_app()
    client = TestClient(app)

    token = _issue_token(rsa_keys["private"], aud="neft-admin", portal="admin")
    response = client.post("/api/core/client/onboarding/profile", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"] == "client_token_missing_or_invalid"
    assert payload["reason"] in {"audience_mismatch", "portal_mismatch"}


def test_client_onboarding_rejects_missing_token():
    app = _build_app()
    client = TestClient(app)

    response = client.post("/api/core/client/onboarding/profile")

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"] == "client_token_missing_or_invalid"
    assert payload["reason"] == "missing_header"
