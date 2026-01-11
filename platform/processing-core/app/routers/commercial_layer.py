from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.models.commercial_layer import (
    ClientBranding,
    CommercialPlan,
    PlanFeature,
    PlanFeatureCode,
    UsageMetric,
)
from app.models.crm import ClientOnboardingState, ClientOnboardingStateEnum
from app.models.subscriptions_v1 import ClientSubscription, SubscriptionStatus
from app.schemas.commercial_layer import (
    BillingPlanSummary,
    BillingUsageSummary,
    ClientBrandingOut,
    ClientBrandingUpdate,
    OnboardingStateOut,
    OnboardingStepUpdate,
    PlanCreate,
    PlanFeatureOut,
    PlanOut,
    UpgradeRequest,
    UpgradeResponse,
    UsageCounterOut,
    UsageLimitSummary,
)
from app.services import admin_auth
from app.models.audit_log import AuditVisibility
from app.services.audit_service import AuditService, request_context_from_request
from app.services.commercial_layer import (
    build_limit_evaluations,
    create_pending_subscription,
    get_active_subscription,
    get_plan,
    get_plan_features,
    require_plan_feature,
)
from app.services.pricing_service import apply_overages, calculate_monthly_usage

router = APIRouter(prefix="/api", tags=["commercial-layer"])


