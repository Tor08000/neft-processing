from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_explain_actions_success(make_jwt):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 10})

    with TestClient(app) as client:
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


def test_explain_actions_requires_kind(make_jwt):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 10})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain/actions",
            headers=_auth_headers(token),
            params={"id": "op-123"},
        )

    assert resp.status_code == 422
