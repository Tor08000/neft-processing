from fastapi.testclient import TestClient

from app.main import app


def test_health_smoke():
    with TestClient(app) as client:
        response = client.get("/api/core/health")
    assert response.status_code == 200
