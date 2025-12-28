from __future__ import annotations

from dataclasses import dataclass

from app.models.crm import CRMSubscriptionCharge, CRMUsageCounter


@dataclass(frozen=True)
class SubscriptionExplain:
    segments: list[dict]
    usage: list[dict]
    charges: list[dict]
    total: int


def build_explain(
    *,
    segments: list[dict],
    counters: list[CRMUsageCounter],
    charges: list[CRMSubscriptionCharge],
) -> SubscriptionExplain:
    usage_payload = [
        {
            "metric": counter.metric.value,
            "value": int(counter.value),
            "limit_value": int(counter.limit_value) if counter.limit_value is not None else None,
            "overage": int(counter.overage) if counter.overage is not None else None,
            "segment_id": str(counter.segment_id) if counter.segment_id else None,
        }
        for counter in counters
    ]
    charges_payload = [
        {
            "code": charge.code,
            "amount": int(charge.amount),
            "quantity": int(charge.quantity),
            "unit_price": int(charge.unit_price),
            "segment_id": str(charge.segment_id) if charge.segment_id else None,
            "explain": charge.explain,
        }
        for charge in charges
    ]
    total_amount = sum(int(charge.amount) for charge in charges)
    return SubscriptionExplain(
        segments=segments,
        usage=usage_payload,
        charges=charges_payload,
        total=total_amount,
    )


__all__ = ["SubscriptionExplain", "build_explain"]
