from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.security.rbac.principal import Principal, get_principal
from app.services import admin_auth, client_auth, partner_auth


def _invalid_token(_: str) -> dict:
    raise HTTPException(status_code=401, detail="invalid")


def test_get_principal_keeps_non_uuid_partner_context(monkeypatch) -> None:
    app = FastAPI()

    @app.get("/partner-context")
    def partner_context(principal: Principal = Depends(get_principal)) -> dict[str, str | None]:
        return {
            "partner_id": str(principal.partner_id) if principal.partner_id is not None else None,
            "actor_id": str(principal.user_id) if principal.user_id is not None else None,
        }

    monkeypatch.setattr(admin_auth, "verify_admin_token", _invalid_token)
    monkeypatch.setattr(client_auth, "verify_client_token", _invalid_token)
    monkeypatch.setattr(
        partner_auth,
        "verify_partner_token",
        lambda _: {
            "sub": "partner.user@example.com",
            "user_id": "7f93389d-6d9d-4ef3-b1d9-acff59e65dd9",
            "subject_type": "partner_user",
            "roles": ["PARTNER_OWNER"],
            "partner_id": "partner-alpha",
            "scopes": ["partner:marketplace:orders:*"],
        },
    )

    with TestClient(app) as client:
        response = client.get("/partner-context", headers={"Authorization": "Bearer stub-token"})

    assert response.status_code == 200
    assert response.json()["partner_id"] == "partner-alpha"
    assert response.json()["actor_id"] == "7f93389d-6d9d-4ef3-b1d9-acff59e65dd9"


def test_get_principal_resolves_canonical_partner_context_from_binding(monkeypatch) -> None:
    app = FastAPI()

    @app.get("/partner-context")
    def partner_context(principal: Principal = Depends(get_principal)) -> dict[str, str | None]:
        return {"partner_id": str(principal.partner_id) if principal.partner_id is not None else None}

    class _DummySession:
        def close(self) -> None:
            return None

    monkeypatch.setattr(admin_auth, "verify_admin_token", _invalid_token)
    monkeypatch.setattr(client_auth, "verify_client_token", _invalid_token)
    monkeypatch.setattr(
        partner_auth,
        "verify_partner_token",
        lambda _: {
            "sub": "partner.user@example.com",
            "user_id": "partner-user-1",
            "subject_type": "partner_user",
            "roles": ["PARTNER_OWNER"],
            "partner_id": "1",
            "scopes": ["partner:marketplace:orders:*"],
        },
    )
    monkeypatch.setattr("app.db.get_sessionmaker", lambda: (lambda: _DummySession()))
    monkeypatch.setattr(
        "app.services.partner_context.resolve_partner_id_from_claims",
        lambda db, *, claims: "9b9a3a6b-8618-43de-9f55-cd71f08852fe",
    )

    with TestClient(app) as client:
        response = client.get("/partner-context", headers={"Authorization": "Bearer stub-token"})

    assert response.status_code == 200
    assert response.json()["partner_id"] == "9b9a3a6b-8618-43de-9f55-cd71f08852fe"
