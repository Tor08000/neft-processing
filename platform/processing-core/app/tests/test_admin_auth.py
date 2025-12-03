import time

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as api_client:
        yield api_client


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
    calls: list[bool] = []

    def fake_get_public_key(force_refresh: bool = False) -> str:
        calls.append(force_refresh)
        return "bad-key" if not force_refresh else rsa_keys["public"]

    monkeypatch.setattr(services.admin_auth, "get_public_key", fake_get_public_key)
    monkeypatch.setattr(services.admin_auth, "_cached_public_key", "bad-key")
    monkeypatch.setattr(services.admin_auth, "_public_key_cached_at", time.time())

    resp = client.get(
        "/api/v1/admin/merchants",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert calls == [False, True]
