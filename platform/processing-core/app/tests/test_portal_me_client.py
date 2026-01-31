from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.routers import client_portal_v1
from app.services import client_fetch
from app.services import portal_me


@pytest.fixture(autouse=True)
def clean_db(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(client_fetch, "DB_SCHEMA", None)
    monkeypatch.setattr(client_portal_v1, "DB_SCHEMA", None)
    monkeypatch.setattr(portal_me, "DB_SCHEMA", None)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_portal_me_returns_client_org_after_profile(make_jwt):
    client_id = uuid4()
    token = make_jwt(roles=("CLIENT_OWNER",), client_id=str(client_id))

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        response = api_client.post(
            "/api/core/client/onboarding/profile",
            json={"org_type": "LEGAL", "name": "ООО ТЕСТ", "inn": "7707083893"},
        )
        assert response.status_code == 200

        response = api_client.get("/api/core/portal/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["org"] is not None
    assert payload["org"]["name"] == "ООО ТЕСТ"
    assert payload["org"]["inn"] == "7707083893"
    assert payload["org_status"] == "ONBOARDING"
    assert payload["access_reason"] != "profile_missing"
