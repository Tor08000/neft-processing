from __future__ import annotations

import io
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.domains.client.onboarding.repo import ClientOnboardingRepository
from app.domains.client.signing.repo import ClientSigningRepository
from app.routers.client_v1 import router as client_v1_router


class _InMemoryStorage:
    data: dict[tuple[str, str], bytes] = {}

    def ensure_bucket(self, bucket: str) -> None:
        return None

    def put_object(self, bucket: str, key: str, payload: bytes, content_type: str, metadata=None) -> None:
        self.data[(bucket, key)] = payload

    def get_object_stream(self, bucket: str, key: str):
        return io.BytesIO(self.data[(bucket, key)])


class _DocClient:
    def render_pdf(self, *, template_id: str, data: dict, **_kwargs) -> bytes:
        return f"%PDF-1.7 {template_id} {data.get('application_id')}".encode()


class _OtpResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"provider_message_id": "msg-1", "status": "sent"}


def _bootstrap_signing_schema(engine) -> None:
    ddl = (
        """
        CREATE TABLE client_onboarding_applications (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            phone TEXT,
            company_name TEXT,
            inn TEXT,
            ogrn TEXT,
            org_type TEXT,
            status TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            created_by_user_id TEXT,
            submitted_at DATETIME,
            reviewed_by_user_id TEXT,
            approved_by_user_id TEXT,
            reviewed_at DATETIME,
            decision_reason TEXT,
            client_id TEXT,
            approved_at DATETIME,
            rejected_at DATETIME
        )
        """,
        """
        CREATE TABLE client_generated_documents (
            id TEXT PRIMARY KEY,
            client_application_id TEXT,
            client_id TEXT,
            doc_kind TEXT NOT NULL,
            version INTEGER NOT NULL,
            storage_key TEXT NOT NULL,
            filename TEXT NOT NULL,
            mime TEXT NOT NULL,
            size BIGINT,
            status TEXT NOT NULL,
            template_id TEXT,
            checksum_sha256 TEXT,
            created_by_user_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            platform_signed_at DATETIME,
            platform_signature_hash TEXT,
            client_signed_at DATETIME,
            client_sign_method TEXT,
            client_sign_phone TEXT,
            client_signature_hash TEXT
        )
        """,
        """
        CREATE TABLE otp_challenges (
            id TEXT PRIMARY KEY,
            purpose TEXT NOT NULL,
            document_id TEXT NOT NULL,
            client_id TEXT,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            destination TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            expires_at DATETIME NOT NULL,
            resend_available_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            used_at DATETIME,
            request_ip TEXT,
            request_user_agent TEXT,
            provider_message_id TEXT,
            provider_meta TEXT,
            error_code TEXT
        )
        """,
        """
        CREATE TABLE client_audit_events (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            application_id TEXT,
            doc_id TEXT,
            event_type TEXT NOT NULL,
            actor_user_id TEXT,
            actor_type TEXT,
            ip TEXT,
            user_agent TEXT,
            meta_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE client_docflow_notifications (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            user_id TEXT,
            channel TEXT NOT NULL DEFAULT 'in_app',
            body TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL DEFAULT 'INFO',
            meta_json TEXT NOT NULL DEFAULT '{}',
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            severity TEXT NOT NULL DEFAULT 'INFO',
            is_read BOOLEAN NOT NULL DEFAULT 0,
            read_at DATETIME,
            dedupe_key TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """,
    )
    with engine.begin() as conn:
        for statement in ddl:
            conn.execute(text(statement))


@contextmanager
def _api_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _bootstrap_signing_schema(engine)
    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    app = FastAPI()
    app.include_router(client_v1_router, prefix="/api/core")

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as api_client:
        yield api_client, session_factory
    engine.dispose()


def _email() -> str:
    return f"sign-docs-{uuid.uuid4().hex[:8]}@example.com"


def _create(api_client: TestClient):
    response = api_client.post("/api/core/client/v1/onboarding/applications", json={"email": _email()})
    assert response.status_code == 200
    body = response.json()
    return body["application"]["id"], body["access_token"]


def _move_to_in_review(session_factory, app_id: str) -> None:
    db = session_factory()
    try:
        repo = ClientOnboardingRepository(db=db)
        application = repo.get_by_id(app_id)
        assert application is not None
        repo.update_draft(application, {"status": "IN_REVIEW"})
    finally:
        db.close()