def _ensure_client_context(token: dict) -> tuple[str, int]:
    client_id = token.get("client_id")
    tenant_id = token.get("tenant_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="missing_tenant_context")
    return str(client_id), int(tenant_id)


def _month_bounds(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        period_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        period_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return period_start, period_end


def _plan_out(plan: CommercialPlan, features: list[PlanFeature]) -> PlanOut:
    return PlanOut(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        base_price_monthly=Decimal(plan.base_price_monthly or 0),
        currency=plan.currency,
        billing_period=plan.billing_period,
        active=plan.active,
        features=[
            PlanFeatureOut(
                id=feature.id,
                feature=feature.feature,
                enabled=feature.enabled,
                limits=feature.limits,
            )
            for feature in features
        ],
    )


def _parse_completed_at(value: object | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _serialize_onboarding_state(state: ClientOnboardingState) -> OnboardingStateOut:
    meta = state.meta or {}
    current_step = meta.get("current_step") or (state.state.value if state.state else None)
    completed_steps = meta.get("completed_steps")
    completed_at = _parse_completed_at(meta.get("completed_at"))
    return OnboardingStateOut(
        client_id=state.client_id,
        current_step=current_step,
        completed_steps=completed_steps,
        updated_at=state.updated_at,
        completed_at=completed_at,
    )


@router.get("/client/billing/plan", response_model=BillingPlanSummary)
def get_client_billing_plan(
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> BillingPlanSummary:
    client_id, _tenant_id = _ensure_client_context(token)
    subscription = get_active_subscription(db, client_id=client_id)

    if not subscription:
        return BillingPlanSummary(plan=None, subscription_status=None, started_at=None, ends_at=None, next_invoice_date=None, usage=[])

    plan = get_plan(db, plan_id=str(subscription.plan_id))
    if not plan:
        raise HTTPException(status_code=404, detail="plan_not_found")

    features = get_plan_features(db, plan_id=str(plan.id))
    period_start, period_end = _month_bounds()
    usage_values = calculate_monthly_usage(db, client_id=client_id, period_start=period_start, period_end=period_end)
    usage_values = {metric: usage_values.get(metric, Decimal("0")) for metric in UsageMetric}
    limits = build_limit_evaluations(plan_features=features, usage_values=usage_values)

    return BillingPlanSummary(
        plan=_plan_out(plan, features),
        subscription_status=subscription.status,
        started_at=subscription.start_at,
        ends_at=subscription.end_at,
        next_invoice_date=period_end,
        usage=[
            UsageLimitSummary(
                metric=item.metric,
                used=item.used,
                limit=item.limit,
                overage=item.overage,
            )
            for item in limits
        ],
    )


@router.get("/client/billing/usage", response_model=BillingUsageSummary)
def get_client_billing_usage(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> BillingUsageSummary:
    client_id, _tenant_id = _ensure_client_context(token)
    period_start, period_end = _month_bounds()

    usage_values = calculate_monthly_usage(db, client_id=client_id, period_start=period_start, period_end=period_end)
    usage_values = {metric: usage_values.get(metric, Decimal("0")) for metric in UsageMetric}
    subscription = get_active_subscription(db, client_id=client_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    plan = get_plan(db, plan_id=str(subscription.plan_id))
    if not plan:
        raise HTTPException(status_code=404, detail="plan_not_found")

    features = get_plan_features(db, plan_id=str(plan.id))
    overages = apply_overages(plan, plan_features=features, usage=usage_values)

    return BillingUsageSummary(
        period_start=period_start,
        period_end=period_end,
        usage=[
            UsageCounterOut(
                metric=metric,
                period_start=period_start,
                period_end=period_end,
                value=value,
            )
            for metric, value in usage_values.items()
        ],
        overages=[
            UsageLimitSummary(
                metric=item.metric,
                used=item.value,
                limit=item.limit,
                overage=item.overage,
            )
            for item in overages
        ],
    )


@router.post("/client/billing/upgrade", response_model=UpgradeResponse)
def upgrade_plan(
    payload: UpgradeRequest,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> UpgradeResponse:
    client_id, tenant_id = _ensure_client_context(token)
    plan = get_plan(db, plan_id=str(payload.plan_id))
    if not plan or not plan.active:
        raise HTTPException(status_code=404, detail="plan_not_found")

    request_ctx = request_context_from_request(request, token=token)
    audit = AuditService(db).audit(
        event_type="PLAN_UPGRADE_REQUESTED",
        entity_type="client",
        entity_id=client_id,
        action="upgrade",
        visibility=AuditVisibility.INTERNAL,
        after={"plan_id": str(plan.id), "auto_upgrade": payload.auto_upgrade},
        request_ctx=request_ctx,
    )

    if payload.auto_upgrade:
        subscription = ClientSubscription(
            tenant_id=tenant_id,
            client_id=client_id,
            plan_id=str(plan.id),
            status=SubscriptionStatus.ACTIVE,
            start_at=datetime.now(timezone.utc),
            end_at=None,
            auto_renew=True,
            audit_event_id=str(audit.id),
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        return UpgradeResponse(subscription_id=subscription.id, status=subscription.status)

    subscription = create_pending_subscription(
        db,
        client_id=client_id,
        tenant_id=tenant_id,
        plan_id=str(plan.id),
        billing_account_id=None,
        audit_event_id=str(audit.id),
    )
    return UpgradeResponse(subscription_id=subscription.id, status=subscription.status)


@router.get("/client/branding", response_model=ClientBrandingOut)
def get_client_branding(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientBrandingOut:
    client_id, _tenant_id = _ensure_client_context(token)
    require_plan_feature(db, client_id=client_id, feature=PlanFeatureCode.WHITE_LABEL)
    branding = db.query(ClientBranding).filter(ClientBranding.client_id == client_id).one_or_none()
    if not branding:
        raise HTTPException(status_code=404, detail="branding_not_found")
    return ClientBrandingOut.model_validate(branding)


@router.post("/client/branding", response_model=ClientBrandingOut)
def update_client_branding(
    payload: ClientBrandingUpdate,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientBrandingOut:
    client_id, _tenant_id = _ensure_client_context(token)
    require_plan_feature(db, client_id=client_id, feature=PlanFeatureCode.WHITE_LABEL)
    branding = db.query(ClientBranding).filter(ClientBranding.client_id == client_id).one_or_none()
    if not branding:
        branding = ClientBranding(client_id=client_id)
        db.add(branding)

    for field, value in payload.model_dump().items():
        setattr(branding, field, value)

    db.commit()
    db.refresh(branding)
    return ClientBrandingOut.model_validate(branding)


@router.get("/client/onboarding/state", response_model=OnboardingStateOut)
def get_onboarding_state(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> OnboardingStateOut:
    client_id, _tenant_id = _ensure_client_context(token)
    state = db.query(ClientOnboardingState).filter(ClientOnboardingState.client_id == client_id).one_or_none()
    if not state:
        state = ClientOnboardingState(
            client_id=client_id,
            state=ClientOnboardingStateEnum.LEAD_CREATED,
            meta={},
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    return _serialize_onboarding_state(state)


@router.post("/client/onboarding/step", response_model=OnboardingStateOut)
def update_onboarding_step(
    payload: OnboardingStepUpdate,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> OnboardingStateOut:
    client_id, _tenant_id = _ensure_client_context(token)
    state = db.query(ClientOnboardingState).filter(ClientOnboardingState.client_id == client_id).one_or_none()
    if not state:
        state = ClientOnboardingState(
            client_id=client_id,
            state=ClientOnboardingStateEnum.LEAD_CREATED,
            meta={},
        )
        db.add(state)

    meta = state.meta or {}
    completed = meta.get("completed_steps") or {}
    completed[payload.step] = payload.completed
    meta["completed_steps"] = completed
    meta["current_step"] = payload.step
    try:
        state.state = ClientOnboardingStateEnum(payload.step)
    except ValueError:
        pass
    if payload.step == "done" and payload.completed:
        meta["completed_at"] = datetime.now(timezone.utc).isoformat()
        AuditService(db).audit(
            event_type="ONBOARDING_COMPLETED",
            entity_type="client",
            entity_id=client_id,
            action="onboarding",
            visibility=AuditVisibility.INTERNAL,
            request_ctx=request_context_from_request(request, token=token),
        )
    state.meta = meta

    db.commit()
    db.refresh(state)
    return _serialize_onboarding_state(state)


@router.get("/admin/plans", response_model=list[PlanOut])
def list_plans(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> list[PlanOut]:
    query = db.query(CommercialPlan)
    if active_only:
        query = query.filter(CommercialPlan.active.is_(True))
    plans = query.order_by(CommercialPlan.created_at.desc()).all()
    return [_plan_out(plan, get_plan_features(db, plan_id=str(plan.id))) for plan in plans]


@router.post("/admin/plans", response_model=PlanOut)
def create_plan(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> PlanOut:
    plan = CommercialPlan(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        base_price_monthly=payload.base_price_monthly,
        currency=payload.currency,
        billing_period=payload.billing_period,
        active=payload.active,
    )
    db.add(plan)
    db.flush()

    features: list[PlanFeature] = []
    if payload.features:
        for feature in payload.features:
            model = PlanFeature(
                plan_id=plan.id,
                feature=feature.feature,
                enabled=feature.enabled,
                limits=feature.limits,
            )
            db.add(model)
            features.append(model)

    db.commit()
    db.refresh(plan)
    return _plan_out(plan, features or get_plan_features(db, plan_id=str(plan.id)))


@router.get("/admin/subscriptions", response_model=list[UpgradeResponse])
def list_subscriptions(
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> list[UpgradeResponse]:
    subscriptions = db.query(ClientSubscription).order_by(ClientSubscription.created_at.desc()).limit(200).all()
    return [UpgradeResponse(subscription_id=subscription.id, status=subscription.status) for subscription in subscriptions]


@router.post("/admin/subscriptions/{subscription_id}/approve", response_model=UpgradeResponse)
def approve_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> UpgradeResponse:
    subscription = db.query(ClientSubscription).filter(ClientSubscription.id == subscription_id).one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    subscription.status = SubscriptionStatus.ACTIVE
    db.commit()
    db.refresh(subscription)
    return UpgradeResponse(subscription_id=subscription.id, status=subscription.status)


@router.get("/admin/branding", response_model=ClientBrandingOut)
def get_branding_admin(
    client_id: str = Query(...),
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> ClientBrandingOut:
    branding = db.query(ClientBranding).filter(ClientBranding.client_id == client_id).one_or_none()
    if not branding:
        raise HTTPException(status_code=404, detail="branding_not_found")
    return ClientBrandingOut.model_validate(branding)
