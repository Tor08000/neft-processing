from __future__ import annotations

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session, sessionmaker

import app.db as app_db
from app.domains.client.onboarding.documents.models import ClientDocument
from app.domains.client.onboarding.models import ClientOnboardingApplication
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.client_user_roles import ClientUserRole
from app.models.client_users import ClientUser
from app.models.fuel import FleetOfflineProfile
from app.services import admin_auth, client_auth
from app.tests.test_admin_onboarding_approve import _InMemoryStorage, _base_prefix, _create_and_submit_application, _jwt


@pytest.fixture(autouse=True)
def _sqlite_harness() -> None:
    engine = app_db.make_engine("sqlite://", schema="")
    testing_session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    old_engine = app_db._engine
    old_session_local = app_db._SessionLocal

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app_db._engine = engine
    app_db._SessionLocal = testing_session_local
    app.dependency_overrides[app_db.get_db] = override_get_db
    app_db.Base.metadata.create_all(
        bind=engine,
        tables=[
            FleetOfflineProfile.__table__,
            ClientOnboardingApplication.__table__,
            ClientDocument.__table__,
            Client.__table__,
            ClientUser.__table__,
            ClientUserRole.__table__,
            AuditLog.__table__,
        ],
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(app_db.get_db, None)
        app_db._engine = old_engine
        app_db._SessionLocal = old_session_local
        engine.dispose()


def test_set_roles_and_prevent_removing_last_owner(monkeypatch) -> None:
    secret = "users-roles-secret"
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "onboarding-secret")
    monkeypatch.setenv("CLIENT_TOKEN_SECRET", secret)
    monkeypatch.setenv("CLIENT_PUBLIC_KEY", secret)
    monkeypatch.setenv("ADMIN_PUBLIC_KEY", secret)
    monkeypatch.setenv("NEFT_AUTH_ALLOWED_ALGS", "HS256")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("NEFT_CLIENT_ISSUER", "neft-client")
    monkeypatch.setenv("NEFT_CLIENT_AUDIENCE", "neft-client")
    monkeypatch.setattr(admin_auth, "ALLOWED_ALGS", ["HS256"])
    monkeypatch.setattr(client_auth, "ALLOWED_ALGS", ["HS256"])
    monkeypatch.setattr(client_auth, "EXPECTED_ISSUER", "neft-client")
    monkeypatch.setattr(client_auth, "EXPECTED_AUDIENCE", "neft-client")
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

        with app_db._SessionLocal() as db:
            owner_user_ids = []
            for record in db.query(ClientUserRole).filter(ClientUserRole.client_id == client_id).all():
                record_roles = record.roles if isinstance(record.roles, list) else str(record.roles).split(",")
                normalized_roles = {str(item).upper() for item in record_roles if item}
                if "CLIENT_OWNER" in normalized_roles:
                    owner_user_ids.append(str(record.user_id))
        assert len(owner_user_ids) == 1
        initial_owner_user_id = owner_user_ids[0]

        create_owner = api_client.post(
            f"{base}/client/users/user-2/roles",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"roles": ["CLIENT_OWNER"]},
        )
        assert create_owner.status_code == 200
        assert create_owner.json()["roles"] == ["CLIENT_OWNER"]

        remove_secondary_owner = api_client.post(
            f"{base}/client/users/user-2/roles",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"roles": ["CLIENT_MANAGER"]},
        )
        assert remove_secondary_owner.status_code == 200
        assert remove_secondary_owner.json()["roles"] == ["CLIENT_MANAGER"]

        remove_last_owner = api_client.post(
            f"{base}/client/users/{initial_owner_user_id}/roles",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"roles": ["CLIENT_MANAGER"]},
        )
        assert remove_last_owner.status_code == 409
        assert "cannot_remove_last_owner" in remove_last_owner.text

        set_manager = api_client.post(
            f"{base}/client/users/user-3/roles",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"roles": ["CLIENT_MANAGER"]},
        )
        assert set_manager.status_code == 200
        assert set_manager.json()["roles"] == ["CLIENT_MANAGER"]
