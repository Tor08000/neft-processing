from app.main import app


def test_app_smoke_import_and_routes() -> None:
    assert app is not None

    paths = [route.path for route in app.router.routes if hasattr(route, "path")]
    assert paths
    assert any(path.startswith("/api/v1/admin") for path in paths)
    assert any(path.startswith("/client/api/v1") for path in paths)
    assert any(path.startswith("/api/v1/client/me") for path in paths)
    assert "/api/core/portal/me" in paths
    assert "/api/core/client/me" in paths
    assert "/api/client/invoices" in paths
    assert "/api/core/client/invoices" in paths
    assert "/api/core/client/marketplace/orders/{order_id}/sla" in paths
    assert "/api/core/client/marketplace/orders/{order_id}/consequences" in paths
    assert "/api/client/fleet/cards" in paths
    assert "/api/core/client/fleet/cards" not in paths
    assert "/api/client/onboarding/state" in paths
    assert "/api/client/marketplace/recommendations" in paths
    assert "/api/client/marketplace/events" in paths
    assert "/api/marketplace/client/recommendations" in paths
    assert "/api/marketplace/client/events" in paths
    assert "/v1/marketplace/client/recommendations" in paths
    assert "/v1/marketplace/client/events" in paths
    assert "/api/core/v1/marketplace/client/recommendations" in paths
    assert "/api/core/v1/marketplace/client/events" in paths
    assert "/api/core/client/onboarding/status" in paths
    assert "/api/core/client/auth/verify" in paths
    assert "/api/core/partner/auth/verify" in paths
    assert "/api/core/admin/auth/verify" in paths
    assert "/api/core/v1/admin/auth/verify" in paths
    assert "/api/core/v1/admin/runtime/summary" in paths
    assert "/api/core/v1/admin/legal/documents" in paths
    assert "/api/core/v1/admin/logistics/orders/{order_id}/inspection" in paths
    assert "/api/partner/acts" in paths
    assert "/api/partner/balance" in paths
    assert "/api/partner/invoices" in paths
    assert "/api/partner/ledger" in paths
    assert "/api/partner/payouts" in paths
    assert "/api/partner/payouts/preview" in paths
    assert "/api/core/partner/acts" in paths
    assert "/api/core/partner/balance" in paths
    assert "/api/core/partner/finance/dashboard" in paths
    assert "/api/core/partner/invoices" in paths
    assert "/api/core/partner/ledger" in paths
    assert "/api/core/partner/payouts" in paths
    assert "/api/core/partner/payouts/preview" in paths
    assert "/api/partner/contracts" in paths
    assert "/api/partner/contracts/{contract_id}" in paths
    assert "/api/partner/settlements" in paths
    assert "/api/partner/settlements/{settlement_id}" in paths
    assert "/api/core/partner/contracts" in paths
    assert "/api/core/partner/contracts/{contract_id}" in paths
    assert "/api/core/partner/settlements" in paths
    assert "/api/core/partner/settlements/{settlement_id}" in paths
    assert "/api/core/partner/self-profile" in paths
    assert "/api/core/partner/users" in paths
    assert "/api/core/partner/terms" in paths
    assert "/api/v1/partner/fuel/stations/{station_id}/prices" in paths
    assert "/api/v1/partner/fuel/stations/{station_id}/prices/import" in paths
    assert "/portal/me" not in paths
    assert "/client/auth/verify" not in paths
    assert "/partner/auth/verify" not in paths
    assert "/admin/auth/verify" not in paths
    assert "/v1/admin/auth/verify" not in paths
    assert "/v1/admin/runtime/summary" not in paths
    assert "/v1/admin/merchants" not in paths
    assert "/api/core/v1/admin/merchants" in paths
    assert "/v1/admin/terminals" not in paths
    assert "/api/core/v1/admin/terminals" in paths
    assert "/v1/admin/terminals/{terminal_id}" not in paths
    assert "/api/core/v1/admin/terminals/{terminal_id}" in paths
    assert "/v1/admin/audit" not in paths
    assert "/api/core/v1/admin/audit" in paths
    assert "/api/v1/admin/audit" not in paths
    assert "/v1/admin/billing/summary" not in paths
    assert "/api/core/v1/admin/billing/summary" in paths
    assert "/v1/admin/finance/overview" not in paths
    assert "/api/core/v1/admin/finance/overview" in paths
    assert "/v1/admin/finance/payouts" not in paths
    assert "/api/core/v1/admin/finance/payouts" in paths
    assert "/api/v1/admin/finance/overview" not in paths
    assert "/api/v1/admin/finance/payouts" not in paths
    assert "/v1/admin/commercial/orgs/{org_id}" not in paths
    assert "/api/core/v1/admin/commercial/orgs/{org_id}" in paths
    assert "/v1/admin/commercial/orgs/{org_id}/plan" not in paths
    assert "/api/core/v1/admin/commercial/orgs/{org_id}/plan" in paths
    assert "/v1/admin/commercial/orgs/{org_id}/entitlements/recompute" not in paths
    assert "/api/core/v1/admin/commercial/orgs/{org_id}/entitlements/recompute" in paths
    assert "/v1/admin/clients/{client_id}/invitations" not in paths
    assert "/api/core/v1/admin/clients/{client_id}/invitations" in paths
    assert "/v1/admin/clients/invitations/{invitation_id}/resend" not in paths
    assert "/api/core/v1/admin/clients/invitations/{invitation_id}/resend" in paths
    assert "/v1/admin/clients/invitations/{invitation_id}/revoke" not in paths
    assert "/api/core/v1/admin/clients/invitations/{invitation_id}/revoke" in paths
    assert "/v1/admin/me" not in paths
    assert "/api/core/v1/admin/me" in paths
    assert "/api/v1/admin/me" in paths
    assert "/v1/admin/ops/summary" not in paths
    assert "/api/core/v1/admin/ops/summary" in paths
    assert "/v1/admin/legal/partners" not in paths
    assert "/api/core/v1/admin/legal/partners" in paths
    assert "/v1/admin/legal/partners/{partner_id}" not in paths
    assert "/api/core/v1/admin/legal/partners/{partner_id}" in paths
    assert "/v1/admin/legal/partners-legacy" not in paths
    assert "/api/core/v1/admin/legal/partners-legacy" in paths
    assert "/v1/admin/legal/documents" not in paths
    assert "/api/core/v1/admin/legal/documents" in paths
    assert "/api/v1/admin/legal/documents" not in paths
    assert "/v1/admin/marketplace/moderation/queue" not in paths
    assert "/api/core/v1/admin/marketplace/moderation/queue" in paths
    assert "/api/v1/admin/marketplace/moderation/queue" not in paths
    assert "/v1/admin/money/health" not in paths
    assert "/api/core/v1/admin/money/health" in paths
    assert "/api/v1/admin/money/health" not in paths
    assert "/api/core/admin/me" not in paths
    assert "/api/core/admin/runtime/summary" not in paths
    assert "/api/core/admin/finance/overview" not in paths
    assert "/api/core/admin/legal/partners" not in paths
    assert "/api/core/admin/audit" not in paths
    assert "/api/core/partner/dashboard" not in paths
    assert "/api/partner/dashboard" in paths
    assert "/v1/admin/reconciliation/runs" not in paths
    assert "/api/core/v1/admin/reconciliation/runs" in paths
    assert "/api/v1/admin/reconciliation/runs" not in paths
    assert any(path.startswith("/api/v1/client/documents") for path in paths)
    assert any(path.startswith("/api/core/client/documents") for path in paths)
    assert "/api/v1/client/closing-packages/{package_id}/ack" in paths
    assert "/api/core/client/documents/{document_id}/submit" in paths
    assert "/api/core/client/documents/{document_id}/ack" in paths
