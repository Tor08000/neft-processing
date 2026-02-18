from fastapi.testclient import TestClient

from app.main import app
from app.services.email_provider_runtime import set_email_degraded


def test_health_smoke():
    set_email_degraded(False)
    with TestClient(app) as client:
        response = client.get("/api/core/health")
    assert response.status_code == 200
    assert response.json().get("email_provider") == "ok"


def test_ready_degraded_when_email_provider_unreachable():
    set_email_degraded(True)
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
        assert response.status_code == 200
        assert response.json().get("email_provider") == "degraded"
    finally:
        set_email_degraded(False)
