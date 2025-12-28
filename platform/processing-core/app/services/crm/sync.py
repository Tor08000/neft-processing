from __future__ import annotations

from datetime import time

from sqlalchemy.orm import Session

from app.models.crm import CRMContract, CRMFeatureFlagType
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.fuel import (
    FuelCard,
    FuelCardGroup,
    FuelCardGroupStatus,
    FuelCardStatus,
    FuelLimit,
    FuelRiskProfile,
)
from app.services.audit_service import RequestContext
from app.services.crm import events, repository


def apply_contract(db: Session, *, contract: CRMContract, request_ctx: RequestContext | None) -> None:
    _apply_limit_profile(db, contract=contract, request_ctx=request_ctx)
    _apply_risk_profile(db, contract=contract, request_ctx=request_ctx)
    _apply_feature_flags(db, contract=contract, request_ctx=request_ctx)


def disable_contract_features(db: Session, *, contract: CRMContract, request_ctx: RequestContext | None) -> None:
    for feature in (
        CRMFeatureFlagType.FUEL_ENABLED,
        CRMFeatureFlagType.LOGISTICS_ENABLED,
        CRMFeatureFlagType.DOCUMENTS_ENABLED,
        CRMFeatureFlagType.RISK_BLOCKING_ENABLED,
        CRMFeatureFlagType.ACCOUNTING_EXPORT_ENABLED,
    ):
        repository.set_feature_flag(
            db,
            tenant_id=contract.tenant_id,
            client_id=contract.client_id,
            feature=feature,
            enabled=False,
            updated_by=request_ctx.actor_id if request_ctx else None,
        )
        events.audit_event(
            db,
            event_type=events.CRM_FEATURE_DISABLED,
            entity_type="crm_feature_flag",
            entity_id=f"{contract.client_id}:{feature.value}",
            payload={"enabled": False, "feature": feature.value},
            request_ctx=request_ctx,
        )


def _apply_limit_profile(db: Session, *, contract: CRMContract, request_ctx: RequestContext | None) -> None:
    if not contract.limit_profile_id:
        return
    profile = repository.get_limit_profile(db, profile_id=str(contract.limit_profile_id))
    if not profile:
        return
    definition = profile.definition or {}
    rules = _normalize_limit_rules(definition)
    if not rules:
        return
    desired_limits = _expand_limits(
        db,
        tenant_id=contract.tenant_id,
        client_id=contract.client_id,
        profile_id=str(profile.id),
        rules=rules,
    )
    existing = (
        db.query(FuelLimit)
        .filter(FuelLimit.client_id == contract.client_id)
        .filter(FuelLimit.active.is_(True))
        .all()
    )
    existing_by_key = {
        _limit_identity(limit): limit for limit in existing if _limit_profile_id(limit) == str(profile.id)
    }
    desired_keys = set()
    for limit in desired_limits:
        key = _limit_identity(limit)
        desired_keys.add(key)
        if key in existing_by_key:
            continue
        db.add(limit)
    for key, limit in existing_by_key.items():
        if key not in desired_keys:
            limit.active = False
            db.add(limit)
    db.commit()
    events.audit_event(
        db,
        event_type=events.CRM_PROFILE_APPLIED,
        entity_type="crm_limit_profile",
        entity_id=str(profile.id),
        payload={"contract_id": str(contract.id), "client_id": contract.client_id},
        request_ctx=request_ctx,
    )


def _apply_risk_profile(db: Session, *, contract: CRMContract, request_ctx: RequestContext | None) -> None:
    if not contract.risk_profile_id:
        return
    profile = repository.get_risk_profile(db, profile_id=str(contract.risk_profile_id))
    if not profile:
        return
    definition = _extract_risk_profile_definition(profile.meta)
    thresholds_override = _thresholds_override_from_definition(definition)
    signal_inputs = definition.get("signal_inputs") if definition else None
    if signal_inputs:
        thresholds_override = {**thresholds_override, "signal_inputs": signal_inputs}
    existing = (
        db.query(FuelRiskProfile)
        .filter(FuelRiskProfile.client_id == contract.client_id)
        .one_or_none()
    )
    if existing:
        existing.policy_id = profile.risk_policy_id
        existing.thresholds_override = thresholds_override or None
        existing.enabled = True
        db.add(existing)
    else:
        db.add(
            FuelRiskProfile(
                client_id=contract.client_id,
                policy_id=profile.risk_policy_id,
                thresholds_override=thresholds_override or None,
                enabled=True,
            )
        )
    db.commit()
    events.audit_event(
        db,
        event_type=events.CRM_PROFILE_APPLIED,
        entity_type="crm_risk_profile",
        entity_id=str(profile.id),
        payload={"contract_id": str(contract.id), "client_id": contract.client_id},
        request_ctx=request_ctx,
    )


