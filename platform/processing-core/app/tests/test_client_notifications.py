from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.domains.client.onboarding.repo import ClientOnboardingRepository
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


def _setup_env(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("PLATFORM_DOC_SIGN_MODE", "mock")
    monkeypatch.setenv("CLIENT_SIGN_MODE", "otp")
    monkeypatch.setenv("OTP_PROVIDER_STUB_ECHO_CODE", "1")
    monkeypatch.setattr("app.routers.client_generated_docs_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.domains.client.docflow.service.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.client_generated_docs_v1.DocumentServiceRenderClient", lambda: _DocClient())


def _create(api_client: TestClient) -> tuple[str, str]:
    email = f"notify-{uuid.uuid4().hex[:8]}@example.com"
    response = api_client.post("/api/core/client/v1/onboarding/applications", json={"email": email})
    body = response.json()
    return body["application"]["id"], body["access_token"]


def _move_to_in_review(app_id: str) -> None:
    session = get_sessionmaker()()
    try:
        repo = ClientOnboardingRepository(db=session)
        app_row = repo.get_by_id(app_id)
        assert app_row is not None
        repo.update_draft(app_row, {"status": "IN_REVIEW"})
    finally:
        session.close()


def test_sign_event_creates_notification_and_mark_read(monkeypatch) -> None:
    _setup_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        _move_to_in_review(app_id)
        api_client.post(f"/api/core/client/v1/onboarding/applications/{app_id}/generate-docs", headers={"Authorization": f"Bearer {token}"})
        doc_id = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{app_id}/generated-docs",
            headers={"Authorization": f"Bearer {token}"},
        ).json()["items"][0]["id"]
        req = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"phone": "+79990000000", "consent": True},
        ).json()
        api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"request_id": req["request_id"], "otp_code": req["otp_code"]},
        )

        listed = api_client.get("/api/core/client/docflow/notifications", headers={"Authorization": f"Bearer {token}"})
        assert listed.status_code == 200
        assert listed.json()["unread_count"] >= 1
        nid = listed.json()["items"][0]["id"]

        marked = api_client.post(f"/api/core/client/docflow/notifications/{nid}/read", headers={"Authorization": f"Bearer {token}"})
        assert marked.status_code == 200
        assert marked.json()["read_at"] is not None
