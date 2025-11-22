from app.main import create_app
from fastapi.testclient import TestClient


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"
