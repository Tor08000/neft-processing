from __future__ import annotations

from app.models.audit_log import AuditVisibility
from app.services.audit_service import AuditService, RequestContext


FUEL_EVENT_AUTHORIZED = "FUEL_TX_AUTHORIZED"
FUEL_EVENT_DECLINED = "FUEL_TX_DECLINED"
FUEL_EVENT_REVIEW = "FUEL_TX_REVIEW_REQUIRED"
FUEL_EVENT_REVIEW_APPROVED = "FUEL_TX_REVIEW_APPROVED"
FUEL_EVENT_REVIEW_REJECTED = "FUEL_TX_REVIEW_REJECTED"
FUEL_EVENT_SETTLED = "FUEL_TX_SETTLED"
FUEL_EVENT_REVERSED = "FUEL_TX_REVERSED"


def audit_event(
    db,
    *,
    event_type: str,
    entity_id: str,
    payload: dict,
    request_ctx: RequestContext | None,
) -> None:
    AuditService(db).audit(
        event_type=event_type,
        entity_type="fuel_transaction",
        entity_id=entity_id,
        action=event_type,
        visibility=AuditVisibility.INTERNAL,
        after=payload,
        request_ctx=request_ctx,
    )


__all__ = [
    "FUEL_EVENT_AUTHORIZED",
    "FUEL_EVENT_DECLINED",
    "FUEL_EVENT_REVIEW",
    "FUEL_EVENT_REVIEW_APPROVED",
    "FUEL_EVENT_REVIEW_REJECTED",
    "FUEL_EVENT_SETTLED",
    "FUEL_EVENT_REVERSED",
    "audit_event",
]
