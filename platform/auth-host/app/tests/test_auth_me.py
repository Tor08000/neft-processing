import sys
from importlib import import_module, util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import auth
from app.models import User
from app.security import hash_password

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR.parent) not in sys.path:
    sys.path.insert(0, str(APP_DIR.parent))

sys.modules.pop("app", None)
sys.modules.pop("app.main", None)

package_spec = util.spec_from_file_location("app", APP_DIR / "__init__.py")
package_module = util.module_from_spec(package_spec)
sys.modules["app"] = package_module
package_spec.loader.exec_module(package_module)

app = import_module("app.main").app


def test_auth_me_requires_bearer_token():
    client = TestClient(app)

    resp = client.get("/api/v1/auth/me")

    assert resp.status_code == 401
    assert resp.json() == {"detail": "not_authenticated"}


def test_auth_me_returns_user_payload(monkeypatch: pytest.MonkeyPatch):
    password_hash = hash_password("admin123")
    demo_user = User(
        id="00000000-0000-0000-0000-000000000999",
        email="admin@example.com",
        full_name="Demo Admin",
        password_hash=password_hash,
        is_active=True,
        created_at=None,
    )

    async def fake_get_user(email: str):
        if email.lower() == demo_user.email:
            return demo_user
        return None

    async def fake_get_roles(_user_id: str):
        return ["ADMIN"]

    monkeypatch.setattr(auth, "_get_user_from_db", fake_get_user)
    monkeypatch.setattr(auth, "_get_roles_for_user", fake_get_roles)

    client = TestClient(app)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert login.status_code == 200

    token = login.json()["access_token"]

    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["email"] == "admin@example.com"
    assert payload["roles"] == ["ADMIN"]
    assert payload["subject"] == "admin@example.com"
    assert payload.get("client_id") is None
    assert payload.get("subject_type") == "user"
