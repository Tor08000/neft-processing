from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.crm import CRMFeatureFlagType
from app.services.crm import repository


class DecisionContextNotFound(ValueError):
    pass


def build_decision_context(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
) -> dict[str, Any]:
    client = repository.get_client(db, tenant_id=tenant_id, client_id=client_id)
    if not client:
        raise DecisionContextNotFound("client_not_found")

    contract = repository.get_active_contract(db, client_id=client_id)
    subscription = repository.get_active_subscription(db, client_id=client_id)
    tariff = repository.get_tariff(db, tariff_id=subscription.tariff_plan_id) if subscription else None

    risk_profile = repository.get_risk_profile(db, profile_id=contract.risk_profile_id) if contract else None
    limit_profile = repository.get_limit_profile(db, profile_id=contract.limit_profile_id) if contract else None

    feature_flags = repository.list_feature_flags(db, tenant_id=tenant_id, client_id=client_id)
    flag_map = {flag.feature: flag.enabled for flag in feature_flags}

    enforcement_flags = {
        "fuel_enabled": bool(flag_map.get(CRMFeatureFlagType.FUEL_ENABLED)),
        "logistics_enabled": bool(flag_map.get(CRMFeatureFlagType.LOGISTICS_ENABLED)),
        "documents_enabled": bool(flag_map.get(CRMFeatureFlagType.DOCUMENTS_ENABLED)),
        "risk_blocking_enabled": bool(flag_map.get(CRMFeatureFlagType.RISK_BLOCKING_ENABLED)),
        "accounting_export_enabled": bool(flag_map.get(CRMFeatureFlagType.ACCOUNTING_EXPORT_ENABLED)),
        "subscription_meter_fuel_enabled": bool(
            flag_map.get(CRMFeatureFlagType.SUBSCRIPTION_METER_FUEL_ENABLED)
        ),
    }

    return {
        "client_id": client_id,
        "tenant_id": tenant_id,
        "active_contract": contract,
        "tariff": tariff,
        "feature_flags": feature_flags,
        "risk_profile": risk_profile,
        "limit_profile": limit_profile,
        "enforcement_flags": enforcement_flags,
    }


__all__ = ["DecisionContextNotFound", "build_decision_context"]
