from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.cases import Case, CaseEventType, CaseKind, CasePriority
from app.models.marketplace_offers import MarketplaceOffer, MarketplaceOfferStatus, MarketplaceOfferSubjectType
from app.models.marketplace_orders import (
    MarketplaceOrder,
    MarketplaceOrderActorType,
    MarketplaceOrderEvent,
    MarketplaceOrderEventType,
    MarketplaceOrderLine,
    MarketplaceOrderLineSubjectType,
    MarketplaceOrderPaymentMethod,
    MarketplaceOrderPaymentStatus,
    MarketplaceOrderProof,
    MarketplaceOrderProofKind,
    MarketplaceOrderStatus,
)
from app.services.audit_service import RequestContext
from app.services.case_event_redaction import redact_deep
from app.services.case_events_service import CaseEventActor, emit_case_event


class MarketplaceOrdersServiceError(ValueError):
    def __init__(self, code: str, *, detail: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


@dataclass(frozen=True)
class OrderTransition:
    event_type: MarketplaceOrderEventType
    from_statuses: set[MarketplaceOrderStatus]
    to_status: MarketplaceOrderStatus


ORDER_TRANSITIONS = {
    MarketplaceOrderEventType.PAYMENT_PENDING: OrderTransition(
        event_type=MarketplaceOrderEventType.PAYMENT_PENDING,
        from_statuses={MarketplaceOrderStatus.CREATED},
        to_status=MarketplaceOrderStatus.PENDING_PAYMENT,
    ),
    MarketplaceOrderEventType.PAYMENT_PAID: OrderTransition(
        event_type=MarketplaceOrderEventType.PAYMENT_PAID,
        from_statuses={MarketplaceOrderStatus.CREATED, MarketplaceOrderStatus.PENDING_PAYMENT},
        to_status=MarketplaceOrderStatus.PAID,
    ),
    MarketplaceOrderEventType.PAYMENT_FAILED: OrderTransition(
        event_type=MarketplaceOrderEventType.PAYMENT_FAILED,
        from_statuses={MarketplaceOrderStatus.PENDING_PAYMENT, MarketplaceOrderStatus.CREATED},
        to_status=MarketplaceOrderStatus.PAYMENT_FAILED,
    ),
    MarketplaceOrderEventType.CONFIRMED: OrderTransition(
        event_type=MarketplaceOrderEventType.CONFIRMED,
        from_statuses={MarketplaceOrderStatus.PAID},
        to_status=MarketplaceOrderStatus.CONFIRMED_BY_PARTNER,
    ),
    MarketplaceOrderEventType.DECLINED: OrderTransition(
        event_type=MarketplaceOrderEventType.DECLINED,
        from_statuses={MarketplaceOrderStatus.PAID},
        to_status=MarketplaceOrderStatus.DECLINED_BY_PARTNER,
    ),
    MarketplaceOrderEventType.COMPLETED: OrderTransition(
        event_type=MarketplaceOrderEventType.COMPLETED,
        from_statuses={MarketplaceOrderStatus.CONFIRMED_BY_PARTNER},
        to_status=MarketplaceOrderStatus.COMPLETED,
    ),
    MarketplaceOrderEventType.CANCELED: OrderTransition(
        event_type=MarketplaceOrderEventType.CANCELED,
        from_statuses={MarketplaceOrderStatus.CREATED, MarketplaceOrderStatus.PENDING_PAYMENT},
        to_status=MarketplaceOrderStatus.CANCELED_BY_CLIENT,
    ),
}


EVENT_CASE_EVENT_MAP = {
    MarketplaceOrderEventType.CREATED: CaseEventType.MARKETPLACE_ORDER_CREATED,
    MarketplaceOrderEventType.PAYMENT_PENDING: CaseEventType.MARKETPLACE_ORDER_PAYMENT_PENDING,
    MarketplaceOrderEventType.PAYMENT_PAID: CaseEventType.MARKETPLACE_ORDER_PAYMENT_PAID,
    MarketplaceOrderEventType.PAYMENT_FAILED: CaseEventType.MARKETPLACE_ORDER_FAILED,
    MarketplaceOrderEventType.CONFIRMED: CaseEventType.MARKETPLACE_ORDER_CONFIRMED,
    MarketplaceOrderEventType.DECLINED: CaseEventType.MARKETPLACE_ORDER_DECLINED,
    MarketplaceOrderEventType.COMPLETED: CaseEventType.MARKETPLACE_ORDER_COMPLETED,
    MarketplaceOrderEventType.CANCELED: CaseEventType.MARKETPLACE_ORDER_CANCELLED,
}


class MarketplaceOrdersService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _to_decimal(value: object) -> Decimal:
        return Decimal(str(value))

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
        before_status: MarketplaceOrderStatus | None = None,
        after_status: MarketplaceOrderStatus | None = None,
        reason_code: str | None = None,
        comment: str | None = None,
    ) -> MarketplaceOrderEvent:
        case_event_type = EVENT_CASE_EVENT_MAP.get(event_type, CaseEventType.MARKETPLACE_ORDER_CREATED)
        case = self._ensure_order_case(order=order)
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
            occurred_at=self._now(),
            payload_redacted=redact_deep(payload, "", include_hash=True),
            actor_type=actor_type,
            actor_id=actor_id,
            audit_event_id=case_event.id,
            before_status=before_status.value if before_status else None,
            after_status=after_status.value if after_status else None,
            reason_code=reason_code,
            comment=comment,
            meta=payload,
        )
        self.db.add(order_event)
        return order_event

    def _apply_transition(
        self, order: MarketplaceOrder, *, event_type: MarketplaceOrderEventType
    ) -> MarketplaceOrderStatus:
        transition = ORDER_TRANSITIONS.get(event_type)
        if not transition:
            raise MarketplaceOrdersServiceError("invalid_transition", detail={"event": event_type.value})
        current_status = MarketplaceOrderStatus(order.status)
        if current_status not in transition.from_statuses:
            raise MarketplaceOrdersServiceError(
                "invalid_transition",
                detail={"from": current_status.value, "event": event_type.value},
            )
        order.status = transition.to_status.value
        order.updated_at = self._now()
        return transition.to_status

    def _resolve_order(self, *, order_id: str) -> MarketplaceOrder:
        order = self.db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).one_or_none()
        if not order:
            raise MarketplaceOrdersServiceError("order_not_found")
        return order

    def _resolve_offer(self, *, offer_id: str) -> MarketplaceOffer:
        offer = self.db.query(MarketplaceOffer).filter(MarketplaceOffer.id == offer_id).one_or_none()
        if not offer:
            raise MarketplaceOrdersServiceError("offer_not_found")
        if offer.status != MarketplaceOfferStatus.ACTIVE:
            raise MarketplaceOrdersServiceError("offer_not_active")
        return offer

    def create_order(
        self,
        client_id: str,
        *,
        items: list[dict],
        payment_method: MarketplaceOrderPaymentMethod,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        if not items:
            raise MarketplaceOrdersServiceError("items_required")
        offers: list[MarketplaceOffer] = []
        for item in items:
            offers.append(self._resolve_offer(offer_id=item["offer_id"]))
        partner_ids = {str(offer.partner_id) for offer in offers}
        if len(partner_ids) != 1:
            raise MarketplaceOrdersServiceError("partner_mismatch")
        currencies = {offer.currency for offer in offers}
        if len(currencies) != 1:
            raise MarketplaceOrdersServiceError("currency_mismatch")

        partner_id = partner_ids.pop()
        currency = currencies.pop()
        order = MarketplaceOrder(
            id=new_uuid_str(),
            client_id=client_id,
            partner_id=partner_id,
            status=MarketplaceOrderStatus.CREATED.value,
            payment_status=MarketplaceOrderPaymentStatus.UNPAID.value,
            payment_method=payment_method.value,
            currency=currency,
        )
        self.db.add(order)
        self.db.flush()

        subtotal = Decimal("0")
        for offer, item in zip(offers, items):
            qty = self._to_decimal(item.get("qty") or 1)
            if qty <= 0:
                raise MarketplaceOrdersServiceError("invalid_qty")
            if offer.subject_type == MarketplaceOfferSubjectType.SERVICE and qty != 1:
                raise MarketplaceOrdersServiceError("invalid_qty")
            unit_price = offer.price_amount or offer.price_min or offer.price_max or 0
            unit_price = self._to_decimal(unit_price)
            line_amount = unit_price * qty
            title_snapshot = offer.title_override or f"Offer {offer.id}"
            subject_type_value = (
                offer.subject_type.value if hasattr(offer.subject_type, "value") else offer.subject_type
            )
            line = MarketplaceOrderLine(
                id=new_uuid_str(),
                order_id=order.id,
                offer_id=str(offer.id),
                subject_type=MarketplaceOrderLineSubjectType(subject_type_value),
                subject_id=str(offer.subject_id),
                title_snapshot=title_snapshot,
                qty=qty,
                unit_price=unit_price,
                line_amount=line_amount,
            )
            self.db.add(line)
            subtotal += line_amount

        order.subtotal_amount = subtotal
        order.discount_amount = Decimal("0")
        order.total_amount = subtotal
        self.db.flush()

        event = self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.CREATED,
            payload={"order_id": str(order.id)},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
            before_status=None,
            after_status=MarketplaceOrderStatus.CREATED,
        )
        order.audit_event_id = event.audit_event_id

        self._apply_transition(order, event_type=MarketplaceOrderEventType.PAYMENT_PENDING)
        self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.PAYMENT_PENDING,
            payload={"order_id": str(order.id)},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
            before_status=MarketplaceOrderStatus.CREATED,
            after_status=MarketplaceOrderStatus.PENDING_PAYMENT,
        )
        return order

    def pay_order(
        self,
        client_id: str,
        *,
        order_id: str,
        payment_method: MarketplaceOrderPaymentMethod,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.client_id) != client_id:
            raise MarketplaceOrdersServiceError("forbidden")
        before_status = MarketplaceOrderStatus(order.status)
        self._apply_transition(order, event_type=MarketplaceOrderEventType.PAYMENT_PAID)
        order.payment_status = MarketplaceOrderPaymentStatus.PAID.value
        order.payment_method = payment_method.value
        self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.PAYMENT_PAID,
            payload={"order_id": str(order.id), "payment_method": payment_method.value},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
            before_status=before_status,
            after_status=MarketplaceOrderStatus.PAID,
        )
        return order

    def confirm_order(
        self,
        partner_id: str,
        *,
        order_id: str,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrdersServiceError("forbidden")
        if order.payment_status != MarketplaceOrderPaymentStatus.PAID.value:
            raise MarketplaceOrdersServiceError("payment_required")
        before_status = MarketplaceOrderStatus(order.status)
        self._apply_transition(order, event_type=MarketplaceOrderEventType.CONFIRMED)
        self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.CONFIRMED,
            payload={"order_id": str(order.id)},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
            before_status=before_status,
            after_status=MarketplaceOrderStatus.CONFIRMED_BY_PARTNER,
        )
        return order

    def decline_order(
        self,
        partner_id: str,
        *,
        order_id: str,
        reason_code: str,
        comment: str,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrdersServiceError("forbidden")
        if order.payment_status != MarketplaceOrderPaymentStatus.PAID.value:
            raise MarketplaceOrdersServiceError("payment_required")
        before_status = MarketplaceOrderStatus(order.status)
        self._apply_transition(order, event_type=MarketplaceOrderEventType.DECLINED)
        self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.DECLINED,
            payload={"order_id": str(order.id), "reason_code": reason_code, "comment": comment},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
            before_status=before_status,
            after_status=MarketplaceOrderStatus.DECLINED_BY_PARTNER,
            reason_code=reason_code,
            comment=comment,
        )
        return order

    def add_proof(
        self,
        partner_id: str,
        *,
        order_id: str,
        attachment_id: str,
        kind: MarketplaceOrderProofKind,
        note: str | None,
    ) -> MarketplaceOrderProof:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrdersServiceError("forbidden")
        proof = MarketplaceOrderProof(
            id=new_uuid_str(),
            order_id=order.id,
            kind=kind.value,
            attachment_id=attachment_id,
            note=note,
        )
        self.db.add(proof)
        self.db.flush()
        return proof

    def complete_order(
        self,
        partner_id: str,
        *,
        order_id: str,
        comment: str | None,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrdersServiceError("forbidden")
        proof_exists = (
            self.db.query(MarketplaceOrderProof)
            .filter(MarketplaceOrderProof.order_id == order_id)
            .count()
        )
        if not proof_exists:
            raise MarketplaceOrdersServiceError("proof_required")
        before_status = MarketplaceOrderStatus(order.status)
        self._apply_transition(order, event_type=MarketplaceOrderEventType.COMPLETED)
        self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.COMPLETED,
            payload={"order_id": str(order.id), "comment": comment},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
            before_status=before_status,
            after_status=MarketplaceOrderStatus.COMPLETED,
            comment=comment,
        )
        return order

    def cancel_order(
        self,
        client_id: str,
        *,
        order_id: str,
        reason: str | None,
        actor: MarketplaceOrderActorType,
    ) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.client_id) != client_id:
            raise MarketplaceOrdersServiceError("forbidden")
        before_status = MarketplaceOrderStatus(order.status)
        self._apply_transition(order, event_type=MarketplaceOrderEventType.CANCELED)
        self._emit_order_event(
            order=order,
            event_type=MarketplaceOrderEventType.CANCELED,
            payload={"order_id": str(order.id), "reason": reason},
            actor_type=actor,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
            before_status=before_status,
            after_status=MarketplaceOrderStatus.CANCELED_BY_CLIENT,
            reason_code=reason,
        )
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

    def list_order_lines(self, *, order_id: str) -> list[MarketplaceOrderLine]:
        return (
            self.db.query(MarketplaceOrderLine)
            .filter(MarketplaceOrderLine.order_id == order_id)
            .order_by(MarketplaceOrderLine.id.asc())
            .all()
        )

    def list_order_proofs(self, *, order_id: str) -> list[MarketplaceOrderProof]:
        return (
            self.db.query(MarketplaceOrderProof)
            .filter(MarketplaceOrderProof.order_id == order_id)
            .order_by(MarketplaceOrderProof.created_at.asc(), MarketplaceOrderProof.id.asc())
            .all()
        )

    def get_order_for_client(self, *, order_id: str, client_id: str) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.client_id) != client_id:
            raise MarketplaceOrdersServiceError("forbidden")
        return order

    def get_order_for_partner(self, *, order_id: str, partner_id: str) -> MarketplaceOrder:
        order = self._resolve_order(order_id=order_id)
        if str(order.partner_id) != partner_id:
            raise MarketplaceOrdersServiceError("forbidden")
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


__all__ = ["MarketplaceOrdersService", "MarketplaceOrdersServiceError"]
