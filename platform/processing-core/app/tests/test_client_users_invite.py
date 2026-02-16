from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.tests.test_admin_onboarding_approve import _InMemoryStorage, _base_prefix, _create_and_submit_application, _jwt


def _setup(monkeypatch) -> tuple[str, TestClient, str]:
    secret = "users-invite-secret"
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "onboarding-secret")
    monkeypatch.setenv("CLIENT_TOKEN_SECRET", secret)
    monkeypatch.setenv("CLIENT_PUBLIC_KEY", secret)
    monkeypatch.setenv("ADMIN_PUBLIC_KEY", secret)
    monkeypatch.setenv("NEFT_AUTH_ALLOWED_ALGS", "HS256")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setattr("app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.admin_onboarding_review_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    return secret


def test_invite_user_creates_pending_and_prevents_duplicates(monkeypatch) -> None:
    secret = _setup(monkeypatch)

    with TestClient(app) as api_client:
        base = _base_prefix(api_client)
        admin_token = _jwt(secret, roles=["ADMIN"], aud="neft-admin", iss="neft-auth", sub="admin-1")
        app_id = _create_and_submit_application(api_client, base)
        api_client.post(f"{base}/admin/v1/onboarding/applications/{app_id}/start-review", headers={"Authorization": f"Bearer {admin_token}"})
        details = api_client.get(f"{base}/admin/v1/onboarding/applications/{app_id}", headers={"Authorization": f"Bearer {admin_token}"})
        for doc in details.json()["documents"]:
            api_client.post(f"{base}/admin/v1/onboarding/documents/{doc['id']}/verify", headers={"Authorization": f"Bearer {admin_token}"}, json={"comment": "ok"})
        approved = api_client.post(f"{base}/admin/client-onboarding/{app_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
        client_id = approved.json()["client_id"]

        token = _jwt(
            secret,
            roles=["CLIENT_OWNER"],
            aud="neft-client",
            iss="neft-client",
            sub="owner-1",
            extra={"client_id": client_id, "user_id": "owner-1", "subject_type": "client_user"},
        )
        resp = api_client.post(
            f"{base}/client/users/invite",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "new.user@example.com", "roles": ["CLIENT_MANAGER"]},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "PENDING"
        assert resp.json()["invitation_id"]

        duplicate = api_client.post(
            f"{base}/client/users/invite",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "new.user@example.com", "roles": ["CLIENT_VIEWER"]},
        )
        assert duplicate.status_code == 409
