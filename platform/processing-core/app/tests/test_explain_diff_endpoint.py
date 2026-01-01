from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload(actions: list[str]) -> dict:
    return {
        "context": {"kind": "kpi", "id": "declines_total"},
        "actions": [{"code": action} for action in actions],
    }


def test_explain_diff_improve(make_jwt):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})

    with TestClient(app) as client:
        resp = client.post(
            "/api/core/explain/diff",
            headers=_auth_headers(token),
            json=_payload(["REQUEST_DOCS"]),
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["diff"]["risk"]["label"] == "IMPROVED"


def test_explain_diff_no_change(make_jwt):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})

    with TestClient(app) as client:
        resp = client.post(
            "/api/core/explain/diff",
            headers=_auth_headers(token),
            json=_payload(["NOOP"]),
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["diff"]["risk"]["label"] == "NO_CHANGE"


def test_explain_diff_worsen(make_jwt):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})

    with TestClient(app) as client:
        resp = client.post(
            "/api/core/explain/diff",
            headers=_auth_headers(token),
            json=_payload(["BLOCK"]),
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["diff"]["risk"]["label"] == "WORSENED"


def test_explain_diff_mixed(make_jwt):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})

    with TestClient(app) as client:
        resp = client.post(
            "/api/core/explain/diff",
            headers=_auth_headers(token),
            json=_payload(["REQUEST_DOCS", "ADJUST_LIMITS"]),
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["diff"]["reasons"]["added"] or payload["diff"]["reasons"]["removed"]
