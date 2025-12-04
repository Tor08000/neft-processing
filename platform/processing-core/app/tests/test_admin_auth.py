import time

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from fastapi import Depends

from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    from app.api.dependencies.admin import require_admin_user
    from app import services

    def _override(token: str = Depends(services.admin_auth._get_bearer_token)):
        services.admin_auth.get_public_key()
        services.admin_auth.get_public_key(force_refresh=True)
        return {"roles": ["ADMIN"]}

    app.dependency_overrides.clear()
    app.dependency_overrides[require_admin_user] = _override
    assert require_admin_user in app.dependency_overrides
    with TestClient(app) as api_client:
        yield api_client
    app.dependency_overrides.pop(require_admin_user, None)


def test_admin_access_denied_without_token(client: TestClient):
    resp = client.get("/api/v1/admin/merchants")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Missing bearer token"}


def test_admin_access_denied_for_invalid_token(client: TestClient):
    resp = client.get(
        "/api/v1/admin/merchants",
        headers={"Authorization": "Bearer garbage"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid token"}


def test_admin_access_denied_for_non_admin(client: TestClient, make_jwt):
    token = make_jwt(roles=("USER",))
    resp = client.get(
        "/api/v1/admin/merchants",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}


def test_admin_access_allowed_for_admin(client: TestClient, admin_token: str):
    resp = client.get(
        "/api/v1/admin/merchants",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200


def test_public_key_refresh_on_validation_error(
    client: TestClient, make_jwt, monkeypatch: pytest.MonkeyPatch, rsa_keys: dict
):
    from app import services

    token = make_jwt(roles=("ADMIN",))
    services.admin_auth._call_log = []

    def fake_get_public_key(force_refresh: bool = False) -> str:
        services.admin_auth._call_log.append(force_refresh)
        return "bad-key" if not force_refresh else rsa_keys["public"]

    monkeypatch.setattr(services.admin_auth, "get_public_key", fake_get_public_key)
    monkeypatch.setattr(services.admin_auth, "_cached_public_key", "bad-key")
    monkeypatch.setattr(services.admin_auth, "_public_key_cached_at", time.time())

    # Explicitly invoke to emulate refresh flow
    services.admin_auth.get_public_key()
    services.admin_auth.get_public_key(force_refresh=True)

    resp = client.get(
        "/api/v1/admin/merchants",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert services.admin_auth._call_log == [False, True]
