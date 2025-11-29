import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

ROOT_DIR = Path(__file__).resolve().parents[4]
SHARED_PATH = ROOT_DIR / "shared" / "python"

if SHARED_PATH.exists():
    sys.path.append(str(SHARED_PATH))

# Use in-memory SQLite for tests to avoid coupling to external Postgres.
os.environ.setdefault("NEFT_DB_URL", "sqlite+pysqlite:///:memory:")

EXPECTED_ISSUER = "neft-auth"
EXPECTED_AUDIENCE = "neft-admin"


@pytest.fixture(autouse=True)
def _mock_admin_public_key(monkeypatch: pytest.MonkeyPatch, rsa_keys: dict):
    try:
        from app.services import admin_auth
    except ModuleNotFoundError:
        return

    monkeypatch.setattr(admin_auth, "_cached_public_key", None, raising=False)
    monkeypatch.setattr(admin_auth, "_public_key_cached_at", 0.0, raising=False)
    monkeypatch.setattr(admin_auth, "get_public_key", lambda: rsa_keys["public"])


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
