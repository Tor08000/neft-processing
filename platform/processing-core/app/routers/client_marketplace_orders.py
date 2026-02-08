from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_orders import (
    MarketplaceOrderActorType,
    MarketplaceOrderPaymentMethod,
    MarketplaceOrderStatus,
)
from app.schemas.marketplace.orders import (
    OrderCancelRequest,
    OrderCreateRequest,
    OrderDetailOut,
    OrderEventOut,
    OrderLineOut,
    OrderListResponse,
    OrderOut,
    OrderPayRequest,
    OrderProofOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_orders_service import MarketplaceOrdersService, MarketplaceOrdersServiceError


router = APIRouter(prefix="/v1/marketplace/client/orders", tags=["client-portal-v1"])


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
        status=order.status.value if hasattr(order.status, "value") else order.status,
        payment_status=order.payment_status,
        payment_method=order.payment_method,
        currency=order.currency,
        subtotal_amount=order.subtotal_amount,
        discount_amount=order.discount_amount,
        total_amount=order.total_amount,
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
        before_status=event.before_status.value if hasattr(event.before_status, "value") else event.before_status,
        after_status=event.after_status.value if hasattr(event.after_status, "value") else event.after_status,
        reason_code=event.reason_code,
        comment=event.comment,
        meta=event.meta,
    )


def _line_out(line) -> OrderLineOut:
    return OrderLineOut(
        id=str(line.id),
        order_id=str(line.order_id),
        offer_id=str(line.offer_id),
        subject_type=line.subject_type.value if hasattr(line.subject_type, "value") else line.subject_type,
        subject_id=str(line.subject_id),
        title_snapshot=line.title_snapshot,
        qty=line.qty,
        unit_price=line.unit_price,
        line_amount=line.line_amount,
        meta=line.meta,
    )


def _proof_out(proof) -> OrderProofOut:
    return OrderProofOut(
        id=str(proof.id),
        order_id=str(proof.order_id),
        kind=proof.kind.value if hasattr(proof.kind, "value") else proof.kind,
        attachment_id=str(proof.attachment_id),
        note=proof.note,
        created_at=proof.created_at,
        meta=proof.meta,
    )


def _handle_service_error(exc: MarketplaceOrdersServiceError) -> None:
    if exc.code == "forbidden":
        raise HTTPException(status_code=403, detail="forbidden") from exc
    if exc.code in {"order_not_found", "offer_not_found"}:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if exc.code in {"offer_not_active"}:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    if exc.code == "invalid_transition":
        raise HTTPException(
            status_code=409,
            detail={"error": "INVALID_STATE", "reason": exc.detail.get("event"), "from": exc.detail.get("from")},
        ) from exc
    if exc.code in {"items_required", "invalid_qty", "partner_mismatch", "currency_mismatch"}:
        raise HTTPException(status_code=400, detail=exc.code) from exc
    if exc.code == "proof_required":
        raise HTTPException(status_code=409, detail="PROOF_REQUIRED") from exc
    if exc.code == "payment_required":
        raise HTTPException(status_code=409, detail="PAYMENT_REQUIRED") from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("", response_model=OrderListResponse)
def list_client_orders(
    request: Request,
    status: MarketplaceOrderStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("client:marketplace:orders:list")),
    db: Session = Depends(get_db),
) -> OrderListResponse:
    client_id = _ensure_client_context(principal)
    service = MarketplaceOrdersService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    items, total = service.list_orders_for_client(
        client_id=client_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return OrderListResponse(items=[_order_out(item) for item in items], total=total, limit=limit, offset=offset)


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_client_order(
    payload: OrderCreateRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:marketplace:orders:create")),
    db: Session = Depends(get_db),
) -> OrderOut:
    client_id = _ensure_client_context(principal)
    service = MarketplaceOrdersService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.create_order(
            client_id=client_id,
            items=[{"offer_id": item.offer_id, "qty": item.qty} for item in payload.items],
            payment_method=MarketplaceOrderPaymentMethod(payload.payment_method),
            actor=MarketplaceOrderActorType.CLIENT,
        )
    except MarketplaceOrdersServiceError as exc:
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
    service = MarketplaceOrdersService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.get_order_for_client(order_id=order_id, client_id=client_id)
        events = service.list_order_events(order_id=order_id)
        lines = service.list_order_lines(order_id=order_id)
        proofs = service.list_order_proofs(order_id=order_id)
    except MarketplaceOrdersServiceError as exc:
        _handle_service_error(exc)
    return OrderDetailOut(
        **_order_out(order).dict(),
        lines=[_line_out(line) for line in lines],
        proofs=[_proof_out(proof) for proof in proofs],
        events=[_event_out(event) for event in events],
    )


@router.get("/{order_id}/events", response_model=list[OrderEventOut])
def list_client_order_events(
    order_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("client:marketplace:orders:view")),
    db: Session = Depends(get_db),
) -> list[OrderEventOut]:
    client_id = _ensure_client_context(principal)
    service = MarketplaceOrdersService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        _ = service.get_order_for_client(order_id=order_id, client_id=client_id)
        events = service.list_order_events(order_id=order_id)
    except MarketplaceOrdersServiceError as exc:
        _handle_service_error(exc)
    return [_event_out(event) for event in events]


@router.post("/{order_id}:pay", response_model=OrderOut)
def pay_client_order(
    order_id: str,
    payload: OrderPayRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:marketplace:orders:pay")),
    db: Session = Depends(get_db),
) -> OrderOut:
    client_id = _ensure_client_context(principal)
    service = MarketplaceOrdersService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.pay_order(
            client_id=client_id,
            order_id=order_id,
            payment_method=MarketplaceOrderPaymentMethod(payload.payment_method),
            actor=MarketplaceOrderActorType.CLIENT,
        )
    except MarketplaceOrdersServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_client_order(
    order_id: str,
    payload: OrderCancelRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:marketplace:orders:cancel")),
    db: Session = Depends(get_db),
) -> OrderOut:
    client_id = _ensure_client_context(principal)
    service = MarketplaceOrdersService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = service.cancel_order(
            client_id=client_id,
            order_id=order_id,
            reason=payload.reason,
            actor=MarketplaceOrderActorType.CLIENT,
        )
    except MarketplaceOrdersServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _order_out(order)
