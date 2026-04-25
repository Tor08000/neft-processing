from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies.support import support_user
from app.services import admin_auth, client_auth, partner_auth


def _invalid_token(_: str) -> dict:
    raise HTTPException(status_code=401, detail="invalid")


def test_support_user_resolves_canonical_partner_context_from_legacy_org_claim(monkeypatch) -> None:
    app = FastAPI()

    @app.get("/support-context")
    def support_context(payload: dict = Depends(support_user)) -> dict[str, str | bool | None]:
        return {
            "partner_id": str(payload.get("partner_id")) if payload.get("partner_id") is not None else None,
            "is_partner": bool(payload.get("is_partner")),
        }

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
            "org_id": "1",
        },
    )
    monkeypatch.setattr("app.db.get_sessionmaker", lambda: (lambda: _DummySession()))
    monkeypatch.setattr(
        "app.services.partner_context.resolve_partner_id_from_claims",
        lambda db, *, claims: "9b9a3a6b-8618-43de-9f55-cd71f08852fe",
    )

    with TestClient(app) as client:
        response = client.get("/support-context", headers={"Authorization": "Bearer stub-token"})

    assert response.status_code == 200
    assert response.json() == {
        "partner_id": "9b9a3a6b-8618-43de-9f55-cd71f08852fe",
        "is_partner": True,
    }