def _prepare_doc(api_client: TestClient, session_factory, token: str, app_id: str) -> str:
    _move_to_in_review(session_factory, app_id)
    generated = api_client.post(
        f"/api/core/client/v1/onboarding/applications/{app_id}/generate-docs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert generated.status_code == 200
    listed = api_client.get(
        f"/api/core/client/v1/onboarding/applications/{app_id}/generated-docs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    return listed.json()["items"][0]["id"]


def _set_signing_env(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("PLATFORM_DOC_SIGN_MODE", "mock")
    monkeypatch.setenv("OTP_TEST_MODE", "1")
    monkeypatch.setenv("OTP_ENABLED", "1")
    monkeypatch.setenv("OTP_SERVER_PEPPER", "pepper")
    monkeypatch.setenv("OTP_FORCE_REAUTH_SECONDS", "999999")
    monkeypatch.setenv("OTP_RATE_LIMIT_PER_USER_PER_MINUTE", "10")
    monkeypatch.setenv("OTP_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("INTEGRATION_HUB_URL", "http://hub.local")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setattr(
        "app.routers.client_generated_docs_v1.OnboardingDocumentsStorage.from_env",
        lambda: _InMemoryStorage(),
    )
    monkeypatch.setattr("app.routers.client_generated_docs_v1.DocumentServiceRenderClient", lambda: _DocClient())
    monkeypatch.setattr("app.domains.client.signing.service.requests.post", lambda *args, **kwargs: _OtpResponse())


def test_sign_request_creates_pending_otp(monkeypatch) -> None:
    _set_signing_env(monkeypatch)

    def _capture_otp_send(*args, **kwargs):
        raise AssertionError("OTP_TEST_MODE must not call external OTP transport")

    monkeypatch.setattr("app.domains.client.signing.service.requests.post", _capture_otp_send)
    with _api_client() as (api_client, session_factory):
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, session_factory, token, app_id)
        resp = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["challenge_id"]
        assert body["otp_code"] == "000000"

        db = session_factory()
        try:
            challenge = ClientSigningRepository(db).get_challenge(body["challenge_id"])
            assert challenge is not None
            assert challenge.status == "SENT"
            assert challenge.client_id is None
            assert challenge.provider_message_id == f"otp-test:{body['challenge_id']}"
        finally:
            db.close()


def test_sign_confirm_success_marks_signed(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with _api_client() as (api_client, session_factory):
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, session_factory, token, app_id)
        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        assert req.status_code == 200
        body = req.json()
        confirm = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": body["challenge_id"], "code": body["otp_code"]},
        )
        assert confirm.status_code == 200
        doc = confirm.json()["doc"]
        assert doc["status"] == "SIGNED_BY_CLIENT"
        assert doc["client_signed_at"] is not None

        db = session_factory()
        try:
            audit = ClientSigningRepository(db).list_audit_by_doc(doc_id)
            assert any(item.event_type == "DOC_SIGNED_BY_CLIENT" for item in audit)
            notification = db.execute(
                text(
                    "SELECT channel, body, event_type, kind, message "
                    "FROM client_docflow_notifications "
                    "WHERE event_type = 'DOC_SIGNED_BY_CLIENT'"
                )
            ).mappings().first()
            assert notification is not None
            assert notification["channel"] == "in_app"
            assert notification["body"] == notification["message"]
            assert notification["kind"] == "DOC_SIGNED_BY_CLIENT"
        finally:
            db.close()


def test_cannot_sign_other_users_doc(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with _api_client() as (api_client, session_factory):
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, session_factory, token, app_id)
        _, token_other = _create(api_client)

        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token_other}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        assert req.status_code == 403
        assert req.json()["detail"]["reason_code"] == "onboarding_token_app_mismatch"


def test_cannot_sign_twice(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with _api_client() as (api_client, session_factory):
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, session_factory, token, app_id)
        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        body = req.json()
        confirm_1 = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": body["challenge_id"], "code": body["otp_code"]},
        )
        assert confirm_1.status_code == 200
        confirm_2 = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": body["challenge_id"], "code": body["otp_code"]},
        )
        assert confirm_2.status_code == 409
        assert confirm_2.json()["detail"]["error_code"] == "already_signed"


def test_otp_attempts_limit(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with _api_client() as (api_client, session_factory):
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, session_factory, token, app_id)
        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        challenge_id = req.json()["challenge_id"]

        for _ in range(5):
            bad = api_client.post(
                f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
                headers={"Authorization": f"Bearer {token}"},
                json={"challenge_id": challenge_id, "code": "111111"},
            )
        assert bad.status_code == 429
        assert bad.json()["detail"]["error_code"] == "otp_locked"

        blocked = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": challenge_id, "code": "111111"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["detail"]["error_code"] == "otp_locked"

        db = session_factory()
        try:
            challenge = ClientSigningRepository(db).get_challenge(challenge_id)
            assert challenge is not None
            assert challenge.status == "LOCKED"
        finally:
            db.close()


def test_expired_otp(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with _api_client() as (api_client, session_factory):
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, session_factory, token, app_id)
        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        assert req.status_code == 200
        challenge_id = req.json()["challenge_id"]

        db = session_factory()
        try:
            repo = ClientSigningRepository(db)
            challenge = repo.get_challenge(challenge_id)
            assert challenge is not None
            challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
            db.add(challenge)
            db.commit()
        finally:
            db.close()

        confirm = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": challenge_id, "code": req.json()["otp_code"]},
        )
        assert confirm.status_code == 400
        assert confirm.json()["detail"]["error_code"] == "otp_expired"
