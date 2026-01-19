from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit_log import AuditLog, AuditVisibility
from app.models.notifications import NotificationChannel, NotificationPriority, NotificationSubjectType
from app.models.partner_core import (
    PartnerOffer,
    PartnerOfferStatus,
    PartnerOrder,
    PartnerOrderStatus,
    PartnerProfile,
    PartnerProfileStatus,
)
from app.schemas.partner_core import (
    PartnerAnalyticsSummary,
    PartnerOfferIn,
    PartnerOfferOut,
    PartnerOfferUpdate,
    PartnerOrderListResponse,
    PartnerOrderOut,
    PartnerOrderSeedIn,
    PartnerOrderStatusUpdate,
    PartnerProfileOut,
    PartnerProfileUpdate,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.notifications_v1 import enqueue_notification_message
from app.services.partner_core_service import ensure_partner_profile, profile_payload

router = APIRouter(prefix="/partner", tags=["partner-core"])


def _resolve_org_id(principal: Principal) -> int:
    org_id_raw = principal.raw_claims.get("org_id") or principal.raw_claims.get("client_id") or principal.raw_claims.get(
        "partner_id"
    )
    if org_id_raw is None:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "missing_org_context"})
    try:
        return int(org_id_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "invalid_org_context"}) from exc


def _ensure_capability(db: Session, principal: Principal, capability: str) -> int:
    org_id = _resolve_org_id(principal)
    snapshot = get_org_entitlements_snapshot(db, org_id=org_id)
    capabilities = snapshot.entitlements.get("capabilities") or []
    if capability not in capabilities:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_capability", "capability": capability},
        )
    return org_id


def _offer_out(offer: PartnerOffer) -> PartnerOfferOut:
    return PartnerOfferOut(
        id=str(offer.id),
        org_id=offer.org_id,
        code=offer.code,
        title=offer.title,
        description=offer.description,
        base_price=offer.base_price,
        currency=offer.currency,
        status=offer.status.value if hasattr(offer.status, "value") else str(offer.status),
        created_at=offer.created_at,
        updated_at=offer.updated_at,
    )


