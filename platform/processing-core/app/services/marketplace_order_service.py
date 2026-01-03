from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.cases import Case, CaseEventType, CaseKind, CasePriority
from app.models.marketplace_catalog import MarketplaceProduct, MarketplaceProductStatus
from app.models.marketplace_orders import (
    MarketplaceOrder,
    MarketplaceOrderActorType,
    MarketplaceOrderEvent,
    MarketplaceOrderEventType,
    MarketplaceOrderStatus,
)
from app.services.audit_service import RequestContext
from app.services.case_event_redaction import redact_deep
from app.services.case_events_service import CaseEventActor, emit_case_event
from app.services.decision_memory.records import record_decision_memory


class MarketplaceOrderServiceError(ValueError):
    def __init__(self, code: str, *, detail: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


@dataclass(frozen=True)
class OrderTransition:
    event_type: MarketplaceOrderEventType
    from_statuses: set[MarketplaceOrderStatus]
    to_status: MarketplaceOrderStatus | None


ORDER_TRANSITIONS = {
    MarketplaceOrderEventType.ORDER_ACCEPTED: OrderTransition(
        event_type=MarketplaceOrderEventType.ORDER_ACCEPTED,
        from_statuses={MarketplaceOrderStatus.CREATED},
        to_status=MarketplaceOrderStatus.ACCEPTED,
    ),
    MarketplaceOrderEventType.ORDER_REJECTED: OrderTransition(
        event_type=MarketplaceOrderEventType.ORDER_REJECTED,
        from_statuses={MarketplaceOrderStatus.CREATED},
        to_status=MarketplaceOrderStatus.REJECTED,
    ),
    MarketplaceOrderEventType.ORDER_STARTED: OrderTransition(
        event_type=MarketplaceOrderEventType.ORDER_STARTED,
        from_statuses={MarketplaceOrderStatus.ACCEPTED},
        to_status=MarketplaceOrderStatus.IN_PROGRESS,
    ),
    MarketplaceOrderEventType.ORDER_COMPLETED: OrderTransition(
        event_type=MarketplaceOrderEventType.ORDER_COMPLETED,
        from_statuses={MarketplaceOrderStatus.IN_PROGRESS},
        to_status=MarketplaceOrderStatus.COMPLETED,
    ),
    MarketplaceOrderEventType.ORDER_FAILED: OrderTransition(
        event_type=MarketplaceOrderEventType.ORDER_FAILED,
        from_statuses={MarketplaceOrderStatus.ACCEPTED, MarketplaceOrderStatus.IN_PROGRESS},
        to_status=MarketplaceOrderStatus.FAILED,
    ),
    MarketplaceOrderEventType.ORDER_CANCELLED: OrderTransition(
        event_type=MarketplaceOrderEventType.ORDER_CANCELLED,
        from_statuses={MarketplaceOrderStatus.CREATED},
        to_status=MarketplaceOrderStatus.CANCELLED,
    ),
}


EVENT_CASE_EVENT_MAP = {
    MarketplaceOrderEventType.ORDER_CREATED: CaseEventType.MARKETPLACE_ORDER_CREATED,
    MarketplaceOrderEventType.ORDER_ACCEPTED: CaseEventType.MARKETPLACE_ORDER_ACCEPTED,
    MarketplaceOrderEventType.ORDER_REJECTED: CaseEventType.MARKETPLACE_ORDER_REJECTED,
    MarketplaceOrderEventType.ORDER_STARTED: CaseEventType.MARKETPLACE_ORDER_STARTED,
    MarketplaceOrderEventType.ORDER_PROGRESS_UPDATED: CaseEventType.MARKETPLACE_ORDER_PROGRESS_UPDATED,
    MarketplaceOrderEventType.ORDER_COMPLETED: CaseEventType.MARKETPLACE_ORDER_COMPLETED,
    MarketplaceOrderEventType.ORDER_FAILED: CaseEventType.MARKETPLACE_ORDER_FAILED,
    MarketplaceOrderEventType.ORDER_CANCELLED: CaseEventType.MARKETPLACE_ORDER_CANCELLED,
    MarketplaceOrderEventType.ORDER_NOTE_ADDED: CaseEventType.MARKETPLACE_ORDER_PROGRESS_UPDATED,
}


class MarketplaceOrderService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _to_decimal(value: object) -> Decimal:
        return Decimal(str(value))

    def _calculate_price(self, *, price_model: str, price_config: dict, quantity: Decimal) -> Decimal:
        if price_model == "FIXED":
            return self._to_decimal(price_config.get("amount", 0))
        if price_model == "PER_UNIT":
            return self._to_decimal(price_config.get("amount_per_unit", 0)) * quantity
        if price_model == "TIERED":
            tiers = price_config.get("tiers") or []
            if not tiers:
                return Decimal("0")
            selected = None
            for tier in tiers:
                tier_from = self._to_decimal(tier.get("from", 0))
                tier_to = tier.get("to")
                tier_to_value = self._to_decimal(tier_to) if tier_to is not None else None
                if quantity >= tier_from and (tier_to_value is None or quantity <= tier_to_value):
                    selected = tier
            if selected is None:
                selected = tiers[-1]
            return self._to_decimal(selected.get("amount", 0)) * quantity
        return Decimal("0")

    def _ensure_order_case(self, *, order: MarketplaceOrder) -> Case:
        existing = (
            self.db.query(Case)
            .filter(Case.kind == CaseKind.ORDER)
            .filter(Case.entity_id == str(order.id))
            .one_or_none()
        )
        if existing:
            return existing
        tenant_id = self.request_ctx.tenant_id if self.request_ctx and self.request_ctx.tenant_id is not None else 0
        case = Case(
            id=new_uuid_str(),
            tenant_id=tenant_id,
            kind=CaseKind.ORDER,
            entity_id=str(order.id),
            title=f"Marketplace order {order.id}",
            priority=CasePriority.MEDIUM,
            created_by=self.request_ctx.actor_id if self.request_ctx else None,
        )
        self.db.add(case)
        self.db.flush()
        return case

    def _case_actor(self) -> CaseEventActor | None:
        if not self.request_ctx:
            return None
        return CaseEventActor(id=self.request_ctx.actor_id, email=self.request_ctx.actor_email)

    def _emit_order_event(
        self,
        *,
        order: MarketplaceOrder,
        event_type: MarketplaceOrderEventType,
        payload: dict,
        actor_type: MarketplaceOrderActorType,
        actor_id: str | None,
        occurred_at: datetime | None = None,
    ) -> MarketplaceOrderEvent:
        case = self._ensure_order_case(order=order)
        case_event_type = EVENT_CASE_EVENT_MAP[event_type]
        case_event = emit_case_event(
            self.db,
            case_id=str(case.id),
            event_type=case_event_type,
            actor=self._case_actor(),
            request_id=self.request_ctx.request_id if self.request_ctx else None,
            trace_id=self.request_ctx.trace_id if self.request_ctx else None,
            extra_payload={
                "order_id": str(order.id),
                "event": event_type.value,
            },
        )
        order_event = MarketplaceOrderEvent(
            id=new_uuid_str(),
            order_id=order.id,
            event_type=event_type,
            occurred_at=occurred_at or self._now(),
            payload_redacted=redact_deep(payload, "", include_hash=True),
            actor_type=actor_type,
            actor_id=actor_id,
            audit_event_id=case_event.id,
        )
        self.db.add(order_event)
        return order_event

    def _ensure_transition(self, order: MarketplaceOrder, event_type: MarketplaceOrderEventType) -> MarketplaceOrderStatus | None:
        transition = ORDER_TRANSITIONS.get(event_type)
        if not transition:
            return None
        current_status = MarketplaceOrderStatus(order.status)
        if current_status not in transition.from_statuses:
            raise MarketplaceOrderServiceError(
                "invalid_transition",
                detail={"from": current_status.value, "event": event_type.value},
            )
        return transition.to_status

    def _apply_transition(self, order: MarketplaceOrder, *, event_type: MarketplaceOrderEventType) -> None:
        target_status = self._ensure_transition(order, event_type)
        if target_status is not None:
            order.status = target_status.value
            order.updated_at = self._now()

    def _record_decision(
        self,
        *,
        order: MarketplaceOrder,
        decision_type: str,
        rationale: str | None,
        audit_event_id: str,
    ) -> None:
        record_decision_memory(
            self.db,
            case_id=str(self._ensure_order_case(order=order).id),
            decision_type=decision_type,
            decision_ref_id=str(order.id),
            decision_at=self._now(),
            decided_by_user_id=self.request_ctx.actor_id if self.request_ctx else None,
            context_snapshot={"order_id": str(order.id), "status": order.status},
            rationale=rationale,
            score_snapshot=None,
            mastery_snapshot=None,
            audit_event_id=audit_event_id,
        )

    def _get_product(self, *, product_id: str) -> MarketplaceProduct:
        product = self.db.query(MarketplaceProduct).filter(MarketplaceProduct.id == product_id).one_or_none()
        if not product:
            raise MarketplaceOrderServiceError("product_not_found")
        if product.status != MarketplaceProductStatus.PUBLISHED:
            raise MarketplaceOrderServiceError("product_not_published")
        return product

    def _resolve_order(self, *, order_id: str) -> MarketplaceOrder:
        order = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).one_or_none()
        if not order:
            raise MarketplaceOrderServiceError("order_not_found")
        return order

    def create_order(
        self,
        client_id: str,
        *,
        product_id: str,
        quantity: Decimal,
        note: str | None = None,
        external_ref: str | None = None,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        if external_ref:
            existing = (
                self.db.query(MarketplaceOrder)
                .filter(MarketplaceOrder.client_id == client_id)
                .filter(MarketplaceOrder.external_ref == external_ref)
                .one_or_none()
            )
            if existing:
                return existing

        product = self._get_product(product_id=product_id)
        price_model = product.price_model.value if hasattr(product.price_model, "value") else product.price_model
        price_amount = self._calculate_price(
            price_model=price_model,
            price_config=product.price_config,
            quantity=quantity,
        )
        order = MarketplaceOrder(
            id=new_uuid_str(),
            client_id=client_id,
            partner_id=str(product.partner_id),
            product_id=str(product.id),
            quantity=quantity,
            price_snapshot={
                "price_model": price_model,
                "price_config": product.price_config,
            },
            price=price_amount,
            discount=Decimal("0"),
            final_price=price_amount,
            commission=Decimal("0"),
            status=MarketplaceOrderStatus.CREATED.value,
            external_ref=external_ref,
        )
        self.db.add(order)
        self.db.flush()

        event = self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.ORDER_CREATED,
            payload={"order_id": str(order.id), "note": note},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
        )
        order.audit_event_id = event.audit_event_id
        self.db.flush()
        return order

    def list_orders_for_client(
        self,
        *,
        client_id: str,
        status: MarketplaceOrderStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceOrder], int]:
        query = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.client_id == client_id)
        if status:
            query = query.filter(MarketplaceOrder.status == status)
        if date_from:
            query = query.filter(MarketplaceOrder.created_at >= date_from)
        if date_to:
            query = query.filter(MarketplaceOrder.created_at <= date_to)
        total = query.count()
        items = (
            query.order_by(MarketplaceOrder.created_at.desc(), MarketplaceOrder.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def list_orders_for_partner(
        self,
        *,
        partner_id: str,
        status: MarketplaceOrderStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceOrder], int]:
        query = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.partner_id == partner_id)
        if status:
            query = query.filter(MarketplaceOrder.status == status)
        if date_from:
            query = query.filter(MarketplaceOrder.created_at >= date_from)
        if date_to:
            query = query.filter(MarketplaceOrder.created_at <= date_to)
        total = query.count()
        items = (
            query.order_by(MarketplaceOrder.created_at.desc(), MarketplaceOrder.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def list_orders_admin(
        self,
        *,
        status: MarketplaceOrderStatus | None = None,
        client_id: str | None = None,
        partner_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceOrder], int]:
        query = self.db.query(MarketplaceOrder)
        if status:
            query = query.filter(MarketplaceOrder.status == status)
        if client_id:
            query = query.filter(MarketplaceOrder.client_id == client_id)
        if partner_id:
            query = query.filter(MarketplaceOrder.partner_id == partner_id)
        if date_from:
            query = query.filter(MarketplaceOrder.created_at >= date_from)
        if date_to:
            query = query.filter(MarketplaceOrder.created_at <= date_to)
        total = query.count()
        items = (
            query.order_by(MarketplaceOrder.created_at.desc(), MarketplaceOrder.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def list_order_events(self, *, order_id: str) -> list[MarketplaceOrderEvent]:
        return (
            self.db.query(MarketplaceOrderEvent)
            .filter(MarketplaceOrderEvent.order_id == order_id)
            .order_by(MarketplaceOrderEvent.occurred_at.asc(), MarketplaceOrderEvent.id.asc())
            .all()
        )

    def accept_order(
        self,
        partner_id: str,
        *,
        order_id: str,
        note: str | None,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrderServiceError("forbidden")
        self._apply_transition(order, event_type=MarketplaceOrderEventType.ORDER_ACCEPTED)
        event = self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.ORDER_ACCEPTED,
            payload={"order_id": str(order.id), "note": note},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
        )
        self._record_decision(
            order=order,
            decision_type="marketplace_order_accepted",
            rationale=note,
            audit_event_id=str(event.audit_event_id),
        )
        return order

    def reject_order(
        self,
        partner_id: str,
        *,
        order_id: str,
        reason: str,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrderServiceError("forbidden")
        self._apply_transition(order, event_type=MarketplaceOrderEventType.ORDER_REJECTED)
        event = self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.ORDER_REJECTED,
            payload={"order_id": str(order.id), "reason": reason},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
        )
        self._record_decision(
            order=order,
            decision_type="marketplace_order_rejected",
            rationale=reason,
            audit_event_id=str(event.audit_event_id),
        )
        return order

    def start_order(
        self,
        partner_id: str,
        *,
        order_id: str,
        note: str | None,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrderServiceError("forbidden")
        self._apply_transition(order, event_type=MarketplaceOrderEventType.ORDER_STARTED)
        self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.ORDER_STARTED,
            payload={"order_id": str(order.id), "note": note},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
        )
        return order

    def update_order_progress(
        self,
        partner_id: str,
        *,
        order_id: str,
        progress_percent: int | None,
        message: str | None,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrderServiceError("forbidden")
        current_status = MarketplaceOrderStatus(order.status)
        if current_status != MarketplaceOrderStatus.IN_PROGRESS:
            raise MarketplaceOrderServiceError(
                "invalid_transition",
                detail={"from": current_status.value, "event": MarketplaceOrderEventType.ORDER_PROGRESS_UPDATED.value},
            )
        order.updated_at = self._now()
        self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.ORDER_PROGRESS_UPDATED,
            payload={
                "order_id": str(order.id),
                "progress_percent": progress_percent,
                "message": message,
            },
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
        )
        return order

    def complete_order(
        self,
        partner_id: str,
        *,
        order_id: str,
        summary: str,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrderServiceError("forbidden")
        self._apply_transition(order, event_type=MarketplaceOrderEventType.ORDER_COMPLETED)
        order.completed_at = self._now()
        event = self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.ORDER_COMPLETED,
            payload={"order_id": str(order.id), "summary": summary},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
        )
        self._record_decision(
            order=order,
            decision_type="marketplace_order_completed",
            rationale=summary,
            audit_event_id=str(event.audit_event_id),
        )
        return order

    def fail_order(
        self,
        partner_id: str,
        *,
        order_id: str,
        reason: str,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrderServiceError("forbidden")
        self._apply_transition(order, event_type=MarketplaceOrderEventType.ORDER_FAILED)
        event = self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.ORDER_FAILED,
            payload={"order_id": str(order.id), "reason": reason},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
        )
        self._record_decision(
            order=order,
            decision_type="marketplace_order_failed",
            rationale=reason,
            audit_event_id=str(event.audit_event_id),
        )
        return order

    def cancel_order(
        self,
        client_id: str,
        *,
        order_id: str,
        reason: str,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.client_id) != client_id:
            raise MarketplaceOrderServiceError("forbidden")
        self._apply_transition(order, event_type=MarketplaceOrderEventType.ORDER_CANCELLED)
        event = self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.ORDER_CANCELLED,
            payload={"order_id": str(order.id), "reason": reason},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
        )
        self._record_decision(
            order=order,
            decision_type="marketplace_order_cancelled",
            rationale=reason,
            audit_event_id=str(event.audit_event_id),
        )
        return order

    def get_order(self, *, order_id: str) -> MarketplaceOrder | None:
        return self.db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).one_or_none()

    def get_order_for_client(self, *, order_id: str, client_id: str) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.client_id) != client_id:
            raise MarketplaceOrderServiceError("forbidden")
        return order

    def get_order_for_partner(self, *, order_id: str, partner_id: str) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrderServiceError("forbidden")
        return order

    def get_order_for_admin(self, *, order_id: str) -> MarketplaceOrder:
        return self._resolve_order(order_id=order_id)

    def require_order(self, *, order_id: str, client_id: str, partner_id: str) -> MarketplaceOrder | None:
        return (
            self.db.query(MarketplaceOrder)
            .filter(
                and_(
                    MarketplaceOrder.id == order_id,
                    MarketplaceOrder.client_id == client_id,
                    MarketplaceOrder.partner_id == partner_id,
                )
            )
            .one_or_none()
        )


__all__ = ["MarketplaceOrderService", "MarketplaceOrderServiceError"]
