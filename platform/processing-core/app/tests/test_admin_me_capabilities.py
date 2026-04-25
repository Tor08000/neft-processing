from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def _allow_prod_stub_providers(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_me_returns_domain_admin_levels_and_capabilities(make_jwt) -> None:
    token = make_jwt(roles=("NEFT_SUPPORT",))

    with TestClient(app) as client:
        response = client.get("/api/core/v1/admin/me", headers=_auth_headers(token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["primary_role_level"] == "support_admin"
    assert payload["role_levels"] == ["support_admin"]
    assert payload["permissions"]["cases"] == {
        "read": True,
        "operate": True,
        "approve": True,
        "override": False,
        "manage": False,
        "write": True,
    }
    assert payload["permissions"]["onboarding"]["manage"] is True
    assert payload["permissions"]["finance"]["read"] is True
    assert payload["permissions"]["finance"]["write"] is False
    assert payload["permissions"]["revenue"]["read"] is False
    assert payload["permissions"]["marketplace"]["approve"] is False
    assert payload["permissions"]["access"]["read"] is False
    assert payload["permissions"]["access"]["manage"] is False


def test_admin_me_accepts_platform_admin_role_without_superadmin_alias(make_jwt) -> None:
    token = make_jwt(roles=(), extra={"role": "PLATFORM_ADMIN"})

    with TestClient(app) as client:
        response = client.get("/api/core/v1/admin/me", headers=_auth_headers(token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["primary_role_level"] == "platform_admin"
    assert "platform_admin" in payload["role_levels"]
    assert payload["permissions"]["access"]["read"] is True
    assert payload["permissions"]["access"]["manage"] is True
    assert payload["permissions"]["commercial"]["manage"] is True
    assert payload["permissions"]["audit"]["read"] is True
    assert payload["permissions"]["revenue"]["read"] is False


def test_admin_me_returns_revenue_capability_for_finance_and_sales_roles(make_jwt) -> None:
    token = make_jwt(roles=("NEFT_FINANCE", "NEFT_SALES"))

    with TestClient(app) as client:
        response = client.get("/api/core/v1/admin/me", headers=_auth_headers(token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["permissions"]["revenue"] == {
        "read": True,
        "operate": False,
        "approve": False,
        "override": False,
        "manage": False,
        "write": False,
    }
