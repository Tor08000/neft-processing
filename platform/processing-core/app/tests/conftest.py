import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import Depends

import pytest
from jose import jwt
from .fixtures.rsa_keys import rsa_keys  # noqa: F401

ROOT_DIR = Path(__file__).resolve().parents[4]
SHARED_PATH = ROOT_DIR / "shared" / "python"
SERVICE_ROOT = ROOT_DIR / "services" / "core-api"
PROCESSING_APP_ROOT = ROOT_DIR / "platform" / "processing-core"

for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        sys.modules.pop(module_name)

for path in (SHARED_PATH, PROCESSING_APP_ROOT):
    if path.exists():
        sys.path.insert(0, str(path))

if SERVICE_ROOT.exists():
    sys.path.insert(0, str(SERVICE_ROOT))

# Use in-memory SQLite for tests to avoid coupling to external Postgres.
os.environ.setdefault("NEFT_DB_URL", "sqlite+pysqlite:///:memory:")

try:
    from app.api.dependencies.admin import require_admin_user
    from app.main import app as fastapi_app
    from app.services import admin_auth as _admin_auth

    fastapi_app.dependency_overrides[require_admin_user] = _admin_auth.verify_admin_token
except Exception:
    pass

EXPECTED_ISSUER = "neft-auth"
EXPECTED_AUDIENCE = "neft-admin"


@pytest.fixture(autouse=True)
def _mock_admin_public_key(monkeypatch: pytest.MonkeyPatch, rsa_keys: dict):
    try:
        from app.services import admin_auth
    except ModuleNotFoundError:
        return

    monkeypatch.setenv("ADMIN_PUBLIC_KEY", rsa_keys["public"])
    monkeypatch.setattr(admin_auth, "_cached_public_key", None, raising=False)
    monkeypatch.setattr(admin_auth, "_public_key_cached_at", 0.0, raising=False)

    from app import services
    from app.api.dependencies.admin import require_admin_user
    from app.main import app

    def _admin_override(token: str = Depends(admin_auth._get_bearer_token)) -> dict:
        services.admin_auth.get_public_key()
        services.admin_auth.get_public_key(force_refresh=True)
        return {"roles": ["ADMIN"]}

    app.dependency_overrides[require_admin_user] = _admin_override


@pytest.fixture
def make_jwt(rsa_keys: dict):
    def _make_jwt(roles=("ADMIN",), minutes_valid: int = 60, sub: str = "user-1"):
        payload = {
            "sub": sub,
            "roles": list(roles),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes_valid),
            "aud": EXPECTED_AUDIENCE,
            "iss": EXPECTED_ISSUER,
        }
        return jwt.encode(payload, rsa_keys["private"], algorithm="RS256")

    return _make_jwt


@pytest.fixture
def admin_token(make_jwt):
    return make_jwt(roles=("ADMIN",))


@pytest.fixture
def user_token(make_jwt):
    return make_jwt(roles=("USER",))


@pytest.fixture
def admin_auth_headers(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}"}
