from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_jwks_endpoint_returns_keys(tmp_path, monkeypatch) -> None:
    key_dir = tmp_path / "keys"
    monkeypatch.setenv("AUTH_KEY_DIR", str(key_dir))
    monkeypatch.setenv("AUTH_PRIVATE_KEY_PATH", str(key_dir / "private.pem"))
    monkeypatch.setenv("AUTH_PUBLIC_KEY_PATH", str(key_dir / "public.pem"))

    service_root = Path(__file__).resolve().parents[2]
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    if str(service_root) not in sys.path:
        sys.path.insert(0, str(service_root))

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/.well-known/jwks.json")

    assert response.status_code == 200
    payload = response.json()
    assert "keys" in payload
    assert payload["keys"]
    assert payload["keys"][0]["kty"] == "RSA"


def test_jwks_legacy_redirects(tmp_path, monkeypatch) -> None:
    key_dir = tmp_path / "keys"
    monkeypatch.setenv("AUTH_KEY_DIR", str(key_dir))
    monkeypatch.setenv("AUTH_PRIVATE_KEY_PATH", str(key_dir / "private.pem"))
    monkeypatch.setenv("AUTH_PUBLIC_KEY_PATH", str(key_dir / "public.pem"))

    service_root = Path(__file__).resolve().parents[2]
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    if str(service_root) not in sys.path:
        sys.path.insert(0, str(service_root))

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/jwks", allow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "/api/v1/auth/.well-known/jwks.json"
