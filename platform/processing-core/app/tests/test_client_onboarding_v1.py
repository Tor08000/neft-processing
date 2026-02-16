from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app


def _email() -> str:
    return f"onboarding-{uuid.uuid4().hex[:8]}@example.com"


def _create(api_client: TestClient, email: str | None = None):
    payload = {"email": email or _email()}
    response = api_client.post("/api/core/client/v1/onboarding/applications", json=payload)
    assert response.status_code == 200
    body = response.json()
    return body["application"]["id"], body["access_token"], body


def test_create_draft_returns_token(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    with TestClient(app) as api_client:
        app_id, _, payload = _create(api_client)
    assert app_id
    assert payload["application"]["status"] == "DRAFT"
    assert payload["access_token"]


def test_submit_without_required_fields(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    with TestClient(app) as api_client:
        app_id, token, _ = _create(api_client)
        resp = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400


def test_update_draft_ok(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    with TestClient(app) as api_client:
        app_id, token, _ = _create(api_client)
        resp = api_client.put(
            f"/api/core/client/v1/onboarding/applications/{app_id}",
            json={"company_name": "ООО Тест", "inn": "1234567890", "org_type": "ООО"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["company_name"] == "ООО Тест"


def test_update_after_submit_conflict(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    with TestClient(app) as api_client:
        app_id, token, _ = _create(api_client)
        api_client.put(
            f"/api/core/client/v1/onboarding/applications/{app_id}",
            json={"company_name": "ООО Тест", "inn": "1234567890", "org_type": "ООО"},
            headers={"Authorization": f"Bearer {token}"},
        )
        submit_resp = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert submit_resp.status_code == 200
        update_resp = api_client.put(
            f"/api/core/client/v1/onboarding/applications/{app_id}",
            json={"phone": "+79990001122"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert update_resp.status_code == 409


def test_get_without_token_401(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    with TestClient(app) as api_client:
        app_id, _, _ = _create(api_client)
        resp = api_client.get(f"/api/core/client/v1/onboarding/applications/{app_id}")
    assert resp.status_code == 401


def test_get_with_wrong_token_403(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    with TestClient(app) as api_client:
        app1, token1, _ = _create(api_client)
        app2, _, _ = _create(api_client)
        assert app1 != app2
        resp = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{app2}",
            headers={"Authorization": f"Bearer {token1}"},
        )
    assert resp.status_code == 403


def test_happy_path_submit_and_get(monkeypatch) -> None:
    monkeypatch.setenv("ONBOARDING_TOKEN_SECRET", "test-onboarding-secret")
    with TestClient(app) as api_client:
        app_id, token, _ = _create(api_client)
        update = api_client.put(
            f"/api/core/client/v1/onboarding/applications/{app_id}",
            json={"company_name": "ООО Счастливый путь", "inn": "1234567890", "org_type": "ООО", "phone": "+79991234567"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert update.status_code == 200
        submit = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{app_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert submit.status_code == 200
        get_resp = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{app_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "SUBMITTED"
