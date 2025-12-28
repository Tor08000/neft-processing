from __future__ import annotations

from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.models.crm import CRMSubscription, CRMSubscriptionStatus
from app.schemas.crm import CRMSubscriptionCreate
from app.services.crm import repository


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


__all__ = ["create_subscription", "set_subscription_status"]
