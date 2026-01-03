from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.vehicle_maintenance import (
    MaintenanceItem,
    MaintenanceModifier,
    MaintenanceRule,
    VehicleMaintenanceDismissal,
    VehicleServiceRecord,
    VehicleUsageProfile,
)
from app.models.vehicle_profile import VehicleProfile


_STATUS_OK = "OK"
_STATUS_DUE_SOON = "DUE_SOON"
_STATUS_OVERDUE = "OVERDUE"
_STATUS_UNKNOWN = "UNKNOWN"

_SERVICE_THRESHOLDS_KM: dict[str, Decimal] = {
    "OIL_CHANGE": Decimal("1000"),
    "BRAKE_PADS_FRONT": Decimal("2000"),
    "BRAKE_PADS_REAR": Decimal("2000"),
    "BRAKE_DISCS": Decimal("2000"),
    "BELT_TIMING": Decimal("5000"),
    "BELT_ACCESSORY": Decimal("5000"),
}

_MONTH_DUE_SOON_DAYS = 30


@dataclass
class _RecommendationPayload:
    item: MaintenanceItem
    status: str
    interval_km: Decimal | None
    interval_months: int | None
    effective_interval_km: Decimal | None
    effective_interval_months: int | None
    last_service_km: Decimal | None
    last_service_at: datetime | None
    current_km: Decimal
    due_km: Decimal | None
    due_in_km: Decimal | None
    overdue_km: Decimal | None
    due_at: datetime | None
    due_in_months: int | None
    explain: str


