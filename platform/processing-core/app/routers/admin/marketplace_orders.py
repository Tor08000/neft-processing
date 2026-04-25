from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin_capability import require_admin_capability
from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.marketplace_orders import MarketplaceOrderStatus
from app.models.marketplace_settlement import MarketplaceSettlementSnapshot
from app.schemas.marketplace.orders import (
    OrderDetailOut,
    OrderEventOut,
    OrderLineOut,
    OrderListResponse,
    OrderOut,
    OrderProofOut,
)
from app.schemas.marketplace.settlements import SettlementOverrideIn, SettlementSnapshotOut
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_orders_service import MarketplaceOrdersService, MarketplaceOrdersServiceError
from app.services.marketplace_settlement_service import MarketplaceSettlementService

router = APIRouter(
    prefix="/marketplace/orders",
    tags=["admin"],
    dependencies=[Depends(require_admin_capability("marketplace"))],
)


def _order_out(order) -> OrderOut:
    return OrderOut(
        id=str(order.id),
        client_id=str(order.client_id),
        partner_id=str(order.partner_id),
        status=order.status.value if hasattr(order.status, "value") else order.status,
        payment_status=order.payment_status.value if hasattr(order.payment_status, "value") else order.payment_status,
        payment_method=order.payment_method.value if hasattr(order.payment_method, "value") else order.payment_method,
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


def _snapshot_out(snapshot: MarketplaceSettlementSnapshot) -> SettlementSnapshotOut:
    return SettlementSnapshotOut(
        settlement_snapshot_id=str(snapshot.id),
        settlement_id=str(snapshot.settlement_id),
        order_id=str(snapshot.order_id),
        gross_amount=snapshot.gross_amount,
        platform_fee=snapshot.platform_fee,
        penalties=snapshot.penalties,
        partner_net=snapshot.partner_net,
        currency=snapshot.currency,
        finalized_at=snapshot.finalized_at,
        hash=snapshot.hash,
    )


def _handle_service_error(exc: MarketplaceOrdersServiceError) -> None:
    if exc.code == "order_not_found":
        raise HTTPException(status_code=404, detail=exc.code) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("", response_model=OrderListResponse)
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
) -> OrderListResponse:
    service = MarketplaceOrdersService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    items, total = service.list_orders_admin(
        status=status,
        client_id=client_id,
        partner_id=partner_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return OrderListResponse(items=[_order_out(item) for item in items], total=total, limit=limit, offset=offset)


@router.get("/{order_id}", response_model=OrderDetailOut)
def get_order(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OrderDetailOut:
    service = MarketplaceOrdersService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    try:
        order = service.get_order_for_admin(order_id=order_id)
        events = service.list_order_events(order_id=order_id)
        lines = service.list_order_lines(order_id=order_id)
        proofs = service.list_order_proofs(order_id=order_id)
    except MarketplaceOrdersServiceError as exc:
        _handle_service_error(exc)
    return OrderDetailOut(
        **_order_out(order).model_dump(),
        lines=[_line_out(line) for line in lines],
        proofs=[_proof_out(proof) for proof in proofs],
        events=[_event_out(event) for event in events],
    )


@router.get("/{order_id}/events", response_model=list[OrderEventOut])
def list_order_events(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> list[OrderEventOut]:
    service = MarketplaceOrdersService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    try:
        _ = service.get_order_for_admin(order_id=order_id)
        events = service.list_order_events(order_id=order_id)
    except MarketplaceOrdersServiceError as exc:
        _handle_service_error(exc)
    return [_event_out(event) for event in events]


@router.get("/{order_id}/settlement-snapshot", response_model=SettlementSnapshotOut)
def get_order_settlement_snapshot(
    order_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> SettlementSnapshotOut:
    _ = token
    snapshot = (
        db.query(MarketplaceSettlementSnapshot)
        .filter(MarketplaceSettlementSnapshot.order_id == order_id)
        .one_or_none()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="settlement_snapshot_not_found")
    return _snapshot_out(snapshot)


@router.post("/{order_id}/settlement-override", response_model=SettlementSnapshotOut)
def override_order_settlement(
    order_id: str,
    payload: SettlementOverrideIn,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_capability("marketplace", "override")),
) -> SettlementSnapshotOut:
    service = MarketplaceSettlementService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    try:
        snapshot = service.override_settlement_snapshot(
            order_id=order_id,
            gross=payload.gross_amount,
            platform_fee=payload.platform_fee,
            penalties=payload.penalties,
            partner_net=payload.partner_net,
            currency=payload.currency,
            reason=payload.reason,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _snapshot_out(snapshot)
