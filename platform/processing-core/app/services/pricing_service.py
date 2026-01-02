from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.commercial_layer import CommercialPlan, PlanFeature, UsageCounter, UsageMetric
from app.models.contract_limits import TariffPrice


@dataclass
class PriceQuote:
    """Resolved price for a tariff/product combination."""

    client_price_per_liter: Decimal
    cost_price_per_liter: Decimal | None
    currency: str
    tariff_price: TariffPrice


def _to_decimal(value: Decimal | float | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _pick_price(
    db: Session,
    *,
    tariff_id: str,
    product_id: str,
    occurred_at: datetime,
    partner_id: Optional[str] = None,
    azs_id: Optional[str] = None,
) -> TariffPrice | None:
    query = (
        db.query(TariffPrice)
        .filter(TariffPrice.tariff_id == tariff_id)
        .filter(TariffPrice.product_id == product_id)
        .filter(or_(TariffPrice.valid_from.is_(None), TariffPrice.valid_from <= occurred_at))
        .filter(or_(TariffPrice.valid_to.is_(None), TariffPrice.valid_to >= occurred_at))
    )

    if azs_id is not None:
        scoped = (
            query.filter(TariffPrice.azs_id == azs_id)
            .order_by(TariffPrice.priority.asc(), TariffPrice.valid_from.desc().nullslast())
            .first()
        )
        if scoped:
            return scoped

    if partner_id is not None:
        scoped = (
            query.filter(TariffPrice.partner_id == partner_id)
            .order_by(TariffPrice.priority.asc(), TariffPrice.valid_from.desc().nullslast())
            .first()
        )
        if scoped:
            return scoped

    return (
        query.filter(TariffPrice.partner_id.is_(None)).filter(TariffPrice.azs_id.is_(None))
        .order_by(TariffPrice.priority.asc(), TariffPrice.valid_from.desc().nullslast())
        .first()
    )


def get_effective_price(
    db: Session,
    *,
    tariff_id: str,
    product_id: str,
    occurred_at: datetime,
    partner_id: Optional[str] = None,
    azs_id: Optional[str] = None,
) -> PriceQuote:
    """
    Resolve the most specific price for the provided context.

    Priority of resolution:
    1) AZS-specific price when ``azs_id`` is provided.
    2) Partner-scoped price when ``partner_id`` is provided.
    3) General tariff price (no partner/azs bindings).

    Within the scope, prices are ordered by ascending ``priority`` and then by
    the most recent ``valid_from`` value.
    """

    price = _pick_price(
        db,
        tariff_id=tariff_id,
        product_id=product_id,
        partner_id=partner_id,
        azs_id=azs_id,
        occurred_at=occurred_at,
    )
    if not price:
        raise ValueError("PRICE_NOT_FOUND")

    return PriceQuote(
        client_price_per_liter=_to_decimal(price.price_per_liter),
        cost_price_per_liter=_to_decimal(price.cost_price_per_liter)
        if price.cost_price_per_liter is not None
        else None,
        currency=price.currency,
        tariff_price=price,
    )


@dataclass(frozen=True)
class UsageSummary:
    metric: UsageMetric
    value: Decimal


@dataclass(frozen=True)
class InvoiceItem:
    code: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class OverageItem:
    metric: UsageMetric
    limit: Decimal
    value: Decimal
    overage: Decimal


def calculate_monthly_usage(
    db: Session,
    *,
    client_id: str,
    period_start: datetime,
    period_end: datetime,
) -> dict[UsageMetric, Decimal]:
    counters = (
        db.query(UsageCounter)
        .filter(UsageCounter.client_id == client_id)
        .filter(UsageCounter.period_start >= period_start)
        .filter(UsageCounter.period_end <= period_end)
        .all()
    )
    usage: dict[UsageMetric, Decimal] = {}
    for counter in counters:
        metric = counter.metric
        current = usage.get(metric, Decimal("0"))
        usage[metric] = current + _to_decimal(counter.value)
    return usage


def apply_overages(
    plan: CommercialPlan,
    *,
    plan_features: list[PlanFeature],
    usage: dict[UsageMetric, Decimal],
) -> list[OverageItem]:
    limits: dict[UsageMetric, Decimal] = {}
    key_map = {
        UsageMetric.CARDS_ACTIVE: "cards",
        UsageMetric.TRANSACTIONS: "transactions",
        UsageMetric.ALERTS_SENT: "alerts",
        UsageMetric.EXPORTS: "exports",
    }

    for feature in plan_features:
        if not feature.limits:
            continue
        for metric, limit_key in key_map.items():
            if limit_key in feature.limits:
                limits[metric] = _to_decimal(feature.limits[limit_key])

    overages: list[OverageItem] = []
    for metric, value in usage.items():
        limit_value = limits.get(metric)
        if limit_value is not None and value > limit_value:
            overages.append(
                OverageItem(
                    metric=metric,
                    limit=limit_value,
                    value=value,
                    overage=value - limit_value,
                )
            )
    return overages


def calculate_invoice_items(
    *,
    subscription: object,
    usage: dict[UsageMetric, Decimal],
    plan: CommercialPlan,
    plan_features: list[PlanFeature],
) -> list[InvoiceItem]:
    items: list[InvoiceItem] = []

    base_price = _to_decimal(plan.base_price_monthly)
    items.append(
        InvoiceItem(
            code="base_fee",
            description=f"{plan.name} subscription",
            quantity=Decimal("1"),
            unit_price=base_price,
            amount=base_price,
            currency=plan.currency,
        )
    )

    pricing_map = {
        UsageMetric.CARDS_ACTIVE: "cards_unit_price",
        UsageMetric.TRANSACTIONS: "transactions_unit_price",
        UsageMetric.ALERTS_SENT: "alerts_unit_price",
        UsageMetric.EXPORTS: "exports_unit_price",
    }

    unit_prices: dict[UsageMetric, Decimal] = {}
    for feature in plan_features:
        if not feature.limits:
            continue
        for metric, key in pricing_map.items():
            if key in feature.limits:
                unit_prices[metric] = _to_decimal(feature.limits[key])

    for metric, value in usage.items():
        unit_price = unit_prices.get(metric, Decimal("0"))
        if value and unit_price:
            items.append(
                InvoiceItem(
                    code=f"usage_{metric.value}",
                    description=f"Usage {metric.value}",
                    quantity=value,
                    unit_price=unit_price,
                    amount=value * unit_price,
                    currency=plan.currency,
                )
            )

    return items
