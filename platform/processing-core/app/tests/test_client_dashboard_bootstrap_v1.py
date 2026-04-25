from __future__ import annotations

from uuid import UUID, uuid4

from app.api.dependencies.client import client_portal_user
from app.models.client import Client
from app.routers.client_portal_v1 import router as client_portal_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def _owner_token(*, client_id: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "sub": "user-1",
        "user_id": "user-1",
        "subject_type": "client_user",
        "portal": "client",
        "roles": ["CLIENT_OWNER"],
        "role": "CLIENT_OWNER",
    }
    if client_id is not None:
        payload["client_id"] = client_id
    return payload


def test_client_dashboard_returns_bootstrap_widgets_when_client_is_not_resolved() -> None:
    with scoped_session_context(tables=()) as session:
        with router_client_context(
            router=client_portal_router,
            prefix="/api/core",
            db_session=session,
            dependency_overrides={client_portal_user: lambda: _owner_token()},
        ) as client:
            response = client.get("/api/core/client/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "OWNER"
    assert [item["key"] for item in payload["widgets"]] == ["recent_documents", "exports_recent", "owner_actions"]


def test_client_dashboard_degrades_when_supporting_read_models_are_missing() -> None:
    client_id = str(uuid4())
    with scoped_session_context(tables=(Client.__table__,)) as session:
        session.add(Client(id=UUID(client_id), name="Client", status="ONBOARDING"))
        session.commit()

        with router_client_context(
            router=client_portal_router,
            prefix="/api/core",
            db_session=session,
            dependency_overrides={client_portal_user: lambda: _owner_token(client_id=client_id)},
        ) as client:
            response = client.get("/api/core/client/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "OWNER"
    assert [item["key"] for item in payload["widgets"]] == [
        "total_spend_30d",
        "transactions_30d",
        "spend_timeseries_30d",
        "top_cards",
        "health_exports_email",
        "support_overview",
        "slo_health",
        "owner_actions",
    ]
    assert payload["widgets"][0]["data"] is None
    assert payload["widgets"][4]["data"] == {
        "exports_running": 0,
        "exports_failed": 0,
        "email_failures_24h": 0,
    }
    assert payload["widgets"][6]["data"] == {
        "status": "green",
        "breaches_7d": 0,
        "breaches_30d": 0,
    }
