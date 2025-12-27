from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.logistics import LogisticsOrder, LogisticsTrackingEvent


@dataclass(frozen=True)
class LogisticsRiskContext:
    order_id: str
    client_id: str
    vehicle_id: str | None
    driver_id: str | None
    status: str
    last_event_type: str | None
    last_event_ts: datetime | None


def build_risk_context(
    *,
    order: LogisticsOrder,
    last_event: LogisticsTrackingEvent | None = None,
) -> LogisticsRiskContext:
    return LogisticsRiskContext(
        order_id=str(order.id),
        client_id=order.client_id,
        vehicle_id=str(order.vehicle_id) if order.vehicle_id else None,
        driver_id=str(order.driver_id) if order.driver_id else None,
        status=order.status.value,
        last_event_type=last_event.event_type.value if last_event else None,
        last_event_ts=last_event.ts if last_event else None,
    )


__all__ = ["LogisticsRiskContext", "build_risk_context"]
