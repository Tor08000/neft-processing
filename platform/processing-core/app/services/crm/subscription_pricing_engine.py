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


__all__ = ["PricingResult", "price_subscription"]
