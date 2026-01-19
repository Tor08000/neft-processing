from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.marketplace_orders import MarketplaceOrderStatus
from app.schemas.marketplace.orders import OrderDetailOut, OrderEventOut, OrderOut
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_order_service import MarketplaceOrderService, MarketplaceOrderServiceError

router = APIRouter(prefix="/marketplace/orders", tags=["admin"])


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
    if exc.code == "order_not_found":
        raise HTTPException(status_code=404, detail=exc.code) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("", response_model=list[OrderOut])
def list_orders(
    request: Request,
    status: MarketplaceOrderStatus | None = Query(None),
    client_id: str | None = Query(None),
    partner_id: str | None = Query(None),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> list[OrderOut]:
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    items, _ = service.list_orders_admin(
        status=status,
        client_id=client_id,
        partner_id=partner_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [_order_out(item) for item in items]


@router.get("/{order_id}", response_model=OrderDetailOut)
def get_order(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OrderDetailOut:
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    try:
        order = service.get_order_for_admin(order_id=order_id)
        events = service.list_order_events(order_id=order_id)
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    return OrderDetailOut(**_order_out(order).dict(), events=[_event_out(event) for event in events])
