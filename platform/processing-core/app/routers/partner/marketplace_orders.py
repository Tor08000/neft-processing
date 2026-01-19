from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_orders import MarketplaceOrderActorType, MarketplaceOrderStatus
from app.schemas.marketplace.orders import (
    OrderAcceptRequest,
    OrderCompleteRequest,
    OrderDetailOut,
    OrderEventOut,
    OrderFailRequest,
    OrderOut,
    OrderProgressUpdateRequest,
    OrderRejectRequest,
    OrderStartRequest,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_order_service import MarketplaceOrderService, MarketplaceOrderServiceError

router = APIRouter(prefix="/partner/orders", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


def _order_out(order) -> OrderOut:
    return OrderOut(
        id=str(order.id),
        client_id=str(order.client_id),
        partner_id=str(order.partner_id),
        product_id=str(order.product_id),
        quantity=order.quantity,
        price_snapshot=order.price_snapshot,
        status=order.status.value if hasattr(order.status, "value") else order.status,
        payment_flow=order.payment_flow,
        settlement_breakdown=order.settlement_breakdown_json,
        created_at=order.created_at,
        updated_at=order.updated_at,
        audit_event_id=str(order.audit_event_id) if order.audit_event_id else None,
        external_ref=order.external_ref,
    )


def _event_out(event) -> OrderEventOut:
    return OrderEventOut(
        id=str(event.id),
        order_id=str(event.order_id),
        event_type=event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
        occurred_at=event.occurred_at,
        payload_redacted=event.payload_redacted,
        actor_type=event.actor_type.value if hasattr(event.actor_type, "value") else event.actor_type,
        actor_id=str(event.actor_id) if event.actor_id else None,
        audit_event_id=str(event.audit_event_id),
        created_at=event.created_at,
    )


def _handle_service_error(exc: MarketplaceOrderServiceError) -> None:
    if exc.code == "forbidden":
        raise HTTPException(status_code=403, detail="forbidden") from exc
    if exc.code == "order_not_found":
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if exc.code == "invalid_transition":
        raise HTTPException(
            status_code=409,
            detail={"error": "invalid_transition", "reason": exc.detail.get("event"), "from": exc.detail.get("from")},
        ) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("", response_model=list[OrderOut])
def list_partner_orders(
    request: Request,
    status: MarketplaceOrderStatus | None = Query(None),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> list[OrderOut]:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    items, _ = service.list_orders_for_partner(
        partner_id=partner_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [_order_out(item) for item in items]


@router.get("/{order_id}", response_model=OrderDetailOut)
def get_partner_order(
    order_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> OrderDetailOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.get_order_for_partner(order_id=order_id, partner_id=partner_id)
        events = service.list_order_events(order_id=order_id)
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    return OrderDetailOut(**_order_out(order).dict(), events=[_event_out(event) for event in events])


@router.post("/{order_id}/accept", response_model=OrderOut)
def accept_order(
    order_id: str,
    payload: OrderAcceptRequest,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> OrderOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.accept_order(
            partner_id=partner_id,
            order_id=order_id,
            note=payload.note,
            actor=MarketplaceOrderActorType.PARTNER,
        )
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)


@router.post("/{order_id}/reject", response_model=OrderOut)
def reject_order(
    order_id: str,
    payload: OrderRejectRequest,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> OrderOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.reject_order(
            partner_id=partner_id,
            order_id=order_id,
            reason=payload.reason,
            actor=MarketplaceOrderActorType.PARTNER,
        )
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)


@router.post("/{order_id}/start", response_model=OrderOut)
def start_order(
    order_id: str,
    payload: OrderStartRequest,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> OrderOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.start_order(
            partner_id=partner_id,
            order_id=order_id,
            note=payload.note,
            actor=MarketplaceOrderActorType.PARTNER,
        )
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)


@router.post("/{order_id}/progress", response_model=OrderOut)
def update_progress(
    order_id: str,
    payload: OrderProgressUpdateRequest,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> OrderOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.update_order_progress(
            partner_id=partner_id,
            order_id=order_id,
            progress_percent=payload.progress_percent,
            message=payload.message,
            actor=MarketplaceOrderActorType.PARTNER,
        )
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)


@router.post("/{order_id}/complete", response_model=OrderOut)
def complete_order(
    order_id: str,
    payload: OrderCompleteRequest,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> OrderOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.complete_order(
            partner_id=partner_id,
            order_id=order_id,
            summary=payload.summary,
            actor=MarketplaceOrderActorType.PARTNER,
        )
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)


@router.post("/{order_id}/fail", response_model=OrderOut)
def fail_order(
    order_id: str,
    payload: OrderFailRequest,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> OrderOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.fail_order(
            partner_id=partner_id,
            order_id=order_id,
            reason=payload.reason,
            actor=MarketplaceOrderActorType.PARTNER,
        )
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)
