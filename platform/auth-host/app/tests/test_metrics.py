from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

service_root = Path(__file__).resolve().parents[2]
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        sys.modules.pop(module_name)

if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))

from app.main import app


def test_metrics_endpoint():
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "auth_host_up" in response.text
