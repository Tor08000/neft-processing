from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt

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
    return f"review-{uuid.uuid4().hex[:8]}@example.com"


def _jwt(secret: str, *, roles: list[str], aud: str, iss: str, sub: str = "user-1", extra: dict | None = None) -> str:
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


def _create_submit_with_docs(api_client: TestClient, base: str) -> tuple[str, str, list[str]]:
    created = api_client.post(f"{base}/client/v1/onboarding/applications", json={"email": _email()})
    assert created.status_code == 200
    app_id = created.json()["application"]["id"]
    token = created.json()["access_token"]

    patch = api_client.put(
        f"{base}/client/v1/onboarding/applications/{app_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"company_name": "ACME LLC", "inn": "7701234567", "org_type": "LEGAL", "ogrn": "1234567890123"},
    )
    assert patch.status_code == 200

    doc_ids: list[str] = []
    for doc_type in ("CHARTER", "EGRUL", "BANK_DETAILS"):
        upload = api_client.post(
            f"{base}/client/v1/onboarding/applications/{app_id}/documents",
            files={"file": (f"{doc_type}.pdf", b"%PDF-1.7 test", "application/pdf")},
            data={"doc_type": doc_type},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert upload.status_code == 201
        doc_ids.append(upload.json()["id"])

    submitted = api_client.post(
        f"{base}/client/v1/onboarding/applications/{app_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submitted.status_code == 200
    return app_id, token, doc_ids


def _setup_env(monkeypatch, secret: str = "review-secret") -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "onboarding-secret")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
    monkeypatch.setenv("NEFT_AUTH_ALLOWED_ALGS", "HS256")
    monkeypatch.setenv("ADMIN_PUBLIC_KEY", secret)
    monkeypatch.setenv("CLIENT_PUBLIC_KEY", secret)
    monkeypatch.setenv("CLIENT_TOKEN_SECRET", secret)
    monkeypatch.setenv("CLIENT_TOKEN_ALG", "HS256")
    monkeypatch.setattr(
        "app.routers.client_onboarding_documents_v1.OnboardingDocumentsStorage.from_env",
        lambda: _InMemoryStorage(),
    )
    monkeypatch.setattr(
        "app.routers.admin_onboarding_review_v1.OnboardingDocumentsStorage.from_env",
        lambda: _InMemoryStorage(),
    )


def test_onboarding_review_happy_path(monkeypatch) -> None:
    secret = "review-secret"
    _setup_env(monkeypatch, secret)
    admin_token = _jwt(secret, roles=["ADMIN"], aud="neft-admin", iss="neft-auth", sub="admin-1")

    with TestClient(app) as api_client:
        base = _base_prefix(api_client)
        app_id, onboarding_token, doc_ids = _create_submit_with_docs(api_client, base)

        started = api_client.post(
            f"{base}/admin/v1/onboarding/applications/{app_id}/start-review",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert started.status_code == 200

        for doc_id in doc_ids:
            verify = api_client.post(
                f"{base}/admin/v1/onboarding/documents/{doc_id}/verify",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"comment": "ok"},
            )
            assert verify.status_code == 200

        approved = api_client.post(
            f"{base}/admin/v1/onboarding/applications/{app_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "approved"},
        )
        assert approved.status_code == 200

        decision = api_client.get(
            f"{base}/client/v1/onboarding/my-application/decision",
            headers={"Authorization": f"Bearer {onboarding_token}"},
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "APPROVED"
        assert decision.json()["client_id"]

        token_issue = api_client.post(
            f"{base}/client/v1/onboarding/my-application/issue-client-token",
            headers={"Authorization": f"Bearer {onboarding_token}"},
        )
        assert token_issue.status_code == 200
        client_token = token_issue.json()["access_token"]

        me = api_client.get(f"{base}/client/v1/me", headers={"Authorization": f"Bearer {client_token}"})
        assert me.status_code == 200


def test_onboarding_review_reject_and_policy(monkeypatch) -> None:
    secret = "review-secret"
    _setup_env(monkeypatch, secret)
    admin_token = _jwt(secret, roles=["ADMIN"], aud="neft-admin", iss="neft-auth", sub="admin-1")

    with TestClient(app) as api_client:
        base = _base_prefix(api_client)
        app_id, onboarding_token, _doc_ids = _create_submit_with_docs(api_client, base)
        started = api_client.post(
            f"{base}/admin/v1/onboarding/applications/{app_id}/start-review",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert started.status_code == 200

        approve_without_verify = api_client.post(
            f"{base}/admin/v1/onboarding/applications/{app_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"comment": "approved"},
        )
        assert approve_without_verify.status_code == 409
        assert approve_without_verify.json()["detail"]["reason_code"] == "missing_verified_documents"

        rejected = api_client.post(
            f"{base}/admin/v1/onboarding/applications/{app_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "invalid papers"},
        )
        assert rejected.status_code == 200

        decision = api_client.get(
            f"{base}/client/v1/onboarding/my-application/decision",
            headers={"Authorization": f"Bearer {onboarding_token}"},
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "REJECTED"
        assert decision.json()["decision_reason"] == "invalid papers"

        token_issue = api_client.post(
            f"{base}/client/v1/onboarding/my-application/issue-client-token",
            headers={"Authorization": f"Bearer {onboarding_token}"},
        )
        assert token_issue.status_code == 409


def test_permissions_and_admin_download(monkeypatch) -> None:
    secret = "review-secret"
    _setup_env(monkeypatch, secret)
    admin_token = _jwt(secret, roles=["ADMIN"], aud="neft-admin", iss="neft-auth", sub="admin-1")
    client_like_token = _jwt(secret, roles=["CLIENT_OWNER"], aud="neft-admin", iss="neft-auth", sub="client-actor")

    with TestClient(app) as api_client:
        base = _base_prefix(api_client)
        _app_id, _onboarding_token, doc_ids = _create_submit_with_docs(api_client, base)

        forbidden = api_client.get(
            f"{base}/admin/v1/onboarding/applications",
            headers={"Authorization": f"Bearer {client_like_token}"},
        )
        assert forbidden.status_code == 403

        downloaded = api_client.get(
            f"{base}/admin/v1/onboarding/documents/{doc_ids[0]}/download",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert downloaded.status_code == 200
