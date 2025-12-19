import sys
from pathlib import Path

from fastapi.testclient import TestClient

service_root = Path(__file__).resolve().parents[2]
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        sys.modules.pop(module_name)

if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))

from app.main import create_app


def test_health_endpoints():
    client = TestClient(create_app())

    for path in ("/api/v1/health", "/api/v1/live", "/api/v1/ready", "/health", "/api/ai/health"):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["service"] == "ai-service"
