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


def _email() -> str:
    return f"docflow-{uuid.uuid4().hex[:8]}@example.com"


def _setup_env(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("PLATFORM_DOC_SIGN_MODE", "mock")
    monkeypatch.setenv("CLIENT_SIGN_MODE", "otp")
    monkeypatch.setenv("OTP_PROVIDER_STUB_ECHO_CODE", "1")
    monkeypatch.setattr("app.routers.client_generated_docs_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.domains.client.docflow.service.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.client_generated_docs_v1.DocumentServiceRenderClient", lambda: _DocClient())




def _move_to_in_review(app_id: str) -> None:
    session = get_sessionmaker()()
    try:
        repo = ClientOnboardingRepository(db=session)
        application = repo.get_by_id(app_id)
        assert application is not None
        repo.update_draft(application, {"status": "IN_REVIEW"})
    finally:
        session.close()

def _create_application(api_client: TestClient) -> tuple[str, str]:
    response = api_client.post("/api/core/client/v1/onboarding/applications", json={"email": _email()})
    body = response.json()
    return body["application"]["id"], body["access_token"]


def test_timeline_contains_sign_and_effective_events(monkeypatch) -> None:
    _setup_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, token = _create_application(api_client)
        _move_to_in_review(app_id)
        api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        docs = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{app_id}/generated-docs",
            headers={"Authorization": f"Bearer {token}"},
        ).json()["items"]
        doc_id = docs[0]["id"]
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

        timeline = api_client.get(
            f"/api/core/client/docflow/timeline?application_id={app_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert timeline.status_code == 200
        event_types = [item["event_type"] for item in timeline.json()["items"]]
        assert "DOC_SIGNED_BY_CLIENT" in event_types
        assert "DOC_EFFECTIVE" in event_types


def test_timeline_forbidden_for_other_application(monkeypatch) -> None:
    _setup_env(monkeypatch)
    with TestClient(app) as api_client:
        app_id, _ = _create_application(api_client)
        _, token_other = _create_application(api_client)
        forbidden = api_client.get(
            f"/api/core/client/docflow/timeline?application_id={app_id}",
            headers={"Authorization": f"Bearer {token_other}"},
        )
        assert forbidden.status_code == 403
