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
