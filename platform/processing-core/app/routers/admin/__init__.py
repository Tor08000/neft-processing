from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.routers.admin import (
    accounting_exports,
    accounts,
    billing,
    closing_packages,
    client_actions,
    clearing,
    crm,
    dashboard,
    disputes,
    documents,
    fuel,
    integration_monitoring,
    logistics,
    legal_graph,
    limits,
    ledger,
    merchants,
    operations,
    refunds,
    finance,
    reversals,
    risk_rules,
    risk_v5,
    settlements,
    legal_integrations,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin_user)])

router.include_router(accounts.router)
router.include_router(limits.router)
router.include_router(operations.router)
router.include_router(dashboard.router)
router.include_router(merchants.router)
router.include_router(clearing.router)
router.include_router(accounting_exports.router)
router.include_router(billing.router)
router.include_router(closing_packages.router)
router.include_router(risk_rules.router)
router.include_router(risk_v5.router)
router.include_router(integration_monitoring.router)
router.include_router(settlements.router)
router.include_router(refunds.router)
router.include_router(reversals.router)
router.include_router(disputes.router)
router.include_router(finance.router)
router.include_router(ledger.router)
router.include_router(fuel.router)
router.include_router(logistics.router)
router.include_router(client_actions.router)
router.include_router(documents.router)
router.include_router(legal_integrations.router)
router.include_router(legal_graph.router)
router.include_router(crm.router)

__all__ = ["router"]
