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
    return f"otp-docs-{uuid.uuid4().hex[:8]}@example.com"


def _create(api_client: TestClient):
    response = api_client.post("/api/core/client/v1/onboarding/applications", json={"email": _email()})
    body = response.json()
    return body["application"]["id"], body["access_token"]


def _move_to_in_review(app_id: str) -> None:
    session = get_sessionmaker()()
    try:
        repo = ClientOnboardingRepository(db=session)
        application = repo.get_by_id(app_id)
        repo.update_draft(application, {"status": "IN_REVIEW"})
    finally:
        session.close()


def _prepare_doc(api_client: TestClient, token: str, app_id: str) -> str:
    _move_to_in_review(app_id)
    api_client.post(f"/api/core/client/v1/onboarding/applications/{app_id}/generate-docs", headers={"Authorization": f"Bearer {token}"})
    listed = api_client.get(f"/api/core/client/v1/onboarding/applications/{app_id}/generated-docs", headers={"Authorization": f"Bearer {token}"})
    return listed.json()["items"][0]["id"]


def _set_env(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("OTP_TEST_MODE", "1")
    monkeypatch.setenv("OTP_ENABLED", "1")
    monkeypatch.setenv("OTP_SERVER_PEPPER", "pepper")
    monkeypatch.setenv("OTP_RATE_LIMIT_PER_USER_PER_MINUTE", "3")
    monkeypatch.setenv("OTP_FORCE_REAUTH_SECONDS", "999999")
    monkeypatch.setenv("OTP_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("INTEGRATION_HUB_URL", "http://hub.local")
    monkeypatch.setattr("app.routers.client_generated_docs_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.client_generated_docs_v1.DocumentServiceRenderClient", lambda: _DocClient())

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"provider_message_id": "msg-1", "status": "sent"}

    monkeypatch.setattr("app.domains.client.signing.service.requests.post", lambda *args, **kwargs: _Resp())


def test_start_and_confirm_otp(monkeypatch) -> None:
    _set_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, token, app_id)
        start = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        assert start.status_code == 200
        body = start.json()
        confirm = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": body["challenge_id"], "code": "000000"},
        )
        assert confirm.status_code == 200
        assert confirm.json()["doc"]["status"] == "SIGNED_BY_CLIENT"


def test_wrong_code_locks(monkeypatch) -> None:
    _set_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, token, app_id)
        start = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        cid = start.json()["challenge_id"]
        bad1 = api_client.post(f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm", headers={"Authorization": f"Bearer {token}"}, json={"challenge_id": cid, "code": "111111"})
        assert bad1.status_code == 400
        bad2 = api_client.post(f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm", headers={"Authorization": f"Bearer {token}"}, json={"challenge_id": cid, "code": "111111"})
        assert bad2.status_code == 429

        session = get_sessionmaker()()
        try:
            ch = ClientSigningRepository(session).get_challenge(cid)
            assert ch is not None
            assert ch.status == "LOCKED"
        finally:
            session.close()


def test_expired(monkeypatch) -> None:
    _set_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        doc_id = _prepare_doc(api_client, token, app_id)
        start = api_client.post(f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start", headers={"Authorization": f"Bearer {token}"}, json={"channel": "sms", "destination": "+79990000000"})
        cid = start.json()["challenge_id"]

        session = get_sessionmaker()()
        try:
            repo = ClientSigningRepository(session)
            ch = repo.get_challenge(cid)
            ch.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.add(ch)
            session.commit()
        finally:
            session.close()

        confirm = api_client.post(f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm", headers={"Authorization": f"Bearer {token}"}, json={"challenge_id": cid, "code": "000000"})
        assert confirm.status_code == 400
        assert confirm.json()["detail"]["error_code"] == "otp_expired"
