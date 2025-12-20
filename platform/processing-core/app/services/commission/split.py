from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from app.config import settings
from app.models.operation import Operation, OperationStatus, OperationType

DEFAULT_RATE_SOURCE = "DEFAULT"
DEFAULT_PROMO_FUNDING_SOURCE = "NONE"


def _resolve_gross_amount(operation: Operation) -> int:
    """Determine the gross amount to use for commission calculation."""

    for candidate in (operation.amount_settled, operation.captured_amount, operation.amount_original):
        if candidate and candidate != 0:
            amount = int(candidate)
            break
    else:
        amount = 0

    negative = operation.status in {
        OperationStatus.REFUNDED,
        OperationStatus.REVERSED,
    } or operation.operation_type in {OperationType.REFUND, OperationType.REVERSE}

    return -amount if negative else amount


def compute_posting_result(operation: Operation, commission_rate: float | None = None) -> dict:
    """Compute immutable commission split snapshot for an operation."""

    rate = Decimal(str(commission_rate if commission_rate is not None else settings.NEFT_COMMISSION_RATE))
    gross_amount = _resolve_gross_amount(operation)

    partner_fee = Decimal("0")
    promo_discount = Decimal("0")
    adjusted_amount = Decimal(gross_amount) - partner_fee + promo_discount
    base_cost = (adjusted_amount / (Decimal("1") + rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    platform_commission = (base_cost * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    return {
        "currency": operation.currency,
        "gross_amount": int(gross_amount),
        "base_cost": int(base_cost),
        "platform_commission": int(platform_commission),
        "partner_fee": int(partner_fee),
        "promo_discount": int(promo_discount),
        "promo_funding_source": DEFAULT_PROMO_FUNDING_SOURCE,
        "commission_rate": float(rate),
        "rate_source": DEFAULT_RATE_SOURCE,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
