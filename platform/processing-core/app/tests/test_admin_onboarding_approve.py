from __future__ import annotations

from contextlib import contextmanager
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session, sessionmaker

import app.db as app_db
from app.api.dependencies.admin import require_admin_user
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.client_user_roles import ClientUserRole
from app.models.client_users import ClientUser
from app.models.fuel import FleetOfflineProfile
from app.domains.client.onboarding.documents.models import ClientDocument
from app.domains.client.onboarding.models import ClientOnboardingApplication
from app.services import admin_auth, client_auth, partner_auth


class _InMemoryStorage:
    data: dict[tuple[str, str], bytes] = {}

    def ensure_bucket(self, bucket: str) -> None:
        return None

    def put_object(self, bucket: str, key: str, payload: bytes, content_type: str, metadata=None) -> None:
        self.data[(bucket, key)] = payload

    def get_object_stream(self, bucket: str, key: str):
        import io

        return io.BytesIO(self.data[(bucket, key)])


def _jwt(secret: str, *, roles: list[str], aud: str, iss: str, sub: str, extra: dict | None = None) -> str:
    payload = {
        "sub": sub,
        "roles": roles,
        "role": roles[0] if roles else None,
        "aud": aud,
        "iss": iss,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm="HS256")


def _base_prefix(api_client: TestClient) -> str:
    for prefix in ("/api/core", "/api"):
        probe = api_client.get(f"{prefix}/client/v1/health")
        if probe.status_code != 404:
            return prefix
    return "/api/core"


def _configure_onboarding_test_env(monkeypatch, secret: str) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "onboarding-secret")
    monkeypatch.setenv("CLIENT_TOKEN_SECRET", secret)
    monkeypatch.setenv("CLIENT_PUBLIC_KEY", secret)
    monkeypatch.setenv("ADMIN_PUBLIC_KEY", secret)
    monkeypatch.setenv("NEFT_AUTH_ALLOWED_ALGS", "HS256")
    monkeypatch.setenv("NEFT_CLIENT_ISSUER", "neft-client")
    monkeypatch.setenv("NEFT_CLIENT_AUDIENCE", "neft-client")
    monkeypatch.setattr(admin_auth, "ALLOWED_ALGS", ["HS256"])
    monkeypatch.setattr(client_auth, "ALLOWED_ALGS", ["HS256"])
    monkeypatch.setattr(client_auth, "EXPECTED_ISSUER", "neft-client")
    monkeypatch.setattr(client_auth, "EXPECTED_AUDIENCE", "neft-client")
    monkeypatch.setattr(partner_auth, "ALLOWED_ALGS", ["HS256"])


ONBOARDING_BASE_TEST_TABLES = (
    FleetOfflineProfile.__table__,
    Client.__table__,
    ClientOnboardingApplication.__table__,
    ClientDocument.__table__,
    ClientUser.__table__,
    ClientUserRole.__table__,
    AuditLog.__table__,
)


def _admin_onboarding_claims() -> dict[str, object]:
    return {
        "sub": "admin-1",
        "user_id": "admin-1",
        "roles": ["ADMIN"],
        "role": "ADMIN",
    }


@contextmanager
def onboarding_sqlite_harness(*extra_tables):
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

    tables = list(dict.fromkeys([*ONBOARDING_BASE_TEST_TABLES, *extra_tables]))
    app_db._engine = engine
    app_db._SessionLocal = testing_session_local
    app.dependency_overrides[app_db.get_db] = override_get_db
    app.dependency_overrides[require_admin_user] = _admin_onboarding_claims
    app_db.Base.metadata.create_all(bind=engine, tables=tables)
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin_user, None)
        app.dependency_overrides.pop(app_db.get_db, None)
        app_db._engine = old_engine
        app_db._SessionLocal = old_session_local
        engine.dispose()


def _create_and_submit_application(api_client: TestClient, base: str) -> str:
    email = f"approve-{uuid.uuid4().hex[:8]}@example.com"
    created = api_client.post(f"{base}/client/v1/onboarding/applications", json={"email": email})
    assert created.status_code == 200
    app_id = created.json()["application"]["id"]
    token = created.json()["access_token"]

    patched = api_client.put(
        f"{base}/client/v1/onboarding/applications/{app_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"company_name": "ACME LLC", "inn": "7701234567", "org_type": "LEGAL", "ogrn": "1234567890123"},
    )
    assert patched.status_code == 200

    for doc_type in ("CHARTER", "EGRUL", "BANK_DETAILS"):
        upload = api_client.post(
            f"{base}/client/v1/onboarding/applications/{app_id}/documents",
            files={"file": (f"{doc_type}.pdf", b"%PDF-1.7", "application/pdf")},
            data={"doc_type": doc_type},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert upload.status_code == 201

    submitted = api_client.post(
        f"{base}/client/v1/onboarding/applications/{app_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submitted.status_code == 200
    return app_id


def test_admin_approve_creates_client_and_membership(monkeypatch) -> None:
    secret = "approve-secret"
    _configure_onboarding_test_env(monkeypatch, secret)
    monkeypatch.setattr("app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.admin_onboarding_review_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())

    admin_token = _jwt(secret, roles=["ADMIN"], aud="neft-admin", iss="neft-auth", sub="admin-1")

    with onboarding_sqlite_harness():
        with TestClient(app) as api_client:
            base = _base_prefix(api_client)
            app_id = _create_and_submit_application(api_client, base)

            started = api_client.post(
                f"{base}/admin/v1/onboarding/applications/{app_id}/start-review",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert started.status_code == 200

            details = api_client.get(
                f"{base}/admin/v1/onboarding/applications/{app_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            for doc in details.json()["documents"]:
                verify = api_client.post(
                    f"{base}/admin/v1/onboarding/documents/{doc['id']}/verify",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={"comment": "ok"},
                )
                assert verify.status_code == 200

            approved = api_client.post(
                f"{base}/admin/client-onboarding/{app_id}/approve",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert approved.status_code == 200
            payload = approved.json()
            assert payload["application_id"] == app_id
            assert payload["status"] == "APPROVED"
            assert payload["client_id"]

            approved_again = api_client.post(
                f"{base}/admin/client-onboarding/{app_id}/approve",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert approved_again.status_code == 409
