import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.email_provider_runtime import set_email_degraded


@pytest.fixture(autouse=True)
def _allow_mock_provider_override(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setattr("app.main._validate_email_provider_startup", lambda: None)


def test_health_smoke():
    set_email_degraded(False)
    with TestClient(app) as client:
        response = client.get("/api/core/health")
    assert response.status_code == 200
    assert response.json().get("email_provider") == "ok"


def test_health_supports_head_probe():
    with TestClient(app) as client:
        response = client.head("/api/core/health")
    assert response.status_code == 200
    assert response.content == b""


def test_ready_degraded_when_email_provider_unreachable():
    set_email_degraded(True)
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
        assert response.status_code == 200
        assert response.json().get("email_provider") == "degraded"
    finally:
        set_email_degraded(False)
