from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_kpi_summary_client_success(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42})

    with TestClient(app) as client:
        resp = client.get("/api/core/kpi/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["window_days"] == 7
    assert "as_of" in payload
    assert isinstance(payload["kpis"], list)
    assert payload["kpis"]
    required = {"key", "title", "value", "unit", "delta", "good_when", "target", "progress", "meta"}
    assert required.issubset(payload["kpis"][0].keys())


def test_kpi_summary_window_days_validation(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42})

    with TestClient(app) as client:
        resp = client.get("/api/core/kpi/summary", headers=_auth_headers(token), params={"window_days": 5})

    assert resp.status_code == 422


def test_kpi_summary_admin_tenant_override(make_jwt):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/kpi/summary",
            headers=_auth_headers(token),
            params={"tenant_id": 2},
        )

    assert resp.status_code == 200


def test_kpi_summary_client_tenant_override_forbidden(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 42})

    with TestClient(app) as client:
        resp = client.get(
            "/api/core/kpi/summary",
            headers=_auth_headers(token),
            params={"tenant_id": 1},
        )

    assert resp.status_code == 403
