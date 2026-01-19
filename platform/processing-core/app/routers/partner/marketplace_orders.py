from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_orders import MarketplaceOrder, MarketplaceOrderActorType, MarketplaceOrderStatus
from app.models.marketplace_settlement import MarketplaceAdjustment, MarketplaceAdjustmentType, MarketplaceSettlementSnapshot
from app.models.marketplace_order_sla import OrderSlaEvaluation
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
from app.schemas.partner_trust import (
    FeeExplainOut,
    PartnerOrderSettlementOut,
    PenaltySourceRefOut,
    SettlementPenaltyOut,
    SettlementSnapshotOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import AuditService, AuditVisibility, _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_order_service import MarketplaceOrderService, MarketplaceOrderServiceError
from app.services.partner_trust_metrics import metrics as partner_trust_metrics

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


def _fee_explain(*, order, gross_amount: Decimal, platform_fee_amount: Decimal) -> FeeExplainOut:
    snapshot = order.commission_snapshot or {}
    basis_raw = (snapshot.get("type") or "FIXED").upper()
    basis = "TIER" if basis_raw == "TIERED" else basis_raw
    rate = snapshot.get("rate")
    rate_value = Decimal(str(rate)) if rate is not None else None
    if basis == "PERCENT" and rate_value is not None:
        explain = f"{(rate_value * 100):.2f}% of gross"
    elif basis == "FIXED":
        explain = f"Fixed fee {platform_fee_amount}"
    else:
        explain = "Tiered fee applied to gross"
    return FeeExplainOut(
        amount=platform_fee_amount,
        basis=basis,
        rate=rate_value,
        explain=explain,
    )


def _penalties_for_order(db: Session, order_id: str) -> list[SettlementPenaltyOut]:
    adjustments = (
        db.query(MarketplaceAdjustment)
        .filter(
            MarketplaceAdjustment.order_id == order_id,
            MarketplaceAdjustment.type == MarketplaceAdjustmentType.PENALTY,
        )
        .order_by(MarketplaceAdjustment.created_at.asc())
        .all()
    )
    penalties: list[SettlementPenaltyOut] = []
    for adjustment in adjustments:
        source_ref = None
        meta = adjustment.meta or {}
        evaluation_id = meta.get("evaluation_id") if isinstance(meta, dict) else None
        if evaluation_id:
            evaluation = db.query(OrderSlaEvaluation).filter(OrderSlaEvaluation.id == evaluation_id).one_or_none()
            source_ref = PenaltySourceRefOut(
                audit_event_id=str(evaluation.audit_event_id) if evaluation else None,
                sla_event_id=str(evaluation.id) if evaluation else str(evaluation_id),
            )
        penalties.append(
            SettlementPenaltyOut(
                type="SLA_PENALTY",
                amount=Decimal(adjustment.amount),
                reason=adjustment.reason_code or "SLA breach",
                source_ref=source_ref,
            )
        )
    return penalties


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


@router.get("/{order_id}/settlement", response_model=PartnerOrderSettlementOut)
def get_partner_order_settlement(
    order_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PartnerOrderSettlementOut:
    partner_id = _ensure_partner_context(principal)
    order_record = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).one_or_none()
    if order_record and str(order_record.partner_id) != partner_id:
        AuditService(db).audit(
            event_type="PARTNER_ACCESS_FORBIDDEN",
            entity_type="marketplace_order",
            entity_id=str(order_id),
            action="FORBIDDEN",
            visibility=AuditVisibility.INTERNAL,
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
        )
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceOrderService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        order = order_record or service.get_order_for_partner(order_id=order_id, partner_id=partner_id)
    except MarketplaceOrderServiceError as exc:
        _handle_service_error(exc)
    status = order.status.value if hasattr(order.status, "value") else str(order.status)
    if status not in {MarketplaceOrderStatus.ACCEPTED.value, MarketplaceOrderStatus.COMPLETED.value}:
        raise HTTPException(status_code=409, detail="settlement_not_available")
    snapshot = (
        db.query(MarketplaceSettlementSnapshot)
        .filter(MarketplaceSettlementSnapshot.order_id == order_id)
        .one_or_none()
    )
    breakdown_json = order.settlement_breakdown_json or {}
    gross_amount = Decimal(snapshot.gross_amount) if snapshot else Decimal(breakdown_json.get("gross_amount") or 0)
    platform_fee_amount = (
        Decimal(snapshot.platform_fee) if snapshot else Decimal(breakdown_json.get("platform_fee_amount") or 0)
    )
    penalties_amount = Decimal(snapshot.penalties) if snapshot else Decimal(breakdown_json.get("penalties_amount") or 0)
    partner_net = (
        Decimal(snapshot.partner_net)
        if snapshot
        else Decimal(breakdown_json.get("partner_net_amount") or (gross_amount - platform_fee_amount - penalties_amount))
    )
    currency = snapshot.currency if snapshot else breakdown_json.get("currency") or "RUB"
    fee_explain = _fee_explain(
        order=order, gross_amount=gross_amount, platform_fee_amount=platform_fee_amount
    )
    penalties = _penalties_for_order(db, str(order.id))
    partner_trust_metrics.mark_settlement_breakdown_requested()
    return PartnerOrderSettlementOut(
        order_id=str(order.id),
        currency=currency,
        gross_amount=gross_amount,
        platform_fee=fee_explain,
        penalties=penalties,
        partner_net=partner_net,
        snapshot=SettlementSnapshotOut(
            settlement_snapshot_id=str(snapshot.id) if snapshot else None,
            finalized_at=snapshot.finalized_at if snapshot else None,
            hash=snapshot.hash if snapshot else None,
        )
        if snapshot
        else None,
    )


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
