from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_orders import MarketplaceOrderActorType, MarketplaceOrderStatus
from app.schemas.marketplace.orders import (
    OrderCancelRequest,
    OrderCreateRequest,
    OrderDetailOut,
    OrderEventOut,
    OrderOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_order_service import MarketplaceOrderService, MarketplaceOrderServiceError

router = APIRouter(prefix="/client/marketplace/orders", tags=["client-portal-v1"])


def _ensure_client_context(principal: Principal) -> str:
    if principal.client_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "client"},
        )
    return str(principal.client_id)


def _order_out(order) -> OrderOut:
    return OrderOut(
        id=str(order.id),
        client_id=str(order.client_id),
        partner_id=str(order.partner_id),
        product_id=str(order.product_id),
        quantity=order.quantity,
        price_snapshot=order.price_snapshot,
        status=order.status.value if hasattr(order.status, "value") else order.status,
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
    if exc.code in {"order_not_found", "product_not_found"}:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if exc.code in {"product_not_published"}:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    if exc.code == "invalid_transition":
        raise HTTPException(
            status_code=409,
            detail={"error": "invalid_transition", "reason": exc.detail.get("event"), "from": exc.detail.get("from")},
        ) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("", response_model=list[OrderOut])
def list_client_orders(
    request: Request,
    status: MarketplaceOrderStatus | None = Query(None),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("client:marketplace:orders:list")),
    db: Session = Depends(get_db),
) -> list[OrderOut]:
    client_id = _ensure_client_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    items, _ = service.list_orders_for_client(
        client_id=client_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [_order_out(item) for item in items]


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_client_order(
    payload: OrderCreateRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:marketplace:orders:create")),
    db: Session = Depends(get_db),
) -> OrderOut:
    client_id = _ensure_client_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.create_order(
            client_id=client_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
            note=payload.note,
            external_ref=payload.external_ref,
            promotion_id=payload.promotion_id,
            coupon_code=payload.coupon_code,
            actor=MarketplaceOrderActorType.CLIENT,
        )
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)


@router.get("/{order_id}", response_model=OrderDetailOut)
def get_client_order(
    order_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("client:marketplace:orders:view")),
    db: Session = Depends(get_db),
) -> OrderDetailOut:
    client_id = _ensure_client_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.get_order_for_client(order_id=order_id, client_id=client_id)
        events = service.list_order_events(order_id=order_id)
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    return OrderDetailOut(**_order_out(order).dict(), events=[_event_out(event) for event in events])


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_client_order(
    order_id: str,
    payload: OrderCancelRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:marketplace:orders:cancel")),
    db: Session = Depends(get_db),
) -> OrderOut:
    client_id = _ensure_client_context(principal)
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.cancel_order(
            client_id=client_id,
            order_id=order_id,
            reason=payload.reason,
            actor=MarketplaceOrderActorType.CLIENT,
        )
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)
