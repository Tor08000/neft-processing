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
    return f"gen-docs-{uuid.uuid4().hex[:8]}@example.com"


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


def test_generated_docs_happy_path_and_access_control(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("PLATFORM_DOC_SIGN_MODE", "mock")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setattr("app.routers.client_generated_docs_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.client_generated_docs_v1.DocumentServiceRenderClient", lambda: _DocClient())

    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        _move_to_in_review(app_id)

        generated = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert generated.status_code == 200
        assert len(generated.json()["items"]) == 3

        listed = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{app_id}/generated-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 3
        doc_id = listed.json()["items"][0]["id"]

        download = api_client.get(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF-1.7")

        _, token_other = _create(api_client)
        forbidden = api_client.get(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/download",
            headers={"Authorization": f"Bearer {token_other}"},
        )
        assert forbidden.status_code == 403


def test_generated_docs_versioning(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("PLATFORM_DOC_SIGN_MODE", "mock")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setattr("app.routers.client_generated_docs_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.client_generated_docs_v1.DocumentServiceRenderClient", lambda: _DocClient())

    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        _move_to_in_review(app_id)
        first = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 200
        second = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 200

        listed = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{app_id}/generated-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        versions = sorted({(item["doc_kind"], item["version"]) for item in listed.json()["items"]})
        assert ("OFFER", 1) in versions
        assert ("OFFER", 2) in versions


def test_generated_docs_prod_mode_without_sign(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("PLATFORM_DOC_SIGN_MODE", "disabled")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setattr("app.routers.client_generated_docs_v1.OnboardingDocumentsStorage.from_env", lambda: _InMemoryStorage())
    monkeypatch.setattr("app.routers.client_generated_docs_v1.DocumentServiceRenderClient", lambda: _DocClient())

    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        _move_to_in_review(app_id)
        generated = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert generated.status_code == 200
    statuses = {item["status"] for item in generated.json()["items"]}
    assert statuses == {"GENERATED"}
