from __future__ import annotations

from datetime import datetime
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, DateTime, MetaData, String, Table, insert
from sqlalchemy.orm import sessionmaker

from app.db import get_db, make_engine
from app.routers import client_portal_v1 as portal
from app.services import client_auth
from app.services import client_fetch

os.environ.setdefault("NEFT_SKIP_DB_BOOTSTRAP", "1")


def test_onboarding_profile_handles_missing_email_column(monkeypatch):
    engine = make_engine("sqlite://", schema=None)
    metadata = MetaData()
    clients_table = Table(
        "clients",
        metadata,
        Column("id", String, primary_key=True),
        Column("name", String),
        Column("inn", String),
        Column("status", String),
        Column("created_at", DateTime, default=datetime.utcnow),
    )
    metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    try:
        db.execute(
            insert(clients_table).values(
                id="client-123",
                name="Legacy LLC",
                inn="7700000000",
                status="ACTIVE",
            )
        )
        db.commit()

        monkeypatch.setattr(client_fetch, "DB_SCHEMA", None)
        monkeypatch.setattr(portal, "DB_SCHEMA", None)

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
            "client_id": "client-123",
            "user_id": "user-1",
        }

        with TestClient(app) as test_client:
            response = test_client.post(
                "/client/onboarding/profile",
                json={"org_type": "LEGAL", "name": "ACME LLC", "inn": "7700000000"},
            )
            assert response.status_code == 200

        payload = client_fetch.safe_get_client(db, "client-123")
        assert payload is not None
        assert "email" not in payload
        resolved = portal._resolve_client(db, {"client_id": "client-123"})
        assert resolved is not None
        assert resolved.id == "client-123"
    finally:
        db.close()
