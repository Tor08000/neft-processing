from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app
from app.tests._path_helpers import find_repo_root


def _find_route(path: str, method: str) -> APIRoute | None:
    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == path and method in (route.methods or set()):
            return route
    return None


def _route(path: str, method: str) -> APIRoute:
    route = _find_route(path, method)
    assert route is not None, f"route not found: {method} {path}"
    return route


def _route_index(path: str, method: str) -> int:
    for index, route in enumerate(app.router.routes):
        if not isinstance(route, APIRoute):
            continue
        if route.path == path and method in (route.methods or set()):
            return index
    raise AssertionError(f"route not found: {method} {path}")


def _repo_root() -> Path:
    discovered = find_repo_root(Path(__file__).resolve())
    candidates = [discovered, Path("/app"), Path.cwd(), *Path.cwd().parents]
    for current in candidates:
        if (current / "gateway").is_dir():
            return current
    return discovered


def _gateway_config(name: str) -> str:
    return (_repo_root() / "gateway" / name).read_text(encoding="utf-8")


def _location_block(config_text: str, header: str) -> str:
    match = re.search(
        rf"^\s*location {re.escape(header)} \{{\n(?P<body>.*?)^\s*\}}",
        config_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"location block not found: {header}"
    return match.group("body")


def test_removed_hidden_root_aliases_no_longer_exist_while_canonical_paths_remain() -> None:
    removed_aliases = {
        ("GET", "/portal/me"): "/api/core/portal/me",
        ("GET", "/client/auth/verify"): "/api/core/client/auth/verify",
        ("GET", "/partner/auth/verify"): "/api/core/partner/auth/verify",
        ("GET", "/admin/auth/verify"): "/api/core/admin/auth/verify",
        ("GET", "/v1/admin/auth/verify"): "/api/core/v1/admin/auth/verify",
        ("GET", "/v1/admin/runtime/summary"): "/api/core/v1/admin/runtime/summary",
        ("GET", "/v1/admin/merchants"): "/api/core/v1/admin/merchants",
        ("GET", "/v1/admin/terminals"): "/api/core/v1/admin/terminals",
        ("GET", "/v1/admin/terminals/{terminal_id}"): "/api/core/v1/admin/terminals/{terminal_id}",
        ("GET", "/v1/admin/audit"): "/api/core/v1/admin/audit",
        ("GET", "/v1/admin/audit/{correlation_id}"): "/api/core/v1/admin/audit/{correlation_id}",
        ("GET", "/v1/admin/audit/signing/keys"): "/api/core/v1/admin/audit/signing/keys",
        ("POST", "/v1/admin/audit/holds"): "/api/core/v1/admin/audit/holds",
        ("GET", "/v1/admin/billing/summary"): "/api/core/v1/admin/billing/summary",
        ("GET", "/v1/admin/finance/overview"): "/api/core/v1/admin/finance/overview",
        ("GET", "/v1/admin/finance/invoices"): "/api/core/v1/admin/finance/invoices",
        ("GET", "/v1/admin/finance/payouts"): "/api/core/v1/admin/finance/payouts",
        ("POST", "/v1/admin/finance/payouts/{payout_id}/approve"): "/api/core/v1/admin/finance/payouts/{payout_id}/approve",
        ("GET", "/v1/admin/commercial/orgs/{org_id}"): "/api/core/v1/admin/commercial/orgs/{org_id}",
        ("POST", "/v1/admin/commercial/orgs/{org_id}/plan"): "/api/core/v1/admin/commercial/orgs/{org_id}/plan",
        ("POST", "/v1/admin/commercial/orgs/{org_id}/entitlements/recompute"): "/api/core/v1/admin/commercial/orgs/{org_id}/entitlements/recompute",
        ("GET", "/v1/admin/clients/{client_id}/invitations"): "/api/core/v1/admin/clients/{client_id}/invitations",
        ("POST", "/v1/admin/clients/invitations/{invitation_id}/resend"): "/api/core/v1/admin/clients/invitations/{invitation_id}/resend",
        ("POST", "/v1/admin/clients/invitations/{invitation_id}/revoke"): "/api/core/v1/admin/clients/invitations/{invitation_id}/revoke",
        ("GET", "/v1/admin/legal/documents"): "/api/core/v1/admin/legal/documents",
        ("POST", "/v1/admin/legal/documents"): "/api/core/v1/admin/legal/documents",
        ("PUT", "/v1/admin/legal/documents/{document_id}"): "/api/core/v1/admin/legal/documents/{document_id}",
        ("POST", "/v1/admin/legal/documents/{document_id}/publish"): "/api/core/v1/admin/legal/documents/{document_id}/publish",
        ("GET", "/v1/admin/legal/partners"): "/api/core/v1/admin/legal/partners",
        ("GET", "/v1/admin/legal/partners/{partner_id}"): "/api/core/v1/admin/legal/partners/{partner_id}",
        ("POST", "/v1/admin/legal/partners/{partner_id}/status"): "/api/core/v1/admin/legal/partners/{partner_id}/status",
        ("GET", "/v1/admin/legal/partners-legacy"): "/api/core/v1/admin/legal/partners-legacy",
        ("GET", "/v1/admin/legal/partners-legacy/{partner_id}"): "/api/core/v1/admin/legal/partners-legacy/{partner_id}",
        ("POST", "/v1/admin/legal/partners-legacy/{partner_id}/status"): "/api/core/v1/admin/legal/partners-legacy/{partner_id}/status",
        ("GET", "/v1/admin/marketplace/moderation/queue"): "/api/core/v1/admin/marketplace/moderation/queue",
        ("GET", "/v1/admin/marketplace/orders/{order_id}/events"): "/api/core/v1/admin/marketplace/orders/{order_id}/events",
        ("POST", "/v1/admin/marketplace/products/{product_id}:approve"): "/api/core/v1/admin/marketplace/products/{product_id}:approve",
        ("POST", "/v1/admin/marketplace/offers/{offer_id}:reject"): "/api/core/v1/admin/marketplace/offers/{offer_id}:reject",
        ("GET", "/v1/admin/me"): "/api/core/v1/admin/me",
        ("GET", "/v1/admin/money/health"): "/api/core/v1/admin/money/health",
        ("GET", "/v1/admin/money/explain"): "/api/core/v1/admin/money/explain",
        ("GET", "/v1/admin/money/cfo-explain"): "/api/core/v1/admin/money/cfo-explain",
        ("POST", "/v1/admin/money/replay"): "/api/core/v1/admin/money/replay",
        ("GET", "/v1/admin/ops/escalations"): "/api/core/v1/admin/ops/escalations",
        ("POST", "/v1/admin/ops/escalations/{escalation_id}/ack"): "/api/core/v1/admin/ops/escalations/{escalation_id}/ack",
        ("GET", "/v1/admin/ops/kpi"): "/api/core/v1/admin/ops/kpi",
        ("GET", "/v1/admin/ops/summary"): "/api/core/v1/admin/ops/summary",
        ("GET", "/v1/admin/reconciliation/runs"): "/api/core/v1/admin/reconciliation/runs",
        ("GET", "/v1/admin/reconciliation/external/statements"): "/api/core/v1/admin/reconciliation/external/statements",
        ("GET", "/v1/admin/reconciliation/imports"): "/api/core/v1/admin/reconciliation/imports",
        ("GET", "/v1/admin/reconciliation/runs/{run_id}/discrepancies"): "/api/core/v1/admin/reconciliation/runs/{run_id}/discrepancies",
        ("POST", "/v1/admin/reconciliation/run"): "/api/core/v1/admin/reconciliation/run",
        ("POST", "/v1/admin/reconciliation/discrepancies/{discrepancy_id}/resolve-adjustment"): "/api/core/v1/admin/reconciliation/discrepancies/{discrepancy_id}/resolve-adjustment",
    }

    for (method, alias_path), canonical_path in removed_aliases.items():
        assert _find_route(alias_path, method) is None
        canonical_route = _route(canonical_path, method)
        assert canonical_route.include_in_schema is True


def test_removed_hidden_core_admin_aliases_no_longer_exist_while_canonical_paths_remain() -> None:
    removed_aliases = {
        ("GET", "/api/core/admin/me"): "/api/core/v1/admin/me",
        ("GET", "/api/core/admin/runtime/summary"): "/api/core/v1/admin/runtime/summary",
        ("GET", "/api/core/admin/finance/overview"): "/api/core/v1/admin/finance/overview",
        ("GET", "/api/core/admin/legal/partners"): "/api/core/v1/admin/legal/partners",
        ("GET", "/api/core/admin/audit"): "/api/core/v1/admin/audit",
    }

    for (method, alias_path), canonical_path in removed_aliases.items():
        assert _find_route(alias_path, method) is None
        canonical_route = _route(canonical_path, method)
        assert canonical_route.include_in_schema is True


def test_removed_public_admin_compat_families_no_longer_exist_while_canonical_paths_remain() -> None:
    removed_aliases = {
        ("GET", "/api/v1/admin/audit"): "/api/core/v1/admin/audit",
        ("POST", "/api/v1/admin/audit/holds"): "/api/core/v1/admin/audit/holds",
        ("GET", "/api/v1/admin/finance/overview"): "/api/core/v1/admin/finance/overview",
        ("POST", "/api/v1/admin/finance/payments"): "/api/core/v1/admin/finance/payments",
        ("GET", "/api/v1/admin/legal/documents"): "/api/core/v1/admin/legal/documents",
        ("POST", "/api/v1/admin/legal/documents"): "/api/core/v1/admin/legal/documents",
        ("GET", "/api/v1/admin/marketplace/moderation/queue"): "/api/core/v1/admin/marketplace/moderation/queue",
        ("POST", "/api/v1/admin/marketplace/products/{product_id}:approve"): "/api/core/v1/admin/marketplace/products/{product_id}:approve",
        ("GET", "/api/v1/admin/money/health"): "/api/core/v1/admin/money/health",
        ("POST", "/api/v1/admin/money/replay"): "/api/core/v1/admin/money/replay",
        ("GET", "/api/v1/admin/reconciliation/runs"): "/api/core/v1/admin/reconciliation/runs",
        ("POST", "/api/v1/admin/reconciliation/run"): "/api/core/v1/admin/reconciliation/run",
    }

    for (method, alias_path), canonical_path in removed_aliases.items():
        assert _find_route(alias_path, method) is None
        canonical_route = _route(canonical_path, method)
        assert canonical_route.include_in_schema is True


def test_removed_hidden_core_partner_dashboard_alias_no_longer_exists_while_canonical_path_remains() -> None:
    assert _find_route("/api/core/partner/dashboard", "GET") is None
    canonical_route = _route("/api/core/partner/finance/dashboard", "GET")
    assert canonical_route.include_in_schema is True


def test_client_bootstrap_projection_topology_stays_explicit() -> None:
    canonical_route = _route("/api/core/portal/me", "GET")
    compatibility_route = _route("/api/core/client/me", "GET")

    assert canonical_route.include_in_schema is True
    assert compatibility_route.include_in_schema is True
    assert compatibility_route.name == "get_client_me"
    assert _find_route("/api/core/partner/me", "GET") is None


def test_partner_marketplace_order_routes_stay_mounted_on_compatibility_family() -> None:
    expected_routes = [
        ("GET", "/api/v1/marketplace/partner/orders"),
        ("GET", "/api/v1/marketplace/partner/orders/{order_id}"),
        ("GET", "/api/v1/marketplace/partner/orders/{order_id}/events"),
        ("GET", "/api/v1/marketplace/partner/orders/{order_id}/settlement"),
        ("POST", "/api/v1/marketplace/partner/orders/{order_id}:confirm"),
        ("POST", "/api/v1/marketplace/partner/orders/{order_id}/proofs"),
        ("POST", "/api/v1/marketplace/partner/orders/{order_id}:complete"),
    ]

    for method, path in expected_routes:
        route = _route(path, method)
        assert route.include_in_schema is True


def test_partner_finance_static_payout_routes_precede_dynamic_payout_id_route() -> None:
    dynamic_routes = [
        ("/api/core/partner/payouts/{payout_id}", "GET"),
        ("/api/partner/payouts/{payout_id}", "GET"),
    ]
    static_paths = [
        "/payouts/history",
        "/payouts/preview",
    ]

    for dynamic_path, method in dynamic_routes:
        prefix = dynamic_path.removesuffix("/payouts/{payout_id}")
        dynamic_index = _route_index(dynamic_path, method)
        for static_tail in static_paths:
            assert _route_index(prefix + static_tail, method) < dynamic_index


def test_checked_in_gateway_forwards_api_core_without_prefix_stripping() -> None:
    location_headers = [
        "^~ /api/core/client/v1/onboarding/",
        "^~ /api/core/client/docflow/",
        "/api/core/client/",
        "/api/core/partner/",
        "/api/core/portal/",
        "/api/core/",
    ]

    for config_name in ("nginx.conf", "default.conf"):
        config_text = _gateway_config(config_name)
        for header in location_headers:
            block = _location_block(config_text, header)
            assert "proxy_pass http://core_api;" in block
            assert "rewrite ^/api/core/" not in block


def test_gateway_onboarding_token_routes_precede_client_jwt_guard() -> None:
    for config_name in ("nginx.conf", "default.conf"):
        config_text = _gateway_config(config_name)
        client_guard_index = config_text.index("location /api/core/client/ {")
        for header in ("^~ /api/core/client/v1/onboarding/", "^~ /api/core/client/docflow/"):
            location_text = f"location {header} {{"
            assert config_text.index(location_text) < client_guard_index
            block = _location_block(config_text, header)
            assert "proxy_pass http://core_api;" in block
            assert "auth_request" not in block


def test_gateway_spa_upstreams_use_dynamic_docker_dns_resolution() -> None:
    for config_name in ("nginx.conf", "default.conf"):
        config_text = _gateway_config(config_name)
        for upstream_name, service_name in (
            ("admin_web", "admin-web"),
            ("client_web", "client-web"),
            ("partner_web", "partner-web"),
        ):
            match = re.search(
                rf"upstream {upstream_name} \{{(?P<body>.*?)^\}}",
                config_text,
                flags=re.MULTILINE | re.DOTALL,
            )
            assert match is not None, f"upstream block not found: {upstream_name}"
            assert f"server {service_name}:80 resolve;" in match.group("body")


def test_remaining_route_topology_freeze_map_stays_explicit() -> None:
    canonical_routes = {
        ("GET", "/api/core/portal/me"),
        ("GET", "/api/core/v1/admin/me"),
        ("GET", "/api/core/cases"),
        ("GET", "/api/core/client/invoices"),
        ("GET", "/api/core/client/onboarding/status"),
        ("GET", "/api/core/partner/acts"),
        ("GET", "/api/core/partner/balance"),
        ("GET", "/api/core/partner/invoices"),
        ("GET", "/api/core/partner/ledger"),
        ("GET", "/api/core/partner/ledger/{entry_id}/explain"),
        ("GET", "/api/core/partner/payouts"),
        ("GET", "/api/core/partner/payouts/history"),
        ("GET", "/api/core/partner/payouts/preview"),
        ("POST", "/api/core/partner/payouts/request"),
        ("GET", "/api/core/v1/admin/commercial/orgs/{org_id}"),
        ("GET", "/api/core/v1/admin/billing/summary"),
        ("GET", "/api/core/v1/admin/billing/invoices"),
        ("GET", "/api/core/v1/admin/finance/overview"),
        ("GET", "/api/core/v1/admin/finance/invoices"),
        ("GET", "/api/core/v1/admin/finance/payouts"),
        ("GET", "/api/core/v1/admin/finance/payouts/{payout_id}"),
        ("GET", "/api/core/v1/admin/marketplace/moderation/queue"),
        ("GET", "/api/core/v1/admin/clients/invitations"),
        ("GET", "/api/core/v1/admin/legal/documents"),
        ("GET", "/api/core/v1/admin/legal/partners"),
        ("GET", "/api/core/v1/admin/logistics/orders/{order_id}/inspection"),
        ("GET", "/api/core/v1/admin/ops/escalations"),
        ("GET", "/api/core/v1/admin/ops/kpi"),
        ("GET", "/api/core/v1/admin/money/explain"),
        ("GET", "/api/core/v1/admin/money/health"),
        ("GET", "/api/core/v1/admin/reconciliation/runs"),
        ("GET", "/api/core/v1/admin/reconciliation/external/statements"),
        ("GET", "/api/core/v1/admin/audit"),
        ("GET", "/api/core/v1/admin/runtime/summary"),
        ("GET", "/api/core/v1/admin/rules/versions"),
        ("POST", "/api/core/v1/admin/rules/versions"),
        ("POST", "/api/core/v1/admin/rules/versions/{version_id}/activate"),
        ("POST", "/api/core/v1/admin/rules/versions/{version_id}/publish"),
        ("POST", "/api/core/v1/admin/rules/rules"),
        ("GET", "/api/core/partner/finance/dashboard"),
        ("GET", "/api/core/partner/ledger"),
        ("GET", "/api/core/client/documents"),
        ("POST", "/api/core/client/documents/{document_id}/ack"),
        ("GET", "/api/core/v1/marketplace/client/recommendations"),
        ("GET", "/api/core/v1/marketplace/client/recommendations/why"),
        ("POST", "/api/core/v1/marketplace/client/events"),
        ("GET", "/api/marketplace/client/recommendations"),
        ("POST", "/api/marketplace/client/events"),
    }
    for method, path in canonical_routes:
        route = _route(path, method)
        assert route.include_in_schema is True

    hidden_or_redirect_tails = {
        ("GET", "/v1/admin/clients"),
        ("GET", "/api/partner/dashboard"),
        ("GET", "/api/core/admin/payouts"),
        ("GET", "/api/core/admin/payouts/{payout_id}"),
        ("GET", "/api/core/admin/partner/{partner_id}/ledger"),
        ("GET", "/api/core/admin/partner/{partner_id}/settlement"),
        ("GET", "/api/core/partner/dashboard"),
    }
    for method, path in hidden_or_redirect_tails:
        route = _find_route(path, method)
        if path == "/api/core/partner/dashboard":
            assert route is None
        else:
            assert route is not None
            assert route.include_in_schema is False

    compatibility_projection_routes = {
        ("GET", "/api/v1/admin/me"),
        ("GET", "/api/v1/admin/clients"),
        ("GET", "/api/v1/admin/billing/summary"),
        ("GET", "/api/core/client/me"),
        ("PUT", "/api/v1/partner/fuel/stations/{station_id}/prices"),
        ("POST", "/api/v1/partner/fuel/stations/{station_id}/prices/import"),
        ("GET", "/api/v1/client/documents"),
        ("POST", "/api/v1/client/documents/{document_id}/ack"),
        ("POST", "/api/v1/client/closing-packages/{package_id}/ack"),
        ("GET", "/api/v1/reports/billing/daily"),
        ("GET", "/api/v1/reports/billing/summary"),
        ("POST", "/api/v1/reports/billing/summary/rebuild"),
        ("GET", "/api/v1/reports/turnover"),
        ("GET", "/api/client/invoices"),
        ("GET", "/api/client/fleet/cards"),
        ("GET", "/api/client/onboarding/state"),
        ("POST", "/api/client/onboarding/step"),
        ("GET", "/v1/marketplace/client/recommendations"),
        ("GET", "/v1/marketplace/client/recommendations/why"),
        ("POST", "/v1/marketplace/client/events"),
        ("GET", "/api/client/marketplace/recommendations"),
        ("POST", "/api/client/marketplace/events"),
        ("GET", "/api/partner/acts"),
        ("GET", "/api/partner/balance"),
        ("GET", "/api/partner/invoices"),
        ("GET", "/api/partner/ledger"),
        ("GET", "/api/partner/ledger/{entry_id}/explain"),
        ("GET", "/api/partner/payouts"),
        ("GET", "/api/partner/payouts/history"),
        ("GET", "/api/partner/payouts/preview"),
        ("POST", "/api/partner/payouts/request"),
    }
    for method, path in compatibility_projection_routes:
        _route(path, method)

    assert _find_route("/api/core/client/fleet/cards", "GET") is None
    _route("/api/core/partner/contracts", "GET")
    _route("/api/core/partner/contracts/{contract_id}", "GET")
    _route("/api/core/partner/settlements", "GET")
    _route("/api/core/partner/settlements/{settlement_id}", "GET")
    _route("/api/partner/contracts", "GET")
    _route("/api/partner/contracts/{contract_id}", "GET")
    _route("/api/partner/settlements", "GET")
    _route("/api/partner/settlements/{settlement_id}", "GET")
    assert _find_route("/api/core/partner/settlements/{settlement_id}/confirm", "POST") is None
    assert _find_route("/api/partner/settlements/{settlement_id}/confirm", "POST") is None

    dormant_conditional_routes = {
        ("GET", "/api/core/partner/me"),
    }
    for method, path in dormant_conditional_routes:
        assert _find_route(path, method) is None


def test_core_admin_non_v1_visibility_map_stays_explicit() -> None:
    expected_schema_visible_routes = {
        ("GET", "/api/core/admin/auth/verify"),
        ("POST", "/api/core/admin/client-onboarding/{application_id}/approve"),
        ("POST", "/api/core/admin/clients/{client_id}/documents"),
        ("GET", "/api/core/admin/clients/{client_id}/subscription"),
        ("POST", "/api/core/admin/clients/{client_id}/subscription/assign"),
        ("POST", "/api/core/admin/documents/{document_id}/files"),
        ("GET", "/api/core/admin/partners"),
        ("POST", "/api/core/admin/partners"),
        ("GET", "/api/core/admin/partners/{partner_id}"),
        ("PATCH", "/api/core/admin/partners/{partner_id}"),
        ("GET", "/api/core/admin/partners/{partner_id}/users"),
        ("POST", "/api/core/admin/partners/{partner_id}/users"),
        ("DELETE", "/api/core/admin/partners/{partner_id}/users/{user_id}"),
        ("GET", "/api/core/admin/v1/onboarding/applications"),
        ("GET", "/api/core/admin/v1/onboarding/applications/{application_id}"),
        ("POST", "/api/core/admin/v1/onboarding/applications/{application_id}/approve"),
        ("POST", "/api/core/admin/v1/onboarding/applications/{application_id}/reject"),
        ("POST", "/api/core/admin/v1/onboarding/applications/{application_id}/start-review"),
        ("GET", "/api/core/admin/v1/onboarding/documents/{doc_id}/download"),
        ("POST", "/api/core/admin/v1/onboarding/documents/{doc_id}/reject"),
        ("POST", "/api/core/admin/v1/onboarding/documents/{doc_id}/verify"),
    }
    expected_schema_hidden_routes = {
        ("GET", "/api/core/admin/payouts"),
        ("GET", "/api/core/admin/payouts/{payout_id}"),
        ("GET", "/api/core/admin/partner/{partner_id}/ledger"),
        ("GET", "/api/core/admin/partner/{partner_id}/settlement"),
    }
    actual_schema_visible_routes: set[tuple[str, str]] = set()
    actual_schema_hidden_routes: set[tuple[str, str]] = set()
    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/core/admin/"):
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            target = actual_schema_visible_routes if route.include_in_schema else actual_schema_hidden_routes
            target.add((method, route.path))

    assert actual_schema_visible_routes == expected_schema_visible_routes
    assert actual_schema_hidden_routes == expected_schema_hidden_routes


def _admin_family_counts(prefix: str) -> tuple[dict[str, int], dict[bool, int]]:
    family_counts: dict[str, int] = {}
    schema_counts = {True: 0, False: 0}
    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith(prefix):
            continue
        methods = {method for method in (route.methods or set()) if method not in {"HEAD", "OPTIONS"}}
        if not methods:
            continue
        family = route.path[len(prefix) :].split("/", 1)[0]
        family_counts[family] = family_counts.get(family, 0) + len(methods)
        schema_counts[route.include_in_schema] += len(methods)
    return family_counts, schema_counts


def test_admin_root_and_public_compatibility_family_maps_stay_explicit() -> None:
    expected_hidden_root_families = {
        "accounting": 6,
        "accounts": 2,
        "api": 5,
        "bank_stub": 4,
        "bi": 2,
        "billing": 38,
        "bookings": 2,
        "card-groups": 8,
        "cards": 1,
        "cases": 6,
        "clearing": 10,
        "client-groups": 8,
        "clients": 3,
        "closing-packages": 2,
        "contracts": 11,
        "crm": 51,
        "decision-memory": 3,
        "disputes": 5,
        "documents": 8,
        "edo": 12,
        "entitlements": 1,
        "erp_stub": 3,
        "explain": 1,
        "exports": 4,
        "fleet": 10,
        "fleet-control": 5,
        "fleet-intelligence": 10,
        "fraud": 3,
        "fuel": 22,
        "integration": 4,
        "integrations": 8,
        "invoice-threads": 1,
        "invoices": 1,
        "ledger": 4,
        "legal": 3,
        "legal-graph": 4,
        "limits": 5,
        "logistics": 4,
        "notifications": 8,
        "operations": 3,
        "partners": 17,
        "payouts": 2,
        "pricing": 8,
        "products": 2,
        "reconciliation-requests": 3,
        "refunds": 1,
        "revenue": 3,
        "reversals": 1,
        "risk": 6,
        "risk-v5": 3,
        "seed": 1,
        "settlement": 7,
        "settlements": 2,
        "transactions": 1,
        "what-if": 1,
    }
    expected_public_compat_families = {
        "accounting": 6,
        "accounts": 2,
        "api": 5,
        "bank_stub": 4,
        "bi": 2,
        "billing": 39,
        "bookings": 2,
        "card-groups": 8,
        "cards": 1,
        "cases": 6,
        "clearing": 10,
        "client-groups": 8,
        "clients": 6,
        "closing-packages": 2,
        "commercial": 15,
        "contracts": 11,
        "crm": 51,
        "decision-memory": 3,
        "disputes": 5,
        "documents": 8,
        "edo": 12,
        "entitlements": 1,
        "erp_stub": 3,
        "explain": 1,
        "exports": 4,
        "fleet": 10,
        "fleet-control": 5,
        "fleet-intelligence": 10,
        "fraud": 3,
        "fuel": 22,
        "integration": 4,
        "integrations": 8,
        "invoice-threads": 1,
        "invoices": 1,
        "ledger": 4,
        "legal": 9,
        "legal-graph": 4,
        "limits": 5,
        "logistics": 4,
        "me": 1,
        "merchants": 6,
        "notifications": 8,
        "operations": 3,
        "ops": 12,
        "partners": 17,
        "payouts": 2,
        "pricing": 8,
        "products": 2,
        "reconciliation-requests": 3,
        "refunds": 1,
        "revenue": 3,
        "reversals": 1,
        "risk": 6,
        "risk-v5": 3,
        "seed": 1,
        "settlement": 7,
        "settlements": 2,
        "terminals": 6,
        "transactions": 1,
        "what-if": 1,
    }

    hidden_root_families, hidden_root_schema_counts = _admin_family_counts("/v1/admin/")
    public_compat_families, public_compat_schema_counts = _admin_family_counts("/api/v1/admin/")

    assert hidden_root_families == expected_hidden_root_families
    assert hidden_root_schema_counts == {True: 0, False: 349}
    assert public_compat_families == expected_public_compat_families
    assert public_compat_schema_counts == {True: 399, False: 0}


def test_unified_rules_nested_tail_has_canonical_admin_parity_without_public_widening() -> None:
    canonical_routes = {
        ("GET", "/api/core/v1/admin/rules/versions"),
        ("POST", "/api/core/v1/admin/rules/versions"),
        ("POST", "/api/core/v1/admin/rules/versions/{version_id}/activate"),
        ("POST", "/api/core/v1/admin/rules/versions/{version_id}/publish"),
        ("POST", "/api/core/v1/admin/rules/rules"),
    }
    core_nested_tails = {
        ("GET", "/api/core/v1/admin/api/v1/admin/rules/versions"),
        ("POST", "/api/core/v1/admin/api/v1/admin/rules/versions"),
        ("POST", "/api/core/v1/admin/api/v1/admin/rules/versions/{version_id}/activate"),
        ("POST", "/api/core/v1/admin/api/v1/admin/rules/versions/{version_id}/publish"),
        ("POST", "/api/core/v1/admin/api/v1/admin/rules/rules"),
    }
    public_nested_tails = {
        ("GET", "/api/v1/admin/api/v1/admin/rules/versions"),
        ("POST", "/api/v1/admin/api/v1/admin/rules/versions"),
        ("POST", "/api/v1/admin/api/v1/admin/rules/versions/{version_id}/activate"),
        ("POST", "/api/v1/admin/api/v1/admin/rules/versions/{version_id}/publish"),
        ("POST", "/api/v1/admin/api/v1/admin/rules/rules"),
    }
    hidden_root_nested_tails = {
        ("GET", "/v1/admin/api/v1/admin/rules/versions"),
        ("POST", "/v1/admin/api/v1/admin/rules/versions"),
        ("POST", "/v1/admin/api/v1/admin/rules/versions/{version_id}/activate"),
        ("POST", "/v1/admin/api/v1/admin/rules/versions/{version_id}/publish"),
        ("POST", "/v1/admin/api/v1/admin/rules/rules"),
    }

    for method, path in canonical_routes | core_nested_tails | public_nested_tails:
        route = _route(path, method)
        assert route.include_in_schema is True

    for method, path in hidden_root_nested_tails:
        route = _route(path, method)
        assert route.include_in_schema is False

    assert _find_route("/api/v1/admin/rules/versions", "GET") is None
    assert _find_route("/v1/admin/rules/versions", "GET") is None
