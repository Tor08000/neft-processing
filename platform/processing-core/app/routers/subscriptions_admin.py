from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.subscriptions_v1 import SubscriptionPlan
from app.schemas.subscriptions import AssignSubscriptionIn, ClientSubscriptionOut
from app.services import admin_auth
from app.services.subscription_service import (
    DEFAULT_TENANT_ID,
    assign_plan_to_client,
    ensure_free_subscription,
    get_client_subscription,
)
from app.routers.subscriptions_v1 import _build_plan_out

router = APIRouter(prefix="/admin/clients", tags=["subscriptions-admin"])


@router.post("/{client_id}/subscription/assign", response_model=ClientSubscriptionOut)
def assign_subscription_to_client(
    client_id: str,
    payload: AssignSubscriptionIn,
    db: Session = Depends(get_db),
    token: dict = Depends(admin_auth.verify_admin_token),
) -> ClientSubscriptionOut:
    tenant_id = int(token.get("tenant_id") or DEFAULT_TENANT_ID)
    subscription = assign_plan_to_client(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        plan_id=payload.plan_id,
        duration_months=payload.duration_months,
        auto_renew=payload.auto_renew,
    )
    plan = db.get(SubscriptionPlan, subscription.plan_id)
    return ClientSubscriptionOut(
        id=subscription.id,
        tenant_id=subscription.tenant_id,
        client_id=subscription.client_id,
        plan_id=subscription.plan_id,
        status=subscription.status,
        start_at=subscription.start_at,
        end_at=subscription.end_at,
        auto_renew=subscription.auto_renew,
        grace_until=subscription.grace_until,
        plan=_build_plan_out(db, plan) if plan else None,
    )


@router.get("/{client_id}/subscription", response_model=ClientSubscriptionOut)
def get_subscription_for_client(
    client_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(admin_auth.verify_admin_token),
) -> ClientSubscriptionOut:
    tenant_id = int(token.get("tenant_id") or DEFAULT_TENANT_ID)
    subscription = get_client_subscription(db, tenant_id=tenant_id, client_id=client_id)
    if not subscription:
        subscription = ensure_free_subscription(db, tenant_id=tenant_id, client_id=client_id)

    plan = db.get(SubscriptionPlan, subscription.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return ClientSubscriptionOut(
        id=subscription.id,
        tenant_id=subscription.tenant_id,
        client_id=subscription.client_id,
        plan_id=subscription.plan_id,
        status=subscription.status,
        start_at=subscription.start_at,
        end_at=subscription.end_at,
        auto_renew=subscription.auto_renew,
        grace_until=subscription.grace_until,
        plan=_build_plan_out(db, plan),
    )


__all__ = ["router"]
