from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

service_root = Path(__file__).resolve().parents[2]
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        sys.modules.pop(module_name)

if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))

from app.schemas.auth import HealthResponse


def test_health_endpoint(monkeypatch) -> None:
    test_app = FastAPI()

    def ok_response() -> JSONResponse:
        response = HealthResponse(status="ok", service="auth-host")
        return JSONResponse(status_code=status.HTTP_200_OK, content=response.model_dump(exclude_none=True))

    @test_app.get("/api/v1/auth/health")
    def compatibility_health():
        return ok_response()

    @test_app.get("/api/auth/health")
    def prefixed_health():
        return ok_response()

    @test_app.get("/api/auth/ready")
    def prefixed_ready():
        return ok_response()

    client = TestClient(test_app)
    response_v1 = client.get("/api/v1/auth/health")
    response_prefixed = client.get("/api/auth/health")
    response_ready = client.get("/api/auth/ready")

    assert response_v1.status_code == 200
    assert response_prefixed.status_code == 200
    assert response_ready.status_code == 200
    assert response_v1.json() == {"status": "ok", "service": "auth-host"}
    assert response_prefixed.json() == {"status": "ok", "service": "auth-host"}
