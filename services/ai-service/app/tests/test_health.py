from app.main import create_app
from fastapi.testclient import TestClient


def test_health_endpoints():
    client = TestClient(create_app())

    for path in ("/api/v1/health", "/api/v1/live", "/api/v1/ready"):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["service"] == "ai-service"
