from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.main import app
from app.models.client_invitations import ClientInvitation
from app.models.invitation_email_deliveries import InvitationEmailDelivery
from app.models.notification_outbox import NotificationOutbox
from app.models.notifications import NotificationSubjectType
from app.tests.test_admin_onboarding_approve import (
    _InMemoryStorage,
    _base_prefix,
    _configure_onboarding_test_env,
    _create_and_submit_application,
    _jwt,
    onboarding_sqlite_harness,
)


def _setup(monkeypatch) -> tuple[str, TestClient, str]:
    secret = "users-invite-secret"
    _configure_onboarding_test_env(monkeypatch, secret)
    monkeypatch.setattr("app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.admin_onboarding_review_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    return secret


def test_invite_user_creates_pending_and_prevents_duplicates(monkeypatch) -> None:
    secret = _setup(monkeypatch)

    with onboarding_sqlite_harness(
        ClientInvitation.__table__,
        NotificationOutbox.__table__,
        InvitationEmailDelivery.__table__,
    ):
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

            session = get_sessionmaker()()
            outbox_rows = session.query(NotificationOutbox).filter(NotificationOutbox.aggregate_id == resp.json()["invitation_id"]).all()
            assert outbox_rows
            assert {row.subject_type for row in outbox_rows} == {NotificationSubjectType.CLIENT}
            assert {str(row.subject_id) for row in outbox_rows} == {client_id}
            assert all(row.template_code for row in outbox_rows)
            assert all(row.priority for row in outbox_rows)
            assert all(row.dedupe_key for row in outbox_rows)
            session.close()

            duplicate = api_client.post(
                f"{base}/client/users/invite",
                headers={"Authorization": f"Bearer {token}"},
                json={"email": "new.user@example.com", "roles": ["CLIENT_VIEWER"]},
            )
            assert duplicate.status_code == 409
