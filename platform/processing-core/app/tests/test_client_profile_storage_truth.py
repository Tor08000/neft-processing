from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.models.fuel import FleetOfflineProfile
from app.routers import client_portal_v1
from app.services import client_auth
from app.tests._scoped_router_harness import scoped_session_context


@contextmanager
def _portal_client(db_session: Session, *, token: dict):
    app = FastAPI()
    app.include_router(client_portal_v1.router, prefix="/api/core")

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[client_auth.require_onboarding_user] = lambda: token

    original_enforce = client_portal_v1._enforce_portal_write_access
    client_portal_v1._enforce_portal_write_access = lambda **kwargs: None
    try:
        with TestClient(app) as api_client:
            yield api_client
    finally:
        client_portal_v1._enforce_portal_write_access = original_enforce


def test_client_onboarding_profile_persists_individual_org_type() -> None:
    tables = (
        FleetOfflineProfile.__table__,
        Client.__table__,
        ClientOnboardingContract.__table__,
        ClientOnboarding.__table__,
    )
    with scoped_session_context(tables=tables) as session:
        client_id = str(uuid4())
        token = {
            "client_id": client_id,
            "sub": "owner-1",
            "user_id": "owner-1",
            "email": "owner-1@neft.local",
            "role": "CLIENT_OWNER",
            "roles": ["CLIENT_OWNER"],
        }

        with _portal_client(session, token=token) as api_client:
            response = api_client.post(
                "/api/core/client/onboarding/profile",
                json={
                    "org_type": "INDIVIDUAL",
                    "name": "Demo Client",
                    "inn": "123456789012",
                    "address": "Moscow",
                },
            )

        assert response.status_code == 200, response.text

        stored = session.get(Client, UUID(client_id))
        assert stored is not None
        assert stored.org_type == "INDIVIDUAL"
        assert stored.full_name == "Demo Client"
        assert stored.legal_name is None
