from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import get_db
from app.main import app
from app.security.rbac.principal import Principal, get_principal


def test_portal_me_contract_includes_legal_and_features():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    session = SessionLocal()

    def _override_db():
        try:
            yield session
        finally:
            pass

    def _override_principal():
        return Principal(
            user_id=uuid4(),
            roles={"admin"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=True,
            raw_claims={"sub": "admin@example.com", "roles": ["ADMIN"]},
        )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_principal] = _override_principal

    previous_onboarding = settings.CORE_ONBOARDING_ENABLED
    previous_legal_gate = settings.LEGAL_GATE_ENABLED
    settings.CORE_ONBOARDING_ENABLED = False
    settings.LEGAL_GATE_ENABLED = True

    try:
        with TestClient(app) as client:
            response = client.get("/api/core/portal/me")
            assert response.status_code == 200
            payload = response.json()
            assert payload["actor_type"] == "admin"
            assert payload["legal"] == {
                "required_count": 0,
                "accepted": True,
                "missing": [],
                "required_enabled": False,
            }
            assert payload["features"] == {
                "onboarding_enabled": False,
                "legal_gate_enabled": True,
            }
    finally:
        settings.CORE_ONBOARDING_ENABLED = previous_onboarding
        settings.LEGAL_GATE_ENABLED = previous_legal_gate
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_principal, None)
        session.close()
        engine.dispose()
