from __future__ import annotations

import pytest

from app.main import app

pytestmark = [pytest.mark.contracts, pytest.mark.contracts_api]

OPENAPI = app.openapi()


def _schema_properties(schema_name: str) -> set[str]:
    schema = OPENAPI["components"]["schemas"][schema_name]
    return set(schema.get("properties", {}).keys())


def test_unified_explain_schema_fields_retained():
    fields = _schema_properties("UnifiedExplainResponse")
    for field in {"primary_reason", "secondary_reasons", "actions", "sla", "escalation"}:
        assert field in fields


def test_money_flow_schema_fields_retained():
    health_fields = _schema_properties("MoneyHealthResponse")
    for field in {"stuck_authorized", "missing_money_flow_links", "top_offenders"}:
        assert field in health_fields

    replay_fields = _schema_properties("MoneyReplayResponse")
    for field in {"mode", "scope", "recompute_hash", "diff", "links_rebuilt"}:
        assert field in replay_fields


def test_fuel_authorize_schema_fields_retained():
    fields = _schema_properties("FuelAuthorizeResponse")
    for field in {"status", "transaction_id", "decline_code", "explain"}:
        assert field in fields


def test_crm_header_declared_in_openapi():
    crm_paths = [
        ("/api/core/v1/admin/crm/tariffs", "post"),
        ("/api/core/v1/admin/crm/tariffs/{tariff_id}", "patch"),
        ("/api/core/v1/admin/crm/clients/{client_id}/subscriptions", "post"),
    ]
    for path, method in crm_paths:
        parameters = OPENAPI["paths"][path][method].get("parameters", [])
        assert any(
            param.get("in") == "header" and param.get("name") == "X-CRM-Version"
            for param in parameters
        )
