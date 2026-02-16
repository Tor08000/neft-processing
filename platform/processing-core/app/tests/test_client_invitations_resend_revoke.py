from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.main import app
from app.models.client_portal import ClientInvitation, NotificationOutbox
from app.tests.test_admin_onboarding_approve import _InMemoryStorage, _base_prefix, _create_and_submit_application, _jwt


def _setup(monkeypatch) -> str:
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


def _bootstrap_client(api_client: TestClient, secret: str) -> tuple[str, str, str]:
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
    manager_token = _jwt(
        secret,
        roles=["CLIENT_MANAGER"],
        aud="neft-client",
        iss="neft-client",
        sub="manager-1",
        extra={"client_id": client_id, "user_id": "manager-1", "subject_type": "client_user"},
    )
    return base, owner_token, manager_token


def _create_invite(api_client: TestClient, base: str, token: str, email: str = "new.user@example.com") -> str:
    resp = api_client.post(
        f"{base}/client/users/invite",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": email, "roles": ["CLIENT_MANAGER"]},
    )
    assert resp.status_code == 201
    return resp.json()["invitation_id"]


def test_revoke_and_resend_and_permissions(monkeypatch) -> None:
    secret = _setup(monkeypatch)

    with TestClient(app) as api_client:
        base, owner_token, manager_token = _bootstrap_client(api_client, secret)
        invitation_id = _create_invite(api_client, base, owner_token)

        resend = api_client.post(
            f"{base}/client/users/invitations/{invitation_id}/resend",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"expires_in_days": 10},
        )
        assert resend.status_code == 200
        assert resend.json()["status"] == "PENDING"
        assert resend.json()["resent_count"] == 1

        session = get_sessionmaker()()
        invitation = session.query(ClientInvitation).filter(ClientInvitation.id == invitation_id).one()
        first_hash = invitation.token_hash
        assert int(invitation.resent_count or 0) == 1

        outbox_events = session.query(NotificationOutbox).filter(NotificationOutbox.aggregate_id == invitation_id).all()
        event_types = {item.event_type for item in outbox_events}
        assert "INVITATION_CREATED" in event_types
        assert "INVITATION_RESENT" in event_types

        forbidden = api_client.post(
            f"{base}/client/users/invitations/{invitation_id}/resend",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert forbidden.status_code == 403

        revoke = api_client.post(
            f"{base}/client/users/invitations/{invitation_id}/revoke",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"reason": "manual"},
        )
        assert revoke.status_code == 200
        assert revoke.json()["status"] == "REVOKED"

        session.refresh(invitation)
        assert invitation.status == "REVOKED"
        assert invitation.revoked_by_user_id == "owner-1"

        revoke_again = api_client.post(
            f"{base}/client/users/invitations/{invitation_id}/revoke",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert revoke_again.status_code == 409

        resend_revoked = api_client.post(
            f"{base}/client/users/invitations/{invitation_id}/resend",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resend_revoked.status_code == 409

        outbox_events = session.query(NotificationOutbox).filter(NotificationOutbox.aggregate_id == invitation_id).all()
        event_types = {item.event_type for item in outbox_events}
        assert "INVITATION_REVOKED" in event_types

        invitations_resp = api_client.get(f"{base}/client/users/invitations", headers={"Authorization": f"Bearer {owner_token}"})
        assert invitations_resp.status_code == 200
        assert invitations_resp.json()["items"]
        session.close()
