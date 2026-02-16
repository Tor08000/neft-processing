from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.tests.test_admin_onboarding_approve import _InMemoryStorage, _base_prefix, _create_and_submit_application, _jwt


def test_set_roles_and_prevent_removing_last_owner(monkeypatch) -> None:
    secret = "users-roles-secret"
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "onboarding-secret")
    monkeypatch.setenv("CLIENT_TOKEN_SECRET", secret)
    monkeypatch.setenv("CLIENT_PUBLIC_KEY", secret)
    monkeypatch.setenv("ADMIN_PUBLIC_KEY", secret)
    monkeypatch.setenv("NEFT_AUTH_ALLOWED_ALGS", "HS256")
    monkeypatch.setattr("app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.admin_onboarding_review_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())

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

        owner_token = _jwt(
            secret,
            roles=["CLIENT_OWNER"],
            aud="neft-client",
            iss="neft-client",
            sub="owner-1",
            extra={"client_id": client_id, "user_id": "owner-1", "subject_type": "client_user"},
        )

        create_owner = api_client.post(
            f"{base}/client/users/user-2/roles",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"roles": ["CLIENT_OWNER"]},
        )
        assert create_owner.status_code == 200

        remove_last_owner = api_client.post(
            f"{base}/client/users/user-2/roles",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"roles": ["CLIENT_MANAGER"]},
        )
        assert remove_last_owner.status_code == 409

        set_manager = api_client.post(
            f"{base}/client/users/user-3/roles",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"roles": ["CLIENT_MANAGER"]},
        )
        assert set_manager.status_code == 200
        assert set_manager.json()["roles"] == ["CLIENT_MANAGER"]
