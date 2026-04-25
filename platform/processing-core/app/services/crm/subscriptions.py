from __future__ import annotations

from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.models.crm import CRMSubscription, CRMSubscriptionStatus
from app.schemas.crm import CRMSubscriptionCreate, CRMSubscriptionUpdate
from app.services.audit_service import RequestContext
from app.services.crm import events, repository


def create_subscription(
    db: Session,
    *,
    client_id: str,
    payload: CRMSubscriptionCreate,
) -> CRMSubscription:
    subscription = CRMSubscription(
        tenant_id=payload.tenant_id,
        client_id=client_id,
        tariff_plan_id=payload.tariff_plan_id,
        status=payload.status,
        billing_cycle=payload.billing_cycle,
        billing_day=payload.billing_day,
        started_at=payload.started_at,
        paused_at=payload.paused_at,
        ended_at=payload.ended_at,
        meta=payload.meta,
    )
    return repository.add_subscription(db, subscription)


def set_subscription_status(
    db: Session,
    *,
    subscription: CRMSubscription,
    status: CRMSubscriptionStatus,
) -> CRMSubscription:
    subscription.status = status
    if status == CRMSubscriptionStatus.PAUSED:
        subscription.paused_at = datetime.now(timezone.utc)
    if status == CRMSubscriptionStatus.ACTIVE:
        subscription.paused_at = None
    return repository.update_subscription(db, subscription)


def update_subscription(
    db: Session,
    *,
    subscription: CRMSubscription,
    payload: CRMSubscriptionUpdate,
    request_ctx: RequestContext | None,
) -> CRMSubscription:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subscription, field, value)
    subscription = repository.update_subscription(db, subscription)
    events.audit_event(
        db,
        event_type=events.CRM_SUBSCRIPTION_UPDATED,
        entity_type="crm_subscription",
        entity_id=str(subscription.id),
        payload={"status": subscription.status.value, "tariff_plan_id": subscription.tariff_plan_id},
        request_ctx=request_ctx,
    )
    return subscription


__all__ = ["create_subscription", "set_subscription_status", "update_subscription"]
