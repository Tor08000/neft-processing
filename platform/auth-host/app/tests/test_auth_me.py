import sys
from importlib import import_module, util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR.parent) not in sys.path:
    sys.path.insert(0, str(APP_DIR.parent))

sys.modules.pop("app", None)
sys.modules.pop("app.main", None)

package_spec = util.spec_from_file_location("app", APP_DIR / "__init__.py")
package_module = util.module_from_spec(package_spec)
sys.modules["app"] = package_module
package_spec.loader.exec_module(package_module)

from fastapi.testclient import TestClient

app = import_module("app.main").app


def test_auth_me_requires_bearer_token():
    client = TestClient(app)

    resp = client.get("/api/v1/auth/me")

    assert resp.status_code == 401
    assert resp.json() == {"detail": "not_authenticated"}


def test_auth_me_returns_user_payload():
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
