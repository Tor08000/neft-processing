import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import admin_runtime as admin_runtime_service


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


OPERATIONAL_TABLE_MODELS = {
    admin_runtime_service.PayoutOrder,
    admin_runtime_service.SettlementPeriod,
    admin_runtime_service.AuditLog,
    admin_runtime_service.PartnerLedgerEntry,
    admin_runtime_service.SupportTicket,
}

OBSERVED_HEALTH_ALL_UP = {
    "core_api": admin_runtime_service.HealthStatus.UP,
    "auth_host": admin_runtime_service.HealthStatus.UP,
    "gateway": admin_runtime_service.HealthStatus.UP,
    "integration_hub": admin_runtime_service.HealthStatus.UP,
    "document_service": admin_runtime_service.HealthStatus.UP,
    "logistics_service": admin_runtime_service.HealthStatus.UP,
    "ai_service": admin_runtime_service.HealthStatus.UP,
    "redis": admin_runtime_service.HealthStatus.UP,
    "minio": admin_runtime_service.HealthStatus.UP,
    "clickhouse": admin_runtime_service.HealthStatus.UP,
    "prometheus": admin_runtime_service.HealthStatus.UP,
    "grafana": admin_runtime_service.HealthStatus.UP,
    "loki": admin_runtime_service.HealthStatus.UP,
    "otel_collector": admin_runtime_service.HealthStatus.UP,
}


@pytest.fixture(autouse=True)
def _allow_prod_stub_providers(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setattr(
        admin_runtime_service,
        "_build_observed_health",
        lambda: (OBSERVED_HEALTH_ALL_UP.copy(), []),
    )
    monkeypatch.setattr(
        admin_runtime_service,
        "_build_external_provider_health",
        lambda: (
            [
                admin_runtime_service.ExternalProviderHealth(
                    service="integration-hub",
                    provider="diadok",
                    mode="sandbox",
                    status=admin_runtime_service.ExternalProviderStatus.DEGRADED,
                    configured=False,
                    last_error_code="diadok_not_configured",
                    message="DIADOK requires provider credentials",
                )
            ],
            ["provider_degraded:integration-hub:diadok"],
        ),
    )


def test_admin_runtime_summary_schema(make_jwt):
    token = make_jwt(roles=("ADMIN",))

    with TestClient(app) as client:
        resp = client.get("/api/core/v1/admin/runtime/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    for key in ("health", "queues", "violations", "events"):
        assert key in payload
    assert "ts" in payload
    assert "environment" in payload
    assert "read_only" in payload
    assert "warnings" in payload
    assert "missing_tables" in payload
    assert payload["external_providers"][0]["provider"] == "diadok"
    assert payload["external_providers"][0]["status"] == "DEGRADED"


def test_admin_runtime_summary_statuses_valid(make_jwt):
    token = make_jwt(roles=("ADMIN",))

    with TestClient(app) as client:
        resp = client.get("/api/core/v1/admin/runtime/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    allowed = {"UP", "DEGRADED", "DOWN"}
    assert set(payload["health"].values()).issubset(allowed)
    for key in ("integration_hub", "document_service", "logistics_service", "ai_service", "prometheus", "grafana", "loki", "otel_collector"):
        assert key in payload["health"]


def test_admin_runtime_summary_read_only_propagates(make_jwt, monkeypatch):
    token = make_jwt(roles=("ADMIN",))
    monkeypatch.setattr(settings, "ADMIN_READ_ONLY", True)

    with TestClient(app) as client:
        resp = client.get("/api/core/v1/admin/runtime/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["read_only"] is True


def test_admin_runtime_summary_degrades_when_operational_tables_are_missing(make_jwt, monkeypatch):
    token = make_jwt(roles=("ADMIN",))

    def _missing_operational_tables(db, model) -> bool:
        return model not in OPERATIONAL_TABLE_MODELS

    monkeypatch.setattr(admin_runtime_service, "_table_available", _missing_operational_tables)

    with TestClient(app) as client:
        resp = client.get("/api/core/v1/admin/runtime/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["health"]["postgres"] == "DEGRADED"
    assert payload["queues"]["payout"] == {"depth": 0, "oldest_age_sec": 0}
    assert payload["queues"]["settlement"] == {"depth": 0, "oldest_age_sec": 0}
    assert payload["queues"]["blocked_payouts"] == {"count": 0}
    assert payload["violations"]["invariants"] == {"count": 0, "top": []}
    assert payload["violations"]["sla_penalties"] == {"count": 0, "top": []}
    assert payload["events"]["critical_last_10"] == []
    assert set(payload["missing_tables"]) == {
        model.__table__.name for model in OPERATIONAL_TABLE_MODELS
    }
    assert set(payload["warnings"]) == {
        "provider_degraded:integration-hub:diadok",
        *[f"missing_table:{model.__table__.name}" for model in OPERATIONAL_TABLE_MODELS],
    }
    assert payload["money_risk"] == {
        "payouts_blocked": 0,
        "settlements_pending": 0,
        "overdue_clients": 0,
    }


def test_admin_runtime_summary_allows_domain_operator_role(make_jwt):
    token = make_jwt(roles=("NEFT_OPS",))

    with TestClient(app) as client:
        resp = client.get("/api/core/v1/admin/runtime/summary", headers=_auth_headers(token))

    assert resp.status_code == 200


def test_admin_runtime_summary_surfaces_observed_probe_failures(make_jwt, monkeypatch):
    token = make_jwt(roles=("ADMIN",))

    monkeypatch.setattr(
        admin_runtime_service,
        "_build_observed_health",
        lambda: (
            {
                **OBSERVED_HEALTH_ALL_UP,
                "gateway": admin_runtime_service.HealthStatus.DOWN,
                "integration_hub": admin_runtime_service.HealthStatus.DEGRADED,
                "prometheus": admin_runtime_service.HealthStatus.DOWN,
            },
            [
                "health_down:gateway",
                "health_degraded:integration_hub",
                "health_down:prometheus",
                "metrics_down:integration_hub",
            ],
        ),
    )

    with TestClient(app) as client:
        resp = client.get("/api/core/v1/admin/runtime/summary", headers=_auth_headers(token))

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["health"]["gateway"] == "DOWN"
    assert payload["health"]["integration_hub"] == "DEGRADED"
    assert payload["health"]["prometheus"] == "DOWN"
    assert "health_down:gateway" in payload["warnings"]
    assert "health_degraded:integration_hub" in payload["warnings"]
    assert "metrics_down:integration_hub" in payload["warnings"]
