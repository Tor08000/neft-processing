from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

from app.models.crm import (
    CRMSubscription,
    CRMSubscriptionCharge,
    CRMSubscriptionChargeType,
    CRMSubscriptionPeriodSegment,
    CRMSubscriptionSegmentStatus,
    CRMUsageCounter,
)
from app.services.crm.subscription_rules import apply_metric_rules


@dataclass(frozen=True)
class PricingResult:
    charges: list[CRMSubscriptionCharge]


def price_subscription(
    *,
    subscription: CRMSubscription,
    billing_period_id: str,
    counters: list[CRMUsageCounter],
    tariff_definition: dict,
    segments: list[CRMSubscriptionPeriodSegment] | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> PricingResult:
    charges: list[CRMSubscriptionCharge] = []
    active_days, period_days = _resolve_proration(segments, period_start, period_end)
    base_fee = tariff_definition.get("base_fee") if isinstance(tariff_definition, dict) else None
    if base_fee and (active_days is None or active_days > 0):
        amount = int(base_fee.get("amount_minor") or 0)
        if active_days is not None and period_days:
            amount = _apply_proration(amount, active_days=active_days, period_days=period_days)
        currency = base_fee.get("currency") or "RUB"
        if amount > 0:
            charges.append(
                CRMSubscriptionCharge(
                    subscription_id=subscription.id,
                    billing_period_id=billing_period_id,
                    charge_type=CRMSubscriptionChargeType.BASE_FEE,
                    code="BASE_FEE",
                    quantity=1,
                    unit_price=amount,
                    amount=amount,
                    currency=currency,
                    source={"tariff": subscription.tariff_plan_id, "base_fee": base_fee},
                )
            )

    included = tariff_definition.get("included") if isinstance(tariff_definition, dict) else {}
    overage_prices = tariff_definition.get("overage") if isinstance(tariff_definition, dict) else {}
    metric_rules = tariff_definition.get("metric_rules") if isinstance(tariff_definition, dict) else {}
    for counter in counters:
        metric_key = _metric_key(counter.metric.value)
        if not metric_key:
            continue
        raw_limit = included.get(metric_key)
        limit_value = int(raw_limit) if raw_limit is not None else 0
        if active_days is not None and period_days:
            limit_value = _apply_proration(limit_value, active_days=active_days, period_days=period_days)
        rule = _resolve_metric_rule(metric_rules, counter.metric.value, metric_key)
        if rule and not rule.get("billable", True):
            counter.limit_value = limit_value
            counter.overage = 0
            continue
        counter.value = _apply_metric_rule(counter.value, rule)
        limit_value = _apply_metric_rule(limit_value, rule)
        counter.limit_value = limit_value
        overage = max(int(counter.value) - limit_value, 0)
        counter.overage = overage
        if overage == 0:
            continue
        price_cfg = overage_prices.get(metric_key) if isinstance(overage_prices, dict) else None
        if not price_cfg:
            continue
        unit_price = int(price_cfg.get("unit_price_minor") or 0)
        currency = price_cfg.get("currency") or (base_fee.get("currency") if base_fee else "RUB")
        charges.append(
            CRMSubscriptionCharge(
                subscription_id=subscription.id,
                billing_period_id=billing_period_id,
                charge_type=CRMSubscriptionChargeType.OVERAGE,
                code=f"OVERAGE_{counter.metric.value}",
                quantity=overage,
                unit_price=unit_price,
                amount=int(overage * unit_price),
                currency=currency,
                source={
                    "metric": counter.metric.value,
                    "included": limit_value,
                    "value": int(counter.value),
                },
            )
        )

    return PricingResult(charges=charges)


def _resolve_proration(
    segments: list[CRMSubscriptionPeriodSegment] | None,
    period_start: datetime | None,
    period_end: datetime | None,
) -> tuple[int | None, int | None]:
    if not segments or not period_start or not period_end:
        return None, None
    period_days = _count_days(period_start, period_end)
    active_days = sum(
        segment.days_count for segment in segments if segment.status == CRMSubscriptionSegmentStatus.ACTIVE
    )
    return active_days, period_days


def _count_days(start_at: datetime, end_at: datetime) -> int:
    return (end_at.date() - start_at.date()).days + 1


def _apply_proration(amount: int, *, active_days: int, period_days: int) -> int:
    if period_days <= 0 or amount <= 0:
        return 0
    ratio = Decimal(active_days) / Decimal(period_days)
    return int((Decimal(amount) * ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _resolve_metric_rule(metric_rules: dict | None, metric: str, metric_key: str) -> dict | None:
    if not isinstance(metric_rules, dict):
        return None
    rule = metric_rules.get(metric)
    if isinstance(rule, dict):
        return rule
    rule = metric_rules.get(metric_key)
    return rule if isinstance(rule, dict) else None


def _apply_metric_rule(value: int | float, rule: dict | None) -> int:
    normalized = Decimal(str(value))
    if rule:
        multiplier = rule.get("multiplier")
        divisor = rule.get("divisor")
        if multiplier is not None:
            normalized *= Decimal(str(multiplier))
        if divisor:
            normalized /= Decimal(str(divisor))
        minimum = rule.get("min_value")
        maximum = rule.get("max_value")
        rounding = rule.get("rounding")
        if rounding == "ceil":
            rounding_mode = ROUND_CEILING
        elif rounding == "floor":
            rounding_mode = ROUND_FLOOR
        else:
            rounding_mode = ROUND_HALF_UP
        normalized = normalized.quantize(Decimal("1"), rounding=rounding_mode)
        if minimum is not None:
            normalized = max(normalized, Decimal(str(minimum)))
        if maximum is not None:
            normalized = min(normalized, Decimal(str(maximum)))
    return int(normalized)


def _metric_key(metric: str) -> str | None:
    mapping = {
        "CARDS_COUNT": "cards",
        "VEHICLES_COUNT": "vehicles",
        "DRIVERS_COUNT": "drivers",
        "FUEL_TX_COUNT": "fuel_tx",
        "FUEL_VOLUME": "fuel_volume",
        "LOGISTICS_ORDERS": "logistics_orders",
    }
    return mapping.get(metric)


@dataclass(frozen=True)
class PricingResultV2:
    charges: list[CRMSubscriptionCharge]


def price_subscription_v2(
    *,
    subscription: CRMSubscription,
    billing_period_id: str,
    segments: list[CRMSubscriptionPeriodSegment],
    counters: list[CRMUsageCounter],
    tariff_definition: dict,
    period_start: datetime,
    period_end: datetime,
) -> PricingResultV2:
    charges: list[CRMSubscriptionCharge] = []
    period_days = _count_days(period_start, period_end)
    included_map = _normalize_included(tariff_definition.get("included") or [])
    overage_prices = _normalize_overage(tariff_definition.get("overage") or [])
    metric_rules = tariff_definition.get("metric_rules") or []
    caps = _normalize_caps(tariff_definition.get("caps") or [])
    base_fee_cfg = tariff_definition.get("base_fee") or {}
    base_fee_amount = int(base_fee_cfg.get("amount_minor") or 0)
    currency = base_fee_cfg.get("currency") or "RUB"

    counters_by_segment = _group_counters_by_segment(counters)

    for segment in segments:
        if segment.status != CRMSubscriptionSegmentStatus.ACTIVE:
            continue
        segment_days = segment.days_count
        segment_key = _segment_key(segment)
        segment_counters = counters_by_segment.get(str(segment.id), [])
        usage_by_metric = {counter.metric.value: int(counter.value) for counter in segment_counters}

        rules_result = apply_metric_rules(
            usage_by_metric=usage_by_metric,
            overage_prices=overage_prices,
            rules=metric_rules,
        )
        segment_base_fee = _prorate_amount(base_fee_amount, segment_days, period_days)
        if segment_base_fee > 0:
            charges.append(
                CRMSubscriptionCharge(
                    subscription_id=subscription.id,
                    billing_period_id=billing_period_id,
                    segment_id=segment.id,
                    charge_type=CRMSubscriptionChargeType.BASE_FEE,
                    code="BASE_FEE",
                    charge_key=_charge_key(
                        subscription.id,
                        billing_period_id,
                        segment_key,
                        "BASE",
                        "BASE_FEE",
                    ),
                    quantity=1,
                    unit_price=segment_base_fee,
                    amount=segment_base_fee,
                    currency=currency,
                    source={"tariff": segment.tariff_plan_id},
                    explain={
                        "segment_days": segment_days,
                        "period_days": period_days,
                        "base_fee_minor": base_fee_amount,
                        "metric_rules": rules_result.applied_rules,
                    },
                )
            )
        for adjustment in rules_result.base_fee_adjustments:
            prorated_adjustment = _prorate_amount(int(adjustment), segment_days, period_days)
            if prorated_adjustment <= 0:
                continue
            charges.append(
                CRMSubscriptionCharge(
                    subscription_id=subscription.id,
                    billing_period_id=billing_period_id,
                    segment_id=segment.id,
                    charge_type=CRMSubscriptionChargeType.BASE_FEE,
                    code="RULE_ADJ",
                    charge_key=_charge_key(
                        subscription.id,
                        billing_period_id,
                        segment_key,
                        "RULE_ADJ",
                        "BASE_FEE",
                    ),
                    quantity=1,
                    unit_price=prorated_adjustment,
                    amount=prorated_adjustment,
                    currency=currency,
                    source={"tariff": segment.tariff_plan_id},
                    explain={
                        "segment_days": segment_days,
                        "period_days": period_days,
                        "adjustment_minor": int(adjustment),
                        "metric_rules": rules_result.applied_rules,
                    },
                )
            )

        for counter in segment_counters:
            metric_name = counter.metric.value
            included_value = included_map.get(metric_name)
            if included_value is None:
                continue
            proration_mode = included_value["proration"]
            limit_value = _prorate_included(included_value["value"], segment_days, period_days, proration_mode)
            counter.limit_value = limit_value
            overage = max(int(counter.value) - limit_value, 0)
            counter.overage = overage
            if overage == 0:
                continue
            unit_price = int(rules_result.overage_prices.get(metric_name) or 0)
            if unit_price <= 0:
                continue
            amount = int(overage * unit_price)
            cap_amount = caps.get(metric_name)
            if cap_amount is not None:
                amount = min(amount, cap_amount)
            charges.append(
                CRMSubscriptionCharge(
                    subscription_id=subscription.id,
                    billing_period_id=billing_period_id,
                    segment_id=segment.id,
                    charge_type=CRMSubscriptionChargeType.OVERAGE,
                    code=f"OVERAGE_{metric_name}",
                    charge_key=_charge_key(
                        subscription.id,
                        billing_period_id,
                        segment_key,
                        "OVERAGE",
                        metric_name,
                    ),
                    quantity=overage,
                    unit_price=unit_price,
                    amount=amount,
                    currency=currency,
                    source={"metric": metric_name, "included": limit_value, "value": int(counter.value)},
                    explain={
                        "segment_days": segment_days,
                        "period_days": period_days,
                        "included": limit_value,
                        "usage": int(counter.value),
                        "cap_amount_minor": cap_amount,
                        "metric_rules": rules_result.applied_rules,
                    },
                )
            )
    return PricingResultV2(charges=charges)


def _normalize_included(items: list[dict]) -> dict[str, dict]:
    normalized: dict[str, dict] = {}
    for item in items:
        metric = item.get("metric")
        if not metric:
            continue
        normalized[metric] = {"value": int(item.get("value") or 0), "proration": item.get("proration", "DAILY")}
    return normalized


def _normalize_overage(items: list[dict]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for item in items:
        metric = item.get("metric")
        if not metric:
            continue
        normalized[metric] = int(item.get("unit_price_minor") or 0)
    return normalized


def _normalize_caps(items: list[dict]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for item in items:
        metric = item.get("metric")
        if not metric:
            continue
        normalized[metric] = int(item.get("max_overage_amount_minor") or 0)
    return normalized


def _group_counters_by_segment(counters: list[CRMUsageCounter]) -> dict[str, list[CRMUsageCounter]]:
    grouped: dict[str, list[CRMUsageCounter]] = {}
    for counter in counters:
        if not counter.segment_id:
            continue
        key = str(counter.segment_id)
        grouped.setdefault(key, []).append(counter)
    return grouped


def _prorate_amount(amount: int, segment_days: int, period_days: int) -> int:
    if period_days <= 0 or amount <= 0:
        return 0
    return int((Decimal(amount) * Decimal(segment_days) / Decimal(period_days)).quantize(Decimal("1"), rounding=ROUND_FLOOR))


def _prorate_included(value: int, segment_days: int, period_days: int, proration: str) -> int:
    if period_days <= 0 or value <= 0:
        return 0
    result = Decimal(value) * Decimal(segment_days) / Decimal(period_days)
    if proration == "LINEAR":
        return int(result.quantize(Decimal("1"), rounding=ROUND_FLOOR))
    return int(result.quantize(Decimal("1"), rounding=ROUND_FLOOR))


def _segment_key(segment: CRMSubscriptionPeriodSegment) -> str:
    start = segment.segment_start.date().isoformat()
    end = segment.segment_end.date().isoformat()
    return f"{start}-{end}"


def _charge_key(subscription_id: str, period_id: str, segment_key: str, code: str, metric: str) -> str:
    return f"sub:{subscription_id}:period:{period_id}:seg:{segment_key}:code:{code}:{metric}"


__all__ = ["PricingResult", "PricingResultV2", "price_subscription", "price_subscription_v2"]
