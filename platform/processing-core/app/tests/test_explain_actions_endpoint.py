import pytest
from fastapi.testclient import TestClient

from app.routers.explain_v2 import router as explain_v2_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client() -> TestClient:
    with scoped_session_context(tables=()) as db_session:
        with router_client_context(
            router=explain_v2_router,
            prefix="/api/core",
            db_session=db_session,
        ) as api_client:
            yield api_client


def test_explain_actions_success(make_jwt, client: TestClient):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 10})

    resp = client.get(
        "/api/core/explain/actions",
        headers=_auth_headers(token),
        params={"kind": "operation", "id": "op-123"},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, list)
    if payload:
        assert {"action_code", "label"}.issubset(payload[0].keys())


def test_explain_actions_requires_kind(make_jwt, client: TestClient):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 10})

    resp = client.get(
        "/api/core/explain/actions",
        headers=_auth_headers(token),
        params={"id": "op-123"},
    )

    assert resp.status_code == 422
