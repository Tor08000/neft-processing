from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.main import app
from app.models.client_portal import ClientInvitation
from app.tests.test_admin_onboarding_approve import _InMemoryStorage, _base_prefix, _create_and_submit_application, _jwt


def _setup(monkeypatch, *, throttle_minutes: int = 0) -> str:
    secret = "users-invite-secret"
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "onboarding-secret")
    monkeypatch.setenv("CLIENT_TOKEN_SECRET", secret)
    monkeypatch.setenv("CLIENT_PUBLIC_KEY", secret)
    monkeypatch.setenv("ADMIN_PUBLIC_KEY", secret)
    monkeypatch.setenv("NEFT_AUTH_ALLOWED_ALGS", "HS256")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("CLIENT_INVITE_RESEND_THROTTLE_MINUTES", str(throttle_minutes))
    monkeypatch.setattr("app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.admin_onboarding_review_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    return secret


def _bootstrap_client(api_client: TestClient, secret: str) -> tuple[str, str]:
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
    return base, owner_token


def test_client_invitations_flow(monkeypatch) -> None:
    secret = _setup(monkeypatch, throttle_minutes=3)

    with TestClient(app) as api_client:
        base, owner_token = _bootstrap_client(api_client, secret)

        empty_list = api_client.get(f"{base}/client/users/invitations", headers={"Authorization": f"Bearer {owner_token}"})
        assert empty_list.status_code == 200
        assert empty_list.json()["items"] == []

        create = api_client.post(
            f"{base}/client/users/invite",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"email": "new.user@example.com", "roles": ["CLIENT_MANAGER"]},
        )
        assert create.status_code == 201
        invitation_id = create.json()["invitation_id"]
        invitation_token = create.json()["token"]

        listed = api_client.get(
            f"{base}/client/users/invitations?status=PENDING&sort=created_at_desc&limit=10&offset=0",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1
        assert listed.json()["items"][0]["status"] == "PENDING"

        session = get_sessionmaker()()
        invitation = session.query(ClientInvitation).filter(ClientInvitation.id == invitation_id).one()
        before_sent = invitation.last_sent_at
        session.close()

        resend = api_client.post(
            f"{base}/client/users/invitations/{invitation_id}/resend",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"expires_in_days": 7},
        )
        assert resend.status_code == 429

        session = get_sessionmaker()()
        invitation = session.query(ClientInvitation).filter(ClientInvitation.id == invitation_id).one()
        invitation.last_sent_at = datetime.now(timezone.utc).replace(year=2020)
        session.commit()
        session.close()

        resend = api_client.post(
            f"{base}/client/users/invitations/{invitation_id}/resend",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"expires_in_days": 7},
        )
        assert resend.status_code == 200

        session = get_sessionmaker()()
        invitation = session.query(ClientInvitation).filter(ClientInvitation.id == invitation_id).one()
        assert int(invitation.resent_count or 0) == 1
        assert invitation.last_sent_at is not None
        assert invitation.last_sent_at != before_sent

        revoke = api_client.post(
            f"{base}/client/users/invitations/{invitation_id}/revoke",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert revoke.status_code == 200
        session.refresh(invitation)
        assert invitation.status == "REVOKED"

        accept = api_client.post(f"{base}/auth/invitations/accept", json={"token": invitation_token})
        assert accept.status_code == 409
        assert accept.json()["detail"] == "invite_revoked"
        session.close()
