from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_explain_v2_kpi_success(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain",
            headers=_auth_headers(token),
            params={"kpi_key": "declines_total", "window_days": 7},
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["kind"] == "kpi"
    assert payload["id"] == "declines_total"
    assert payload["decision"] in {"APPROVE", "DECLINE", "REVIEW"}
    assert payload["reason_tree"]["weight"] == 1.0
    assert isinstance(payload["evidence"], list)


def test_explain_v2_kind_validation(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain",
            headers=_auth_headers(token),
            params={"kind": "unknown", "id": "op-1"},
        )

    assert resp.status_code == 422


def test_explain_v2_window_days_validation(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain",
            headers=_auth_headers(token),
            params={"kpi_key": "declines_total", "window_days": 5},
        )

    assert resp.status_code == 422


def test_explain_v2_client_tenant_override_forbidden(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/explain",
            headers=_auth_headers(token),
            params={"kpi_key": "declines_total", "window_days": 7, "tenant_id": 1},
        )

    assert resp.status_code == 403