def _apply_feature_flags(db: Session, *, contract: CRMContract, request_ctx: RequestContext | None) -> None:
    subscription = repository.get_active_subscription(db, client_id=contract.client_id)
    domains_payload: dict[str, bool] = {}
    if subscription:
        tariff = repository.get_tariff(db, tariff_id=subscription.tariff_plan_id)
        domains_payload = _resolve_tariff_domains(tariff)

    def _flag_from_payload(key: str) -> bool:
        value = domains_payload.get(key)
        if isinstance(value, bool):
            return value
        return False

    enable_map = {
        CRMFeatureFlagType.FUEL_ENABLED: _flag_from_payload("fuel_enabled"),
        CRMFeatureFlagType.LOGISTICS_ENABLED: _flag_from_payload("logistics_enabled"),
        CRMFeatureFlagType.DOCUMENTS_ENABLED: _flag_from_payload("documents_enabled") or contract.documents_required,
        CRMFeatureFlagType.RISK_BLOCKING_ENABLED: _flag_from_payload("risk_blocking_enabled")
        or bool(contract.risk_profile_id),
        CRMFeatureFlagType.ACCOUNTING_EXPORT_ENABLED: _flag_from_payload("accounting_export_enabled"),
    }
    if not enable_map[CRMFeatureFlagType.FUEL_ENABLED]:
        enable_map[CRMFeatureFlagType.FUEL_ENABLED] = True
    for feature, enabled in enable_map.items():
        record = repository.set_feature_flag(
            db,
            tenant_id=contract.tenant_id,
            client_id=contract.client_id,
            feature=feature,
            enabled=enabled,
            updated_by=request_ctx.actor_id if request_ctx else None,
        )
        events.audit_event(
            db,
            event_type=events.CRM_FEATURE_ENABLED if record.enabled else events.CRM_FEATURE_DISABLED,
            entity_type="crm_feature_flag",
            entity_id=f"{contract.client_id}:{feature.value}",
            payload={"enabled": record.enabled, "feature": feature.value},
            request_ctx=request_ctx,
        )


def _resolve_tariff_domains(tariff) -> dict[str, bool]:
    if not tariff:
        return {}
    if isinstance(tariff.definition, dict):
        domains = tariff.definition.get("domains")
        if isinstance(domains, dict):
            return {str(key): bool(value) for key, value in domains.items()}
    if isinstance(tariff.features, dict):
        return {
            "fuel_enabled": bool(tariff.features.get("fuel")),
            "logistics_enabled": bool(tariff.features.get("logistics")),
            "documents_enabled": bool(tariff.features.get("docs") or tariff.features.get("documents")),
            "accounting_export_enabled": bool(tariff.features.get("export") or tariff.features.get("accounting")),
            "risk_blocking_enabled": bool(tariff.features.get("risk")),
        }
    return {}


def _extract_risk_profile_definition(meta: dict | None) -> dict:
    if not meta:
        return {}
    definition = meta.get("definition")
    return definition if isinstance(definition, dict) else {}


def _thresholds_override_from_definition(definition: dict) -> dict:
    thresholds_hint = definition.get("thresholds_hint") if isinstance(definition, dict) else None
    if not isinstance(thresholds_hint, dict):
        return {}
    return {
        "allow": thresholds_hint.get("allow_max"),
        "review": thresholds_hint.get("review_max"),
        "block": thresholds_hint.get("block_min"),
    }


def _normalize_limit_rules(definition: dict) -> list[dict]:
    if not isinstance(definition, dict):
        return []
    if "rules" in definition and isinstance(definition["rules"], list):
        return definition["rules"]
    if "limits" in definition and isinstance(definition["limits"], list):
        return definition["limits"]
    return []


def _expand_limits(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    profile_id: str,
    rules: list[dict],
) -> list[FuelLimit]:
    limits: list[FuelLimit] = []
    card_groups = _list_active_groups(db, client_id=client_id)
    cards = _list_active_cards(db, client_id=client_id)
    vehicles = _list_active_vehicles(db, client_id=client_id)
    drivers = _list_active_drivers(db, client_id=client_id)

    for idx, rule in enumerate(rules):
        scope_type = rule.get("scope_type")
        scope_selector = rule.get("scope_selector") or {}
        scope_mode = scope_selector.get("mode")
        scope_ids = _resolve_scope_ids(
            scope_type,
            scope_mode,
            card_groups=card_groups,
            cards=cards,
            vehicles=vehicles,
            drivers=drivers,
        )
        for scope_id in scope_ids:
            limits.append(
                _build_limit(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    profile_id=profile_id,
                    rule_index=idx,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    rule=rule,
                )
            )
    return limits


