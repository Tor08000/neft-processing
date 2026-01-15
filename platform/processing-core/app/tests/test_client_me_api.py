from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.client import Client


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_client_me_returns_org_and_entitlements(make_jwt):
    client_id = uuid4()
    session = SessionLocal()
    try:
        session.add(Client(id=client_id, name="Test Client", inn="7700", status="ACTIVE"))
        session.commit()
    finally:
        session.close()

    token = make_jwt(roles=("CLIENT_ADMIN",), client_id=str(client_id), extra={"tenant_id": 1})
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        resp = api_client.get("/api/core/client/me")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["org_status"] == "ACTIVE"
    assert payload["org"]["id"] == str(client_id)
    assert payload["membership"]["roles"] == ["ADMIN"]
    assert payload["entitlements"]["org_status"] == "ACTIVE"


def test_client_me_handles_missing_org(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), extra={"tenant_id": 1})
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        resp = api_client.get("/api/core/client/me")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["org"] is None
    assert payload["org_status"] == "NONE"
