from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.platform_revenue import PlatformRevenueEntry
from app.services.audit_service import AuditService, RequestContext


class PlatformRevenueService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    def record_fee(
        self,
        *,
        order_id: str,
        partner_id: str,
        amount: Decimal,
        currency: str,
        fee_basis: str,
        meta_json: dict | None = None,
        settlement_snapshot_id: str | None = None,
        settlement_id: str | None = None,
    ) -> PlatformRevenueEntry:
        existing = (
            self.db.query(PlatformRevenueEntry)
            .filter(PlatformRevenueEntry.order_id == order_id)
            .one_or_none()
        )
        if existing:
            return existing
        entry = PlatformRevenueEntry(
            order_id=order_id,
            partner_id=partner_id,
            amount=amount,
            currency=currency,
            fee_basis=fee_basis,
            meta_json={
                **(meta_json or {}),
                "settlement_snapshot_id": settlement_snapshot_id,
                "settlement_id": settlement_id,
            },
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        AuditService(self.db).audit(
            event_type="platform_revenue_recorded",
            entity_type="platform_revenue_entry",
            entity_id=str(entry.id),
            action="platform_revenue_recorded",
            after={
                "order_id": order_id,
                "partner_id": partner_id,
                "amount": str(amount),
                "currency": currency,
                "fee_basis": fee_basis,
            },
            request_ctx=self.request_ctx,
        )
        return entry


__all__ = ["PlatformRevenueService"]
