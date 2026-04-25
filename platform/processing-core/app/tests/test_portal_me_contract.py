from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import settings
from app.routers.portal_me import router as portal_me_router
from app.security.rbac.principal import Principal, get_principal
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def test_portal_me_contract_includes_legal_and_features():
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

    previous_onboarding = settings.CORE_ONBOARDING_ENABLED
    previous_legal_gate = settings.LEGAL_GATE_ENABLED
    settings.CORE_ONBOARDING_ENABLED = False
    settings.LEGAL_GATE_ENABLED = True

    try:
        with scoped_session_context(tables=()) as session:
            assert isinstance(session, Session)
            with router_client_context(
                router=portal_me_router,
                prefix="/api/core",
                db_session=session,
                dependency_overrides={get_principal: _override_principal},
            ) as client:
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