def _order_out(order: PartnerOrder) -> PartnerOrderOut:
    return PartnerOrderOut(
        id=str(order.id),
        partner_org_id=order.partner_org_id,
        client_org_id=order.client_org_id,
        offer_id=str(order.offer_id) if order.offer_id else None,
        title=order.title,
        status=order.status.value if hasattr(order.status, "value") else str(order.status),
        response_due_at=order.response_due_at,
        resolution_due_at=order.resolution_due_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _resolve_offer_status(value: str | None, *, default: PartnerOfferStatus) -> PartnerOfferStatus:
    if value is None:
        return default
    try:
        return PartnerOfferStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_offer_status") from exc


def _resolve_order_status(value: str) -> PartnerOrderStatus:
    try:
        return PartnerOrderStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_order_status") from exc


def _audit_order_event(
    db: Session,
    *,
    request: Request,
    principal: Principal,
    event_type: str,
    order: PartnerOrder,
    before: dict | None,
    after: dict | None,
    action: str,
) -> None:
    AuditService(db).audit(
        event_type=event_type,
        entity_type="partner_order",
        entity_id=str(order.id),
        action=action,
        visibility=AuditVisibility.INTERNAL,
        before=before,
        after=after,
        external_refs={
            "partner_org_id": order.partner_org_id,
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
    )


def _maybe_audit_sla_breach(
    db: Session,
    *,
    request: Request,
    principal: Principal,
    order: PartnerOrder,
    due_at: datetime | None,
    reason: str,
) -> None:
    if due_at is None:
        return
    if datetime.now(timezone.utc) <= due_at:
        return
    AuditService(db).audit(
        event_type="partner_sla_breached",
        entity_type="partner_order",
        entity_id=str(order.id),
        action="sla_breached",
        visibility=AuditVisibility.INTERNAL,
        after={"reason": reason, "due_at": due_at},
        external_refs={
            "partner_org_id": order.partner_org_id,
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
    )


def _notify_partner(
    db: Session,
    *,
    event_type: str,
    partner_org_id: int,
    template_vars: dict,
    dedupe_key: str,
) -> None:
    enqueue_notification_message(
        db,
        event_type=event_type,
        subject_type=NotificationSubjectType.PARTNER,
        subject_id=str(partner_org_id),
        template_code=event_type,
        template_vars=template_vars,
        priority=NotificationPriority.NORMAL,
        dedupe_key=dedupe_key,
        channels=[NotificationChannel.PUSH],
    )


@router.get("/profile", response_model=PartnerProfileOut)
def get_partner_profile(
    principal: Principal = Depends(require_permission("partner:profile:view")),
    db: Session = Depends(get_db),
) -> PartnerProfileOut:
    org_id = _ensure_capability(db, principal, "PARTNER_CORE")
    profile = ensure_partner_profile(db, org_id=org_id)
    if profile in db.new:
        db.commit()
        db.refresh(profile)
    return PartnerProfileOut(**profile_payload(profile))


@router.patch("/profile", response_model=PartnerProfileOut)
def update_partner_profile(
    payload: PartnerProfileUpdate,
    principal: Principal = Depends(require_permission("partner:profile:manage")),
    db: Session = Depends(get_db),
) -> PartnerProfileOut:
    org_id = _ensure_capability(db, principal, "PARTNER_CORE")
    profile = db.query(PartnerProfile).filter(PartnerProfile.org_id == org_id).one_or_none()
    if not profile:
        profile = ensure_partner_profile(db, org_id=org_id)
    if payload.display_name is not None:
        profile.display_name = payload.display_name
    if payload.contacts_json is not None:
        profile.contacts_json = payload.contacts_json
    if profile.status == PartnerProfileStatus.ONBOARDING:
        profile.status = PartnerProfileStatus.ACTIVE
    db.commit()
    db.refresh(profile)
    return PartnerProfileOut(**profile_payload(profile))


@router.get("/offers", response_model=list[PartnerOfferOut])
def list_partner_offers(
    status: PartnerOfferStatus | None = Query(None),
    principal: Principal = Depends(require_permission("partner:offers:list")),
    db: Session = Depends(get_db),
) -> list[PartnerOfferOut]:
    org_id = _ensure_capability(db, principal, "PARTNER_CATALOG")
    query = db.query(PartnerOffer).filter(PartnerOffer.org_id == org_id)
    if status:
        query = query.filter(PartnerOffer.status == status)
    offers = query.order_by(PartnerOffer.created_at.desc()).all()
    return [_offer_out(offer) for offer in offers]


@router.post("/offers", response_model=PartnerOfferOut, status_code=status.HTTP_201_CREATED)
def create_partner_offer(
    payload: PartnerOfferIn,
    principal: Principal = Depends(require_permission("partner:offers:manage")),
    db: Session = Depends(get_db),
) -> PartnerOfferOut:
    org_id = _ensure_capability(db, principal, "PARTNER_CATALOG")
    existing = (
        db.query(PartnerOffer)
        .filter(PartnerOffer.org_id == org_id, PartnerOffer.code == payload.code)
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=409, detail="offer_code_exists")
    status_value = _resolve_offer_status(payload.status, default=PartnerOfferStatus.INACTIVE)
    offer = PartnerOffer(
        org_id=org_id,
        code=payload.code,
        title=payload.title,
        description=payload.description,
        base_price=payload.base_price,
        currency=payload.currency,
        status=status_value,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return _offer_out(offer)


@router.patch("/offers/{offer_id}", response_model=PartnerOfferOut)
def update_partner_offer(
    offer_id: str,
    payload: PartnerOfferUpdate,
    principal: Principal = Depends(require_permission("partner:offers:manage")),
    db: Session = Depends(get_db),
) -> PartnerOfferOut:
    org_id = _ensure_capability(db, principal, "PARTNER_CATALOG")
    offer = db.query(PartnerOffer).filter(PartnerOffer.id == offer_id, PartnerOffer.org_id == org_id).one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    if payload.title is not None:
        offer.title = payload.title
    if payload.description is not None:
        offer.description = payload.description
    if payload.base_price is not None:
        offer.base_price = payload.base_price
    if payload.currency is not None:
        offer.currency = payload.currency
    if payload.status is not None:
        offer.status = _resolve_offer_status(payload.status, default=offer.status)
    db.commit()
    db.refresh(offer)
    return _offer_out(offer)


@router.post("/offers/{offer_id}/activate", response_model=PartnerOfferOut)
def activate_partner_offer(
    offer_id: str,
    principal: Principal = Depends(require_permission("partner:offers:manage")),
    db: Session = Depends(get_db),
) -> PartnerOfferOut:
    org_id = _ensure_capability(db, principal, "PARTNER_CATALOG")
    offer = db.query(PartnerOffer).filter(PartnerOffer.id == offer_id, PartnerOffer.org_id == org_id).one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    offer.status = PartnerOfferStatus.ACTIVE
    db.commit()
    db.refresh(offer)
    return _offer_out(offer)


@router.post("/offers/{offer_id}/deactivate", response_model=PartnerOfferOut)
def deactivate_partner_offer(
    offer_id: str,
    principal: Principal = Depends(require_permission("partner:offers:manage")),
    db: Session = Depends(get_db),
) -> PartnerOfferOut:
    org_id = _ensure_capability(db, principal, "PARTNER_CATALOG")
    offer = db.query(PartnerOffer).filter(PartnerOffer.id == offer_id, PartnerOffer.org_id == org_id).one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    offer.status = PartnerOfferStatus.INACTIVE
    db.commit()
    db.refresh(offer)
    return _offer_out(offer)


@router.get("/orders", response_model=PartnerOrderListResponse)
def list_partner_orders(
    status: PartnerOrderStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    principal: Principal = Depends(require_permission("partner:orders:list")),
    db: Session = Depends(get_db),
) -> PartnerOrderListResponse:
    org_id = _ensure_capability(db, principal, "PARTNER_ORDERS")
    try:
        offset = int(cursor or 0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid_cursor") from exc
    query = db.query(PartnerOrder).filter(PartnerOrder.partner_org_id == org_id)
    if status:
        query = query.filter(PartnerOrder.status == status)
    orders = (
        query.order_by(PartnerOrder.created_at.desc(), PartnerOrder.id.desc()).offset(offset).limit(limit).all()
    )
    next_cursor = str(offset + limit) if len(orders) == limit else None
    return PartnerOrderListResponse(items=[_order_out(order) for order in orders], next_cursor=next_cursor)


@router.get("/orders/{order_id}", response_model=PartnerOrderOut)
def get_partner_order(
    order_id: str,
    principal: Principal = Depends(require_permission("partner:orders:view")),
    db: Session = Depends(get_db),
) -> PartnerOrderOut:
    org_id = _ensure_capability(db, principal, "PARTNER_ORDERS")
    order = (
        db.query(PartnerOrder)
        .filter(PartnerOrder.id == order_id, PartnerOrder.partner_org_id == org_id)
        .one_or_none()
    )
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")
    return _order_out(order)


@router.post("/orders/{order_id}/accept", response_model=PartnerOrderOut)
def accept_partner_order(
    order_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:orders:update")),
    db: Session = Depends(get_db),
) -> PartnerOrderOut:
    org_id = _ensure_capability(db, principal, "PARTNER_ORDERS")
    order = (
        db.query(PartnerOrder)
        .filter(PartnerOrder.id == order_id, PartnerOrder.partner_org_id == org_id)
        .one_or_none()
    )
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")
    if order.status != PartnerOrderStatus.NEW:
        raise HTTPException(status_code=409, detail="invalid_transition")
    before = _order_out(order).model_dump()
    order.status = PartnerOrderStatus.ACCEPTED
    db.commit()
    db.refresh(order)
    after = _order_out(order).model_dump()
    _audit_order_event(
        db,
        request=request,
        principal=principal,
        event_type="partner_order_accepted",
        order=order,
        before=before,
        after=after,
        action="accept",
    )
    _maybe_audit_sla_breach(
        db, request=request, principal=principal, order=order, due_at=order.response_due_at, reason="response"
    )
    _notify_partner(
        db,
        event_type="partner_order_status_changed",
        partner_org_id=order.partner_org_id,
        template_vars={"order_id": str(order.id), "status": order.status.value},
        dedupe_key=f"partner_order_status_changed:{order.id}:{order.status.value}",
    )
    db.commit()
    return _order_out(order)


@router.post("/orders/{order_id}/reject", response_model=PartnerOrderOut)
def reject_partner_order(
    order_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:orders:update")),
    db: Session = Depends(get_db),
) -> PartnerOrderOut:
    org_id = _ensure_capability(db, principal, "PARTNER_ORDERS")
    order = (
        db.query(PartnerOrder)
        .filter(PartnerOrder.id == order_id, PartnerOrder.partner_org_id == org_id)
        .one_or_none()
    )
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")
    if order.status != PartnerOrderStatus.NEW:
        raise HTTPException(status_code=409, detail="invalid_transition")
    before = _order_out(order).model_dump()
    order.status = PartnerOrderStatus.REJECTED
    db.commit()
    db.refresh(order)
    after = _order_out(order).model_dump()
    _audit_order_event(
        db,
        request=request,
        principal=principal,
        event_type="partner_order_rejected",
        order=order,
        before=before,
        after=after,
        action="reject",
    )
    _maybe_audit_sla_breach(
        db, request=request, principal=principal, order=order, due_at=order.response_due_at, reason="response"
    )
    _notify_partner(
        db,
        event_type="partner_order_status_changed",
        partner_org_id=order.partner_org_id,
        template_vars={"order_id": str(order.id), "status": order.status.value},
        dedupe_key=f"partner_order_status_changed:{order.id}:{order.status.value}",
    )
    db.commit()
    return _order_out(order)


@router.post("/orders/{order_id}/status", response_model=PartnerOrderOut)
def update_partner_order_status(
    order_id: str,
    payload: PartnerOrderStatusUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:orders:update")),
    db: Session = Depends(get_db),
) -> PartnerOrderOut:
    org_id = _ensure_capability(db, principal, "PARTNER_ORDERS")
    order = (
        db.query(PartnerOrder)
        .filter(PartnerOrder.id == order_id, PartnerOrder.partner_org_id == org_id)
        .one_or_none()
    )
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")
    target_status = _resolve_order_status(payload.status)
    if target_status not in {PartnerOrderStatus.IN_PROGRESS, PartnerOrderStatus.DONE}:
        raise HTTPException(status_code=400, detail="invalid_status_transition")
    if order.status not in {PartnerOrderStatus.ACCEPTED, PartnerOrderStatus.IN_PROGRESS}:
        raise HTTPException(status_code=409, detail="invalid_transition")
    before = _order_out(order).model_dump()
    order.status = target_status
    db.commit()
    db.refresh(order)
    after = _order_out(order).model_dump()
    _audit_order_event(
        db,
        request=request,
        principal=principal,
        event_type="partner_order_status_changed",
        order=order,
        before=before,
        after=after,
        action="status_change",
    )
    _maybe_audit_sla_breach(
        db,
        request=request,
        principal=principal,
        order=order,
        due_at=order.resolution_due_at,
        reason="resolution",
    )
    _notify_partner(
        db,
        event_type="partner_order_status_changed",
        partner_org_id=order.partner_org_id,
        template_vars={"order_id": str(order.id), "status": order.status.value},
        dedupe_key=f"partner_order_status_changed:{order.id}:{order.status.value}",
    )
    db.commit()
    return _order_out(order)


@router.get("/analytics/summary", response_model=PartnerAnalyticsSummary)
def partner_analytics_summary(
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    principal: Principal = Depends(require_permission("partner:analytics:view")),
    db: Session = Depends(get_db),
) -> PartnerAnalyticsSummary:
    org_id = _ensure_capability(db, principal, "PARTNER_ANALYTICS")
    query = db.query(PartnerOrder).filter(PartnerOrder.partner_org_id == org_id)
    if date_from:
        query = query.filter(PartnerOrder.created_at >= date_from)
    if date_to:
        query = query.filter(PartnerOrder.created_at <= date_to)
    orders_total = query.count()
    status_rows = (
        query.with_entities(PartnerOrder.status, func.count(PartnerOrder.id))
        .group_by(PartnerOrder.status)
        .all()
    )
    orders_by_status = {
        (status.value if hasattr(status, "value") else str(status)): count for status, count in status_rows
    }

    order_ids_subq = db.query(PartnerOrder.id).filter(PartnerOrder.partner_org_id == org_id).subquery()
    sla_query = db.query(AuditLog).filter(
        AuditLog.event_type == "partner_sla_breached",
        AuditLog.entity_id.in_(db.query(order_ids_subq.c.id)),
    )
    if date_from:
        sla_query = sla_query.filter(AuditLog.ts >= date_from)
    if date_to:
        sla_query = sla_query.filter(AuditLog.ts <= date_to)
    sla_breaches_count = sla_query.count()

    last_activity = None
    if orders_total:
        last_activity = [
            {
                "order_id": str(order.id),
                "status": order.status.value if hasattr(order.status, "value") else str(order.status),
                "updated_at": order.updated_at,
            }
            for order in query.order_by(PartnerOrder.updated_at.desc()).limit(10).all()
        ]

    return PartnerAnalyticsSummary(
        orders_total=orders_total,
        orders_by_status=orders_by_status,
        sla_breaches_count=sla_breaches_count,
        last_10_activity=last_activity,
    )


@router.post("/orders/seed", response_model=PartnerOrderOut, status_code=status.HTTP_201_CREATED)
def seed_partner_order(
    payload: PartnerOrderSeedIn,
    request: Request,
    principal: Principal = Depends(require_permission("admin:contracts:*")),
    db: Session = Depends(get_db),
) -> PartnerOrderOut:
    response_due_at = payload.response_due_at or datetime.now(timezone.utc) + timedelta(hours=2)
    resolution_due_at = payload.resolution_due_at or datetime.now(timezone.utc) + timedelta(hours=24)
    order = PartnerOrder(
        partner_org_id=payload.partner_org_id,
        client_org_id=payload.client_org_id,
        offer_id=payload.offer_id,
        title=payload.title,
        status=PartnerOrderStatus.NEW,
        response_due_at=response_due_at,
        resolution_due_at=resolution_due_at,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    _audit_order_event(
        db,
        request=request,
        principal=principal,
        event_type="partner_new_order_created",
        order=order,
        before=None,
        after=_order_out(order).model_dump(),
        action="seed",
    )
    _notify_partner(
        db,
        event_type="partner_new_order",
        partner_org_id=order.partner_org_id,
        template_vars={"order_id": str(order.id), "title": order.title},
        dedupe_key=f"partner_new_order:{order.id}",
    )
    db.commit()
    return _order_out(order)
