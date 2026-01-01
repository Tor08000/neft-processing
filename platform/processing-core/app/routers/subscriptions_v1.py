from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.subscriptions_v1 import (
    BonusRule,
    RoleEntitlement,
    SubscriptionModuleCode,
    SubscriptionPlan,
    SubscriptionPlanModule,
)
from app.schemas.subscriptions import (
    BonusRuleBase,
    BonusRuleOut,
    BonusRuleUpdate,
    ClientSubscriptionOut,
    GamificationSummary,
    RoleEntitlementBase,
    RoleEntitlementOut,
    SubscriptionBenefitsOut,
    SubscriptionPlanCreate,
    SubscriptionPlanModuleBase,
    SubscriptionPlanModuleOut,
    SubscriptionPlanOut,
    SubscriptionPlanUpdate,
)
from app.services import admin_auth, client_auth
from app.services.gamification_service import get_client_rewards_summary
from app.services.subscription_service import (
    DEFAULT_TENANT_ID,
    create_bonus_rule,
    create_plan,
    ensure_free_subscription,
    get_client_subscription,
    get_plan,
    list_bonus_rules,
    list_plans,
    update_bonus_rule,
    update_plan,
    update_plan_modules,
    update_role_entitlements,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _plan_modules(db: Session, plan_id: str) -> list[SubscriptionPlanModule]:
    return (
        db.query(SubscriptionPlanModule)
        .filter(SubscriptionPlanModule.plan_id == plan_id)
        .order_by(SubscriptionPlanModule.module_code.asc())
        .all()
    )


def _build_plan_out(db: Session, plan: SubscriptionPlan) -> SubscriptionPlanOut:
    modules = _plan_modules(db, plan.id)
    roles = db.query(RoleEntitlement).filter(RoleEntitlement.plan_id == plan.id).all()
    bonuses = db.query(BonusRule).filter(BonusRule.plan_id == plan.id).all()

    return SubscriptionPlanOut(
        id=plan.id,
        code=plan.code,
        title=plan.title,
        description=plan.description,
        is_active=plan.is_active,
        billing_period_months=plan.billing_period_months,
        price_cents=plan.price_cents,
        currency=plan.currency,
        modules=[
            SubscriptionPlanModuleOut(
                id=module.id,
                module_code=module.module_code,
                enabled=module.enabled,
                tier=module.tier,
                limits=module.limits,
            )
            for module in modules
        ],
        roles=[RoleEntitlementOut(id=role.id, role_code=role.role_code, entitlements=role.entitlements) for role in roles],
        bonus_rules=[
            BonusRuleOut(
                id=rule.id,
                plan_id=rule.plan_id,
                rule_code=rule.rule_code,
                title=rule.title,
                condition=rule.condition,
                reward=rule.reward,
                enabled=rule.enabled,
            )
            for rule in bonuses
        ],
    )


def _modules_with_fallback(modules: list[SubscriptionPlanModule]) -> list[SubscriptionPlanModuleOut]:
    module_map = {module.module_code: module for module in modules}
    output: list[SubscriptionPlanModuleOut] = []
    for code in SubscriptionModuleCode:
        module = module_map.get(code)
        if module:
            output.append(
                SubscriptionPlanModuleOut(
                    id=module.id,
                    module_code=module.module_code,
                    enabled=module.enabled,
                    tier=module.tier,
                    limits=module.limits,
                )
            )
        else:
            output.append(SubscriptionPlanModuleOut(module_code=code, enabled=False, tier=None, limits=None))
    return output


@router.get("/plans", response_model=list[SubscriptionPlanOut])
def list_subscription_plans(
    db: Session = Depends(get_db),
    active_only: bool = Query(False),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> list[SubscriptionPlanOut]:
    plans = list_plans(db, active_only=active_only)
    return [_build_plan_out(db, plan) for plan in plans]


@router.post("/plans", response_model=SubscriptionPlanOut)
def create_subscription_plan(
    payload: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> SubscriptionPlanOut:
    plan = create_plan(db, payload)
    return _build_plan_out(db, plan)


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanOut)
def get_subscription_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> SubscriptionPlanOut:
    plan = get_plan(db, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _build_plan_out(db, plan)


@router.patch("/plans/{plan_id}", response_model=SubscriptionPlanOut)
def patch_subscription_plan(
    plan_id: str,
    payload: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> SubscriptionPlanOut:
    plan = get_plan(db, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    updated = update_plan(db, plan=plan, payload=payload)
    return _build_plan_out(db, updated)


@router.patch("/plans/{plan_id}/modules", response_model=list[SubscriptionPlanModuleOut])
def patch_subscription_plan_modules(
    plan_id: str,
    payload: list[SubscriptionPlanModuleBase],
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> list[SubscriptionPlanModuleOut]:
    modules = update_plan_modules(db, plan_id=plan_id, modules=payload)
    return _modules_with_fallback(modules)


@router.patch("/plans/{plan_id}/roles", response_model=list[RoleEntitlementBase])
def patch_subscription_plan_roles(
    plan_id: str,
    payload: list[RoleEntitlementBase],
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> list[RoleEntitlementBase]:
    roles = update_role_entitlements(db, plan_id=plan_id, roles=payload)
    return [RoleEntitlementBase(role_code=role.role_code, entitlements=role.entitlements) for role in roles]


@router.get("/bonus-rules", response_model=list[BonusRuleOut])
def list_subscription_bonus_rules(
    db: Session = Depends(get_db),
    plan_id: str | None = Query(None),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> list[BonusRuleOut]:
    rules = list_bonus_rules(db, plan_id=plan_id)
    return [
        BonusRuleOut(
            id=rule.id,
            plan_id=rule.plan_id,
            rule_code=rule.rule_code,
            title=rule.title,
            condition=rule.condition,
            reward=rule.reward,
            enabled=rule.enabled,
        )
        for rule in rules
    ]


@router.post("/bonus-rules", response_model=BonusRuleOut)
def create_subscription_bonus_rule(
    payload: BonusRuleBase,
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> BonusRuleOut:
    rule = create_bonus_rule(db, payload)
    return BonusRuleOut(
        id=rule.id,
        plan_id=rule.plan_id,
        rule_code=rule.rule_code,
        title=rule.title,
        condition=rule.condition,
        reward=rule.reward,
        enabled=rule.enabled,
    )


@router.patch("/bonus-rules/{rule_id}", response_model=BonusRuleOut)
def patch_subscription_bonus_rule(
    rule_id: int,
    payload: BonusRuleUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(admin_auth.verify_admin_token),
) -> BonusRuleOut:
    rule = db.get(BonusRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Bonus rule not found")
    updated = update_bonus_rule(db, rule=rule, payload=payload)
    return BonusRuleOut(
        id=updated.id,
        plan_id=updated.plan_id,
        rule_code=updated.rule_code,
        title=updated.title,
        condition=updated.condition,
        reward=updated.reward,
        enabled=updated.enabled,
    )


@router.get("/me", response_model=ClientSubscriptionOut)
def get_my_subscription(
    db: Session = Depends(get_db),
    token: dict = Depends(client_auth.verify_client_token),
) -> ClientSubscriptionOut:
    tenant_id = int(token.get("tenant_id") or DEFAULT_TENANT_ID)
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Missing client context")

    subscription = get_client_subscription(db, tenant_id=tenant_id, client_id=client_id)
    if not subscription:
        subscription = ensure_free_subscription(db, tenant_id=tenant_id, client_id=client_id)

    plan = db.get(SubscriptionPlan, subscription.plan_id)
    plan_out = _build_plan_out(db, plan) if plan else None
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
        plan=plan_out,
    )


@router.get("/me/benefits", response_model=SubscriptionBenefitsOut)
def get_my_subscription_benefits(
    db: Session = Depends(get_db),
    token: dict = Depends(client_auth.verify_client_token),
) -> SubscriptionBenefitsOut:
    tenant_id = int(token.get("tenant_id") or DEFAULT_TENANT_ID)
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Missing client context")

    subscription = get_client_subscription(db, tenant_id=tenant_id, client_id=client_id)
    if not subscription:
        subscription = ensure_free_subscription(db, tenant_id=tenant_id, client_id=client_id)

    plan = db.get(SubscriptionPlan, subscription.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    modules = _plan_modules(db, plan.id)
    all_modules = _modules_with_fallback(modules)
    enabled = [module for module in all_modules if module.enabled]
    disabled = [module for module in all_modules if not module.enabled]

    return SubscriptionBenefitsOut(plan=_build_plan_out(db, plan), modules=enabled, unavailable_modules=disabled)


@router.get("/me/gamification", response_model=GamificationSummary)
def get_my_gamification_summary(
    db: Session = Depends(get_db),
    token: dict = Depends(client_auth.verify_client_token),
) -> GamificationSummary:
    tenant_id = int(token.get("tenant_id") or DEFAULT_TENANT_ID)
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Missing client context")

    subscription = get_client_subscription(db, tenant_id=tenant_id, client_id=client_id)
    if not subscription:
        subscription = ensure_free_subscription(db, tenant_id=tenant_id, client_id=client_id)

    plan = db.get(SubscriptionPlan, subscription.plan_id)
    plan_code = plan.code if plan else "FREE"
    return get_client_rewards_summary(db, tenant_id=tenant_id, client_id=client_id, plan_code=plan_code)


__all__ = ["router"]
