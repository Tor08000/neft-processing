from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.tests.test_admin_onboarding_approve import (
    _InMemoryStorage,
    _base_prefix,
    _configure_onboarding_test_env,
    _create_and_submit_application,
    _jwt,
    onboarding_sqlite_harness,
)


def _bootstrap_client(api_client: TestClient, secret: str) -> tuple[str, str]:
    base = _base_prefix(api_client)
    admin_token = _jwt(secret, roles=["ADMIN"], aud="neft-admin", iss="neft-auth", sub="admin-1")
    app_id = _create_and_submit_application(api_client, base)
    api_client.post(f"{base}/admin/v1/onboarding/applications/{app_id}/start-review", headers={"Authorization": f"Bearer {admin_token}"})
    details = api_client.get(f"{base}/admin/v1/onboarding/applications/{app_id}", headers={"Authorization": f"Bearer {admin_token}"})
    for doc in details.json()["documents"]:
        api_client.post(
            f"{base}/admin/v1/onboarding/documents/{doc['id']}/verify",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "ok"},
        )
    approved = api_client.post(f"{base}/admin/client-onboarding/{app_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    return base, approved.json()["client_id"]


def test_client_users_list_returns_200_on_clean_setup(monkeypatch) -> None:
    secret = "users-list-secret"
    _configure_onboarding_test_env(monkeypatch, secret)
    monkeypatch.setattr("app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.admin_onboarding_review_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())

    with onboarding_sqlite_harness():
        with TestClient(app) as api_client:
            base, client_id = _bootstrap_client(api_client, secret)
            token = _jwt(
                secret,
                roles=["CLIENT_OWNER"],
                aud="neft-client",
                iss="neft-client",
                sub="owner-1",
                extra={"client_id": client_id, "user_id": "owner-1", "subject_type": "client_user"},
            )
            response = api_client.get(f"{base}/client/users", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
            assert "items" in response.json()
