from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_orders import MarketplaceOrder
from app.models.marketplace_settlement import (
    MarketplaceAdjustment,
    MarketplaceAdjustmentType,
    MarketplaceSettlementItem,
    MarketplaceSettlementStatus,
)
from app.models.payout_batch import PayoutBatch, PayoutBatchState, PayoutItem
from app.services.audit_service import AuditService, RequestContext


@dataclass(frozen=True)
class PayoutBatchResult:
    batch: PayoutBatch
    items: list[PayoutItem]
    settlement_items: list[MarketplaceSettlementItem]


class MarketplaceSettlementService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    @staticmethod
    def _decimal(value: object | None) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def _period_for_date(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m")

    def _gross_amount(self, order: MarketplaceOrder) -> Decimal:
        snapshot = order.price_snapshot or {}
        return self._decimal(snapshot.get("total") or snapshot.get("subtotal") or order.final_price or order.price)

    def create_settlement_item_for_order(self, *, order: MarketplaceOrder) -> MarketplaceSettlementItem:
        if not order.completed_at:
            raise ValueError("order_not_completed")
        period = self._period_for_date(order.completed_at)
        existing = (
            self.db.query(MarketplaceSettlementItem)
            .filter(MarketplaceSettlementItem.order_id == order.id)
            .one_or_none()
        )
        if existing:
            return existing
        gross = self._gross_amount(order)
        commission = self._decimal(order.commission or 0)
        net = gross - commission
        item = MarketplaceSettlementItem(
            id=new_uuid_str(),
            order_id=order.id,
            period=period,
            gross_amount=gross,
            commission_amount=commission,
            net_partner_amount=net,
            penalty_amount=Decimal("0"),
            adjustments_amount=Decimal("0"),
            status=MarketplaceSettlementStatus.OPEN.value,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(item)
        AuditService(self.db).audit(
            event_type="MARKETPLACE_SETTLEMENT_ITEM_CREATED",
            entity_type="marketplace_settlement_item",
            entity_id=str(item.id),
            action="MARKETPLACE_SETTLEMENT_ITEM_CREATED",
            after={
                "order_id": str(order.id),
                "period": period,
                "gross_amount": str(gross),
                "commission_amount": str(commission),
                "net_partner_amount": str(net),
            },
            request_ctx=self.request_ctx,
        )
        return item

    def apply_adjustment(
        self,
        *,
        partner_id: str,
        order_id: str | None,
        period: str,
        adjustment_type: MarketplaceAdjustmentType,
        amount: Decimal,
        reason_code: str | None = None,
        meta: dict | None = None,
    ) -> MarketplaceAdjustment:
        adjustment = MarketplaceAdjustment(
            id=new_uuid_str(),
            partner_id=partner_id,
            order_id=order_id,
            period=period,
            type=adjustment_type.value if hasattr(adjustment_type, "value") else str(adjustment_type),
            amount=amount,
            reason_code=reason_code,
            meta=meta,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(adjustment)
        AuditService(self.db).audit(
            event_type="MARKETPLACE_ADJUSTMENT_CREATED",
            entity_type="marketplace_adjustment",
            entity_id=str(adjustment.id),
            action="MARKETPLACE_ADJUSTMENT_CREATED",
            after={
                "partner_id": partner_id,
                "order_id": order_id,
                "period": period,
                "type": adjustment.type,
                "amount": str(amount),
                "reason_code": reason_code,
            },
            request_ctx=self.request_ctx,
        )
        return adjustment

    def update_penalty_for_order(self, *, order_id: str, penalty_amount: Decimal) -> MarketplaceSettlementItem | None:
        item = (
            self.db.query(MarketplaceSettlementItem)
            .filter(MarketplaceSettlementItem.order_id == order_id)
            .one_or_none()
        )
        if not item:
            return None
        item.penalty_amount = self._decimal(item.penalty_amount) + penalty_amount
        item.adjustments_amount = self._decimal(item.adjustments_amount) + penalty_amount
        return item

    def build_payout_batch(
        self,
        *,
        tenant_id: int,
        partner_id: str,
        period: str,
    ) -> PayoutBatchResult:
        date_from = date.fromisoformat(f"{period}-01")
        if date_from.month == 12:
            date_to = date(date_from.year + 1, 1, 1)
        else:
            date_to = date(date_from.year, date_from.month + 1, 1)
        date_to = date_to - timedelta(days=1)
        settlement_items = (
            self.db.query(MarketplaceSettlementItem)
            .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceSettlementItem.order_id)
            .filter(
                MarketplaceSettlementItem.period == period,
                MarketplaceSettlementItem.status == MarketplaceSettlementStatus.OPEN,
                MarketplaceOrder.partner_id == partner_id,
            )
            .all()
        )
        if not settlement_items:
            raise ValueError("no_open_settlement_items")
        gross_total = sum((self._decimal(item.gross_amount) for item in settlement_items), Decimal("0"))
        commission_total = sum((self._decimal(item.commission_amount) for item in settlement_items), Decimal("0"))
        net_total = sum((self._decimal(item.net_partner_amount) for item in settlement_items), Decimal("0"))

        adjustment_total = (
            self.db.query(func.coalesce(func.sum(MarketplaceAdjustment.amount), 0))
            .filter(
                MarketplaceAdjustment.partner_id == partner_id,
                MarketplaceAdjustment.period == period,
            )
            .scalar()
        )
        adjustment_total = self._decimal(adjustment_total)
        payout_amount = net_total - adjustment_total

        batch = PayoutBatch(
            id=new_uuid_str(),
            tenant_id=tenant_id,
            partner_id=partner_id,
            date_from=date_from,
            date_to=date_to,
            state=PayoutBatchState.READY.value,
            total_amount=payout_amount,
            total_qty=Decimal("0"),
            operations_count=len(settlement_items),
            created_at=datetime.now(timezone.utc),
            meta={"marketplace_period": period, "adjustments_total": str(adjustment_total)},
        )
        self.db.add(batch)
        payout_item = PayoutItem(
            id=new_uuid_str(),
            batch_id=batch.id,
            amount_gross=gross_total,
            commission_amount=commission_total,
            amount_net=payout_amount,
            qty=Decimal("0"),
            operations_count=len(settlement_items),
            meta={"marketplace_period": period, "adjustments_total": str(adjustment_total)},
        )
        self.db.add(payout_item)
        for item in settlement_items:
            item.status = MarketplaceSettlementStatus.INCLUDED_IN_PAYOUT.value
        AuditService(self.db).audit(
            event_type="MARKETPLACE_PAYOUT_BATCH_BUILT",
            entity_type="payout_batch",
            entity_id=str(batch.id),
            action="MARKETPLACE_PAYOUT_BATCH_BUILT",
            after={
                "partner_id": partner_id,
                "period": period,
                "gross_total": str(gross_total),
                "commission_total": str(commission_total),
                "adjustments_total": str(adjustment_total),
                "payout_amount": str(payout_amount),
            },
            request_ctx=self.request_ctx,
        )
        return PayoutBatchResult(batch=batch, items=[payout_item], settlement_items=settlement_items)

    def mark_batch_settled(self, *, batch: PayoutBatch) -> None:
        batch.state = PayoutBatchState.SETTLED.value
        batch.settled_at = datetime.now(timezone.utc)
        settlement_items = (
            self.db.query(MarketplaceSettlementItem)
            .filter(MarketplaceSettlementItem.status == MarketplaceSettlementStatus.INCLUDED_IN_PAYOUT)
            .all()
        )
        for item in settlement_items:
            item.status = MarketplaceSettlementStatus.SETTLED.value


__all__ = ["MarketplaceSettlementService", "PayoutBatchResult"]