def _add_months(ts: datetime, months: int) -> datetime:
    month = ts.month - 1 + months
    year = ts.year + month // 12
    month = month % 12 + 1
    day = min(ts.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return ts.replace(year=year, month=month, day=day)


def _now_for(ts: datetime | None) -> datetime:
    if ts is not None and ts.tzinfo is not None:
        return datetime.now(tz=ts.tzinfo)
    return datetime.now(tz=timezone.utc)


def _load_usage_conditions(profile: VehicleUsageProfile | None) -> set[str]:
    conditions: set[str] = set()
    if not profile:
        return conditions
    if profile.usage_type:
        usage = profile.usage_type.lower()
        if usage == "city":
            conditions.add("CITY")
        if usage == "aggressive":
            conditions.add("AGGRESSIVE")
    if profile.aggressiveness_score is not None and Decimal(profile.aggressiveness_score) >= Decimal("0.7"):
        conditions.add("AGGRESSIVE")
    if profile.heavy_load_flag:
        conditions.add("HEAVY_LOAD")
    if profile.climate_zone and profile.climate_zone.lower() == "cold":
        conditions.add("COLD")
    return conditions


def _matches_rule(rule: MaintenanceRule, vehicle: VehicleProfile) -> bool:
    if rule.brand and rule.brand != vehicle.brand:
        return False
    if rule.model and rule.model != vehicle.model:
        return False
    if rule.generation and rule.generation != vehicle.generation:
        return False
    if rule.year_from is not None:
        if vehicle.year is None or vehicle.year < rule.year_from:
            return False
    if rule.year_to is not None:
        if vehicle.year is None or vehicle.year > rule.year_to:
            return False
    if rule.engine_type:
        if vehicle.engine_type is None or rule.engine_type != vehicle.engine_type.value:
            return False
    if rule.engine_volume_from is not None:
        if vehicle.engine_volume is None or Decimal(vehicle.engine_volume) < Decimal(rule.engine_volume_from):
            return False
    if rule.engine_volume_to is not None:
        if vehicle.engine_volume is None or Decimal(vehicle.engine_volume) > Decimal(rule.engine_volume_to):
            return False
    if rule.transmission:
        if vehicle.transmission is None or rule.transmission != vehicle.transmission:
            return False
    if rule.drive_type:
        if vehicle.drive_type is None or rule.drive_type != vehicle.drive_type:
            return False
    return True


def _rule_specificity(rule: MaintenanceRule) -> int:
    fields = [
        rule.brand,
        rule.model,
        rule.generation,
        rule.year_from,
        rule.year_to,
        rule.engine_type,
        rule.engine_volume_from,
        rule.engine_volume_to,
        rule.transmission,
        rule.drive_type,
        rule.conditions,
    ]
    return sum(1 for field in fields if field is not None)


def _select_best_rule(rules: list[MaintenanceRule], vehicle: VehicleProfile) -> MaintenanceRule | None:
    candidates = [rule for rule in rules if _matches_rule(rule, vehicle)]
    if not candidates:
        return None
    candidates.sort(
        key=lambda rule: (
            rule.priority,
            -_rule_specificity(rule),
            rule.created_at or datetime.min,
        )
    )
    return candidates[0]


def _resolve_last_service(records: list[VehicleServiceRecord]) -> VehicleServiceRecord | None:
    if not records:
        return None
    by_km = [record for record in records if record.service_at_km is not None]
    if by_km:
        return max(by_km, key=lambda record: Decimal(record.service_at_km))
    by_date = [record for record in records if record.service_at is not None]
    if by_date:
        return max(by_date, key=lambda record: record.service_at)
    return max(records, key=lambda record: record.created_at)


def _apply_modifiers(
    modifiers: list[MaintenanceModifier],
    conditions: set[str],
) -> tuple[Decimal, list[MaintenanceModifier]]:
    factor = Decimal("1")
    applied: list[MaintenanceModifier] = []
    for modifier in modifiers:
        if modifier.condition_code in conditions:
            factor *= Decimal(modifier.factor)
            applied.append(modifier)
    return factor, applied


def _interval_explain(
    base_km: Decimal | None,
    base_months: int | None,
    effective_km: Decimal | None,
    effective_months: int | None,
    applied_modifiers: list[MaintenanceModifier],
) -> str:
    parts: list[str] = []
    if base_km is not None:
        parts.append(f"Базовый интервал: {base_km:.0f} км.")
    if base_months is not None:
        parts.append(f"Базовый интервал: {base_months} мес.")
    if applied_modifiers and effective_km is not None:
        codes = ", ".join(sorted({modifier.condition_code for modifier in applied_modifiers}))
        parts.append(f"С учетом условий ({codes}): {effective_km:.0f} км.")
    if applied_modifiers and effective_months is not None:
        codes = ", ".join(sorted({modifier.condition_code for modifier in applied_modifiers}))
        parts.append(f"С учетом условий ({codes}): {effective_months} мес.")
    return " ".join(parts)


def build_vehicle_maintenance_recommendations(
    db: Session,
    *,
    vehicle: VehicleProfile,
) -> list[_RecommendationPayload]:
    items = db.query(MaintenanceItem).order_by(MaintenanceItem.code.asc()).all()
    if not items:
        return []

    rules = db.query(MaintenanceRule).all()
    modifiers = db.query(MaintenanceModifier).all()
    profile = db.query(VehicleUsageProfile).filter(VehicleUsageProfile.vehicle_id == vehicle.id).one_or_none()
    conditions = _load_usage_conditions(profile)

    records = db.query(VehicleServiceRecord).filter(VehicleServiceRecord.vehicle_id == vehicle.id).all()
    record_map: dict[str, list[VehicleServiceRecord]] = {}
    for record in records:
        record_map.setdefault(record.item_code, []).append(record)

    dismissals = db.query(VehicleMaintenanceDismissal).filter(
        VehicleMaintenanceDismissal.vehicle_id == vehicle.id
    ).all()
    dismissal_map: dict[str, VehicleMaintenanceDismissal] = {}
    for dismissal in dismissals:
        existing = dismissal_map.get(dismissal.item_code)
        if not existing or existing.dismissed_at < dismissal.dismissed_at:
            dismissal_map[dismissal.item_code] = dismissal

    modifier_map: dict[str, list[MaintenanceModifier]] = {}
    for modifier in modifiers:
        modifier_map.setdefault(modifier.item_code, []).append(modifier)

    recommendations: list[_RecommendationPayload] = []
    current_km = Decimal(vehicle.current_odometer_km)

    for item in items:
        item_records = record_map.get(item.code, [])
        last_service = _resolve_last_service(item_records)
        last_service_km = Decimal(last_service.service_at_km) if last_service and last_service.service_at_km is not None else None
        last_service_at = last_service.service_at if last_service else None

        dismissal = dismissal_map.get(item.code)
        if dismissal and last_service_at and dismissal.dismissed_at > last_service_at:
            continue
        if dismissal and last_service_at is None and dismissal.dismissed_at:
            continue

        item_rules = [rule for rule in rules if rule.item_code == item.code]
        rule = _select_best_rule(item_rules, vehicle)
        base_km = Decimal(rule.interval_km) if rule and rule.interval_km is not None else None
        base_months = rule.interval_months if rule and rule.interval_months is not None else None
        if base_km is None:
            base_km = Decimal(item.default_interval_km) if item.default_interval_km is not None else None
        if base_months is None:
            base_months = item.default_interval_months

        factor, applied_modifiers = _apply_modifiers(modifier_map.get(item.code, []), conditions)
        effective_km = base_km * factor if base_km is not None else None
        effective_months = base_months

        if last_service_km is None:
            last_service_km = Decimal(vehicle.start_odometer_km)

        due_km = last_service_km + effective_km if effective_km is not None else None
        due_in_km = due_km - current_km if due_km is not None else None
        overdue_km = None

        due_at = None
        due_in_months = None
        if effective_months is not None and last_service_at is not None:
            due_at = _add_months(last_service_at, effective_months)
            now = _now_for(due_at)
            days_left = (due_at - now).days
            due_in_months = max(int(days_left / 30), 0)

        status = _STATUS_OK
        threshold_km = _SERVICE_THRESHOLDS_KM.get(item.code, Decimal("500"))

        if effective_km is None and effective_months is None:
            status = _STATUS_UNKNOWN
        else:
            status = _STATUS_OK
            if due_in_km is not None:
                if due_in_km <= 0:
                    status = _STATUS_OVERDUE
                    overdue_km = abs(due_in_km)
                elif due_in_km <= threshold_km:
                    status = _STATUS_DUE_SOON
            if due_at is not None:
                now = _now_for(due_at)
                if due_at <= now:
                    status = _STATUS_OVERDUE
                elif (due_at - now).days <= _MONTH_DUE_SOON_DAYS:
                    if status != _STATUS_OVERDUE:
                        status = _STATUS_DUE_SOON

        if not item_records:
            status = _STATUS_UNKNOWN

        interval_explain = _interval_explain(base_km, base_months, effective_km, effective_months, applied_modifiers)
        distance_part = ""
        if due_in_km is not None:
            if due_in_km >= 0:
                distance_part = f"До следующего обслуживания примерно {due_in_km:.0f} км."
            else:
                distance_part = f"Просрочено примерно на {abs(due_in_km):.0f} км."
        elif due_at is not None:
            now = _now_for(due_at)
            if due_at >= now:
                distance_part = "Срок по времени еще не наступил."
            else:
                distance_part = "Срок по времени просрочен."

        explain_parts = [part for part in [interval_explain, distance_part] if part]
        explain = " ".join(explain_parts) if explain_parts else "Интервал обслуживания не задан."

        recommendations.append(
            _RecommendationPayload(
                item=item,
                status=status,
                interval_km=base_km,
                interval_months=base_months,
                effective_interval_km=effective_km,
                effective_interval_months=effective_months,
                last_service_km=last_service_km,
                last_service_at=last_service_at,
                current_km=current_km,
                due_km=due_km,
                due_in_km=due_in_km,
                overdue_km=overdue_km,
                due_at=due_at,
                due_in_months=due_in_months,
                explain=explain,
            )
        )

    return recommendations
