from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.partner_subscriptions import PartnerPlan
from app.schemas.marketplace.subscriptions import PartnerPlanOut, PartnerSubscriptionOut
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.partner_subscription_service import PartnerSubscriptionService

router = APIRouter(prefix="/partner/marketplace", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


def _plan_out(plan) -> PartnerPlanOut:
    return PartnerPlanOut(
        plan_code=plan.plan_code,
        title=plan.title,
        description=plan.description,
        base_commission=plan.base_commission,
        monthly_fee=plan.monthly_fee,
        features=plan.features,
        limits=plan.limits,
    )


def _subscription_out(subscription, plan=None) -> PartnerSubscriptionOut:
    return PartnerSubscriptionOut(
        id=str(subscription.id),
        partner_id=str(subscription.partner_id),
        plan_code=subscription.plan_code,
        status=subscription.status.value if hasattr(subscription.status, "value") else subscription.status,
        started_at=subscription.started_at,
        ended_at=subscription.ended_at,
        billing_cycle=subscription.billing_cycle.value
        if hasattr(subscription.billing_cycle, "value")
        else subscription.billing_cycle,
        commission_rate=subscription.commission_rate,
        features=subscription.features,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
        plan=_plan_out(plan) if plan else None,
    )


@router.get("/plans", response_model=list[PartnerPlanOut])
def list_partner_plans(
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> list[PartnerPlanOut]:
    _ensure_partner_context(principal)
    service = PartnerSubscriptionService(db)
    return [_plan_out(plan) for plan in service.list_plans()]


@router.get("/subscription", response_model=PartnerSubscriptionOut)
def get_partner_subscription(
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PartnerSubscriptionOut:
    partner_id = _ensure_partner_context(principal)
    service = PartnerSubscriptionService(db)
    subscription = service.ensure_subscription(partner_id=partner_id)
    plan = db.get(PartnerPlan, subscription.plan_code)
    db.commit()
    return _subscription_out(subscription, plan)
