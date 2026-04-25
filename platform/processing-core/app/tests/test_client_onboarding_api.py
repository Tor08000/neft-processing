from __future__ import annotations

import os
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db, make_engine
from app.models.client import Client
from app.models.fuel import FleetOfflineProfile
from app.routers import client_portal_v1 as portal
from app.services import client_auth
from app.services import client_fetch

os.environ.setdefault("NEFT_SKIP_DB_BOOTSTRAP", "1")


def test_current_onboarding_profile_updates_existing_client_and_resolves_client(monkeypatch):
    engine = make_engine("sqlite://", schema=None)
    Base.metadata.create_all(bind=engine, tables=[FleetOfflineProfile.__table__, Client.__table__])
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    client_id = "123e4567-e89b-12d3-a456-426614174000"
    try:
        db.add(Client(id=UUID(client_id), name="Legacy LLC", inn="7709999999", status="ACTIVE"))
        db.commit()

        monkeypatch.setattr(client_fetch, "DB_SCHEMA", None, raising=False)
        monkeypatch.setattr(portal, "DB_SCHEMA", None, raising=False)

        class DummyOnboarding:
            contract_id = None
            profile_json = None
            step = None
            status = None

        monkeypatch.setattr(
            portal,
            "_get_or_create_onboarding",
            lambda db, owner_id, client_id: DummyOnboarding(),
        )

        app = FastAPI()
        app.include_router(portal.router)

        def _get_db_override():
            yield db

        app.dependency_overrides[get_db] = _get_db_override
        app.dependency_overrides[client_auth.require_onboarding_user] = lambda: {
            "client_id": client_id,
            "user_id": "user-1",
        }

        with TestClient(app) as test_client:
            response = test_client.post(
                "/client/onboarding/profile",
                json={"org_type": "LEGAL", "name": "ACME LLC", "inn": "7700000000"},
            )
            assert response.status_code == 200
            assert response.json()["name"] == "ACME LLC"
            assert response.json()["status"] == "ONBOARDING"

        payload = client_fetch.safe_get_client(db, client_id)
        assert payload is not None
        assert payload["name"] == "ACME LLC"
        assert payload["inn"] == "7700000000"
        resolved = portal._resolve_client(db, {"client_id": client_id})
        assert resolved is not None
        assert resolved.id == client_id
    finally:
        db.close()
