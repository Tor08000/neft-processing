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


def _email() -> str:
    return f"docs-{uuid.uuid4().hex[:8]}@example.com"


def _create(api_client: TestClient):
    response = api_client.post("/api/core/client/v1/onboarding/applications", json={"email": _email()})
    assert response.status_code == 200
    body = response.json()
    return body["application"]["id"], body["access_token"]


def test_upload_list_download_happy_path(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setattr(
        "app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env",
        lambda: _InMemoryStorage(),
    )

    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        files = {"file": ("sample.pdf", b"%PDF-1.7 test", "application/pdf")}
        upload = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/documents",
            files=files,
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert upload.status_code == 201
        doc_id = upload.json()["id"]

        listed = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{app_id}/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1

        download = api_client.get(
            f"/api/core/client/v1/onboarding/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert download.status_code == 200
    assert download.content == b"%PDF-1.7 test"
    assert download.headers["content-type"].startswith("application/pdf")


def test_access_control_forbidden(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setattr(
        "app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env",
        lambda: _InMemoryStorage(),
    )

    with TestClient(app) as api_client:
        app_a, token_a = _create(api_client)
        _, token_b = _create(api_client)
        files = {"file": ("sample.pdf", b"%PDF-1.7 test", "application/pdf")}
        upload = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_a}/documents",
            files=files,
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        doc_id = upload.json()["id"]

        forbidden = api_client.get(
            f"/api/core/client/v1/onboarding/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {token_b}"},
        )

    assert forbidden.status_code == 403


def test_upload_restricted_state(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setattr(
        "app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env",
        lambda: _InMemoryStorage(),
    )

    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        session = get_sessionmaker()()
        try:
            repo = ClientOnboardingRepository(db=session)
            application = repo.get_by_id(app_id)
            assert application is not None
            repo.update_draft(application, {"status": "IN_REVIEW"})
        finally:
            session.close()

        files = {"file": ("sample.pdf", b"%PDF-1.7 test", "application/pdf")}
        blocked = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/documents",
            files=files,
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert blocked.status_code == 409


def test_upload_mime_and_size(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    monkeypatch.setattr(
        "app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env",
        lambda: _InMemoryStorage(),
    )

    with TestClient(app) as api_client:
        app_id, token = _create(api_client)
        bad_mime = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/documents",
            files={"file": ("bad.txt", b"hello", "text/plain")},
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token}"},
        )
        too_big = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/documents",
            files={"file": ("big.pdf", b"0" * (1024 * 1024 + 1), "application/pdf")},
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert bad_mime.status_code == 415
    assert too_big.status_code == 413
