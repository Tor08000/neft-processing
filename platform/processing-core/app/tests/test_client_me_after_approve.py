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


def test_client_me_after_approve_returns_active_profile(monkeypatch) -> None:
    secret = "approve-secret"
    _configure_onboarding_test_env(monkeypatch, secret)
    monkeypatch.setattr("app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.admin_onboarding_review_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())

    admin_token = _jwt(secret, roles=["ADMIN"], aud="neft-admin", iss="neft-auth", sub="admin-1")

    with onboarding_sqlite_harness():
        with TestClient(app) as api_client:
            base = _base_prefix(api_client)
            app_id = _create_and_submit_application(api_client, base)

            api_client.post(
                f"{base}/admin/v1/onboarding/applications/{app_id}/start-review",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            details = api_client.get(
                f"{base}/admin/v1/onboarding/applications/{app_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            for doc in details.json()["documents"]:
                api_client.post(
                    f"{base}/admin/v1/onboarding/documents/{doc['id']}/verify",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={"comment": "ok"},
                )

            approved = api_client.post(
                f"{base}/admin/client-onboarding/{app_id}/approve",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert approved.status_code == 200
            client_id = approved.json()["client_id"]

            client_token = _jwt(
                secret,
                roles=["CLIENT_OWNER"],
                aud="neft-client",
                iss="neft-client",
                sub="client-owner",
                extra={"client_id": client_id, "user_id": "client-owner", "subject_type": "client_user"},
            )

            me = api_client.get(f"{base}/client/me", headers={"Authorization": f"Bearer {client_token}"})
            assert me.status_code == 200
            payload = me.json()
            assert payload["org"] is not None
            assert payload["org_status"] == "ACTIVE"