def _resolve_scope_ids(
    scope_type: str | None,
    scope_mode: str | None,
    *,
    card_groups: list[FuelCardGroup],
    cards: list[FuelCard],
    vehicles: list[FleetVehicle],
    drivers: list[FleetDriver],
) -> list[str | None]:
    if scope_type == "CLIENT":
        return [None]
    if scope_type == "CARD_GROUP" and scope_mode == "GROUP_ALL":
        return [str(group.id) for group in card_groups]
    if scope_type == "CARD" and scope_mode == "EACH_CARD":
        return [str(card.id) for card in cards]
    if scope_type == "VEHICLE" and scope_mode == "EACH_VEHICLE":
        return [str(vehicle.id) for vehicle in vehicles]
    if scope_type == "DRIVER" and scope_mode == "EACH_DRIVER":
        return [str(driver.id) for driver in drivers]
    return []


def _build_limit(
    *,
    tenant_id: int,
    client_id: str,
    profile_id: str,
    rule_index: int,
    scope_type: str | None,
    scope_id: str | None,
    rule: dict,
) -> FuelLimit:
    constraints = rule.get("constraints") or {}
    timezone = constraints.get("timezone") or "Europe/Moscow"
    time_window_start = _parse_time(constraints.get("time_window_start"))
    time_window_end = _parse_time(constraints.get("time_window_end"))
    meta = {**(rule.get("meta") or {}), "crm_profile_id": profile_id, "crm_rule_index": rule_index}
    return FuelLimit(
        tenant_id=tenant_id,
        client_id=client_id,
        scope_type=rule.get("scope_type"),
        scope_id=scope_id,
        fuel_type_code=constraints.get("fuel_type"),
        station_id=constraints.get("station_id"),
        station_network_id=constraints.get("network_id"),
        limit_type=rule.get("limit_type"),
        period=rule.get("period"),
        value=rule.get("value"),
        currency=rule.get("currency"),
        priority=rule.get("priority", 100),
        active=True,
        time_window_start=time_window_start,
        time_window_end=time_window_end,
        timezone=timezone,
        meta=meta,
    )


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return time.fromisoformat(value)


def _list_active_cards(db: Session, *, client_id: str) -> list[FuelCard]:
    return (
        db.query(FuelCard)
        .filter(FuelCard.client_id == client_id)
        .filter(FuelCard.status == FuelCardStatus.ACTIVE)
        .all()
    )


def _list_active_groups(db: Session, *, client_id: str) -> list[FuelCardGroup]:
    return (
        db.query(FuelCardGroup)
        .filter(FuelCardGroup.client_id == client_id)
        .filter(FuelCardGroup.status == FuelCardGroupStatus.ACTIVE)
        .all()
    )


def _list_active_vehicles(db: Session, *, client_id: str) -> list[FleetVehicle]:
    return (
        db.query(FleetVehicle)
        .filter(FleetVehicle.client_id == client_id)
        .filter(FleetVehicle.status == FleetVehicleStatus.ACTIVE)
        .all()
    )


def _list_active_drivers(db: Session, *, client_id: str) -> list[FleetDriver]:
    return (
        db.query(FleetDriver)
        .filter(FleetDriver.client_id == client_id)
        .filter(FleetDriver.status == FleetDriverStatus.ACTIVE)
        .all()
    )


def _limit_profile_id(limit: FuelLimit) -> str | None:
    meta = limit.meta or {}
    return meta.get("crm_profile_id")


def _limit_identity(limit: FuelLimit) -> tuple:
    return (
        limit.client_id,
        str(limit.scope_type),
        str(limit.scope_id) if limit.scope_id else None,
        str(limit.limit_type),
        str(limit.period),
        int(limit.value) if limit.value is not None else None,
        str(limit.fuel_type_code) if limit.fuel_type_code else None,
        str(limit.station_id) if limit.station_id else None,
        str(limit.station_network_id) if limit.station_network_id else None,
        str(limit.currency) if limit.currency else None,
        int(limit.priority) if limit.priority is not None else None,
        limit.time_window_start.isoformat() if limit.time_window_start else None,
        limit.time_window_end.isoformat() if limit.time_window_end else None,
        str(limit.timezone) if limit.timezone else None,
    )


__all__ = ["apply_contract", "disable_contract_features"]
