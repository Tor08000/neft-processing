from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.domains.client.onboarding.repo import ClientOnboardingRepository
from app.domains.client.signing.repo import ClientSigningRepository
from app.main import app


class _InMemoryStorage:
    data: dict[tuple[str, str], bytes] = {}

    def ensure_bucket(self, bucket: str) -> None:
        return None

    def put_object(self, bucket: str, key: str, payload: bytes, content_type: str, metadata=None) -> None:
        self.data[(bucket, key)] = payload

    def get_object_stream(self, bucket: str, key: str):
        return io.BytesIO(self.data[(bucket, key)])


class _DocClient:
    def render_pdf(self, *, template_id: str, data: dict) -> bytes:
        return f"%PDF-1.7 {template_id} {data.get('application_id')}".encode()


def _email() -> str:
    return f"sign-docs-{uuid.uuid4().hex[:8]}@example.com"


def _create(api_client: TestClient):
    response = api_client.post("/api/core/client/v1/onboarding/applications", json={"email": _email()})
    assert response.status_code == 200
    body = response.json()
    return body["application"]["id"], body["access_token"]


def _move_to_in_review(app_id: str) -> None:
    session = get_sessionmaker()()
    try:
        repo = ClientOnboardingRepository(db=session)
        application = repo.get_by_id(app_id)
        assert application is not None
        repo.update_draft(application, {"status": "IN_REVIEW"})
    finally:
        session.close()


def _prepare_doc(api_client: TestClient, token: str, app_id: str) -> str:
    _move_to_in_review(app_id)
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
    monkeypatch.setenv("CLIENT_SIGN_MODE", "otp")
    monkeypatch.setenv("OTP_PROVIDER", "stub")
    monkeypatch.setenv("OTP_PROVIDER_STUB_ECHO_CODE", "1")
    monkeypatch.setenv("OTP_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setattr("app.routers.client_generated_docs_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.client_generated_docs_v1.DocumentServiceRenderClient", lambda: _DocClient())


def test_sign_request_creates_pending_otp(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, token, app_id)
        resp = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"phone": "+79990000000", "consent": True},
        )
        assert resp.status_code == 200
        assert resp.json()["request_id"]


def test_sign_confirm_success_marks_signed(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, token, app_id)
        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"phone": "+79990000000", "consent": True},
        )
        assert req.status_code == 200
        body = req.json()
        confirm = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"request_id": body["request_id"], "otp_code": body["otp_code"]},
        )
        assert confirm.status_code == 200
        doc = confirm.json()["doc"]
        assert doc["status"] == "SIGNED_BY_CLIENT"
        assert doc["client_signed_at"] is not None

        session = get_sessionmaker()()
        try:
            audit = ClientSigningRepository(session).list_audit_by_doc(doc_id)
            assert any(item.event_type == "DOC_SIGNED_BY_CLIENT" for item in audit)
        finally:
            session.close()


def test_cannot_sign_other_users_doc(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, token, app_id)
        _, token_other = _create(api_client)

        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/request",
            headers={"Authorization": f"Bearer {token_other}"},
            json={"phone": "+79990000000", "consent": True},
        )
        assert req.status_code == 403


def test_cannot_sign_twice(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, token, app_id)
        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"phone": "+79990000000", "consent": True},
        )
        body = req.json()
        confirm_1 = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"request_id": body["request_id"], "otp_code": body["otp_code"]},
        )
        assert confirm_1.status_code == 200
        confirm_2 = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"request_id": body["request_id"], "otp_code": body["otp_code"]},
        )
        assert confirm_2.status_code == 409
        assert confirm_2.json()["detail"]["reason_code"] == "already_signed"


def test_otp_attempts_limit(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, token, app_id)
        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"phone": "+79990000000", "consent": True},
        )
        request_id = req.json()["request_id"]

        for _ in range(5):
            bad = api_client.post(
                f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/confirm",
                headers={"Authorization": f"Bearer {token}"},
                json={"request_id": request_id, "otp_code": "000000"},
            )
        assert bad.status_code == 429

        blocked = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"request_id": request_id, "otp_code": "000000"},
        )
        assert blocked.status_code == 429


def test_expired_otp(monkeypatch) -> None:
    _set_signing_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, token, app_id)
        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"phone": "+79990000000", "consent": True},
        )
        assert req.status_code == 200
        request_id = req.json()["request_id"]

        session = get_sessionmaker()()
        try:
            repo = ClientSigningRepository(session)
            sign_req = repo.get_request(request_id)
            assert sign_req is not None
            sign_req.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
            session.add(sign_req)
            session.commit()
        finally:
            session.close()

        confirm = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"request_id": request_id, "otp_code": req.json()["otp_code"]},
        )
        assert confirm.status_code == 400
        assert confirm.json()["detail"]["reason_code"] == "otp_expired"
