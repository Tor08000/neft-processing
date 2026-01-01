from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.subscriptions_v1 import (
    BonusRule,
    ClientSubscription,
    RoleEntitlement,
    SubscriptionModuleCode,
    SubscriptionPlan,
    SubscriptionPlanModule,
    SubscriptionStatus,
)
from app.schemas.subscriptions import (
    BonusRuleBase,
    BonusRuleUpdate,
    RoleEntitlementBase,
    SubscriptionPlanCreate,
    SubscriptionPlanModuleBase,
    SubscriptionPlanUpdate,
)

DEFAULT_TENANT_ID = 1
FREE_PLAN_CODES = {"FREE_BASE", "FREE"}
DEFAULT_FREE_PLAN_CODE = "FREE_BASE"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_free_plan(db: Session) -> SubscriptionPlan | None:
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == DEFAULT_FREE_PLAN_CODE).one_or_none()
    if plan:
        return plan
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "FREE").one_or_none()


def ensure_free_subscription(db: Session, *, tenant_id: int, client_id: str) -> ClientSubscription:
    existing = (
        db.query(ClientSubscription)
        .filter(ClientSubscription.tenant_id == tenant_id, ClientSubscription.client_id == client_id)
        .order_by(ClientSubscription.created_at.desc())
        .first()
    )
    if existing:
        return existing

    plan = get_free_plan(db)
    if plan is None:
        plan = SubscriptionPlan(
            code=DEFAULT_FREE_PLAN_CODE,
            title="FREE Base",
            description="Базовая бесплатная подписка",
            is_active=True,
            billing_period_months=0,
            price_cents=0,
            discount_percent=0,
            bonus_multiplier_override=None,
            currency="RUB",
        )
        db.add(plan)
        db.flush()

        base_modules = {
            SubscriptionModuleCode.FUEL_CORE: {"enabled": True, "tier": "free", "limits": {"cards_max": 5}},
            SubscriptionModuleCode.MARKETPLACE: {
                "enabled": True,
                "tier": "free",
                "limits": {"marketplace_discount_percent": 0},
            },
            SubscriptionModuleCode.EXPLAIN: {
                "enabled": True,
                "tier": "basic",
                "limits": {"explain_depth": 1, "explain_diff": False, "what_if": "off"},
            },
            SubscriptionModuleCode.ANALYTICS: {
                "enabled": True,
                "tier": "basic",
                "limits": {"exports_per_month": 1},
            },
            SubscriptionModuleCode.BONUSES: {
                "enabled": True,
                "tier": "preview",
                "limits": {"preview_only": True, "bonus_multiplier": 0},
            },
        }

        for module_code in SubscriptionModuleCode:
            config = base_modules.get(module_code, {"enabled": False, "tier": "off", "limits": {}})
            db.add(
                SubscriptionPlanModule(
                    plan_id=plan.id,
                    module_code=module_code,
                    enabled=config["enabled"],
                    tier=config["tier"],
                    limits=config["limits"],
                )
            )

    subscription = ClientSubscription(
        tenant_id=tenant_id,
        client_id=client_id,
        plan_id=plan.id,
        status=SubscriptionStatus.FREE,
        start_at=_now(),
        auto_renew=False,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def get_client_subscription(db: Session, *, tenant_id: int, client_id: str) -> ClientSubscription | None:
    return (
        db.query(ClientSubscription)
        .filter(ClientSubscription.tenant_id == tenant_id, ClientSubscription.client_id == client_id)
        .order_by(ClientSubscription.created_at.desc())
        .first()
    )


def assign_plan_to_client(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    plan_id: str,
    duration_months: int | None,
    auto_renew: bool,
) -> ClientSubscription:
    plan = db.get(SubscriptionPlan, plan_id)
    if plan is None:
        raise ValueError("Plan not found")

    now = _now()
    end_at = None
    if duration_months:
        end_at = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        month = end_at.month - 1 + duration_months
        year = end_at.year + month // 12
        month = month % 12 + 1
        end_at = end_at.replace(year=year, month=month)

    status = SubscriptionStatus.FREE if plan.code in FREE_PLAN_CODES else SubscriptionStatus.ACTIVE

    subscription = ClientSubscription(
        tenant_id=tenant_id,
        client_id=client_id,
        plan_id=plan.id,
        status=status,
        start_at=now,
        end_at=end_at,
        auto_renew=auto_renew,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def list_plans(db: Session, *, active_only: bool = False) -> list[SubscriptionPlan]:
    query = db.query(SubscriptionPlan)
    if active_only:
        query = query.filter(SubscriptionPlan.is_active.is_(True))
    return query.order_by(SubscriptionPlan.created_at.desc()).all()


def get_plan(db: Session, *, plan_id: str) -> SubscriptionPlan | None:
    return db.get(SubscriptionPlan, plan_id)


def create_plan(db: Session, payload: SubscriptionPlanCreate) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        code=payload.code,
        title=payload.title,
        description=payload.description,
        is_active=payload.is_active,
        billing_period_months=payload.billing_period_months,
        price_cents=payload.price_cents,
        discount_percent=payload.discount_percent,
        bonus_multiplier_override=payload.bonus_multiplier_override,
        currency=payload.currency,
    )
    db.add(plan)
    db.flush()

    if payload.modules:
        for module in payload.modules:
            db.add(
                SubscriptionPlanModule(
                    plan_id=plan.id,
                    module_code=module.module_code,
                    enabled=module.enabled,
                    tier=module.tier,
                    limits=module.limits,
                )
            )

    db.commit()
    db.refresh(plan)
    return plan


def update_plan(db: Session, *, plan: SubscriptionPlan, payload: SubscriptionPlanUpdate) -> SubscriptionPlan:
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(plan, key, value)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def update_plan_modules(
    db: Session,
    *,
    plan_id: str,
    modules: Iterable[SubscriptionPlanModuleBase],
) -> list[SubscriptionPlanModule]:
    existing = db.query(SubscriptionPlanModule).filter(SubscriptionPlanModule.plan_id == plan_id).all()
    existing_map = {item.module_code: item for item in existing}
    incoming_codes = {item.module_code for item in modules}

    for item in existing:
        if item.module_code not in incoming_codes:
            db.delete(item)

    for module in modules:
        current = existing_map.get(module.module_code)
        if current:
            current.enabled = module.enabled
            current.tier = module.tier
            current.limits = module.limits
        else:
            db.add(
                SubscriptionPlanModule(
                    plan_id=plan_id,
                    module_code=module.module_code,
                    enabled=module.enabled,
                    tier=module.tier,
                    limits=module.limits,
                )
            )

    db.commit()
    return db.query(SubscriptionPlanModule).filter(SubscriptionPlanModule.plan_id == plan_id).all()


def update_role_entitlements(
    db: Session,
    *,
    plan_id: str,
    roles: Iterable[RoleEntitlementBase],
) -> list[RoleEntitlement]:
    db.query(RoleEntitlement).filter(RoleEntitlement.plan_id == plan_id).delete()
    for role in roles:
        db.add(
            RoleEntitlement(
                plan_id=plan_id,
                role_code=role.role_code,
                entitlements=role.entitlements,
            )
        )
    db.commit()
    return db.query(RoleEntitlement).filter(RoleEntitlement.plan_id == plan_id).all()


def compute_entitlements(db: Session, *, plan_id: str, role_code: str) -> dict:
    record = (
        db.query(RoleEntitlement)
        .filter(RoleEntitlement.plan_id == plan_id, RoleEntitlement.role_code == role_code)
        .one_or_none()
    )
    return record.entitlements if record and record.entitlements else {}


def list_bonus_rules(db: Session, *, plan_id: str | None = None) -> list[BonusRule]:
    query = db.query(BonusRule)
    if plan_id:
        query = query.filter(BonusRule.plan_id == plan_id)
    return query.order_by(BonusRule.created_at.desc()).all()


def create_bonus_rule(db: Session, payload: BonusRuleBase) -> BonusRule:
    rule = BonusRule(
        plan_id=payload.plan_id,
        rule_code=payload.rule_code,
        title=payload.title,
        condition=payload.condition,
        reward=payload.reward,
        enabled=payload.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_bonus_rule(db: Session, *, rule: BonusRule, payload: BonusRuleUpdate) -> BonusRule:
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(rule, key, value)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


__all__ = [
    "DEFAULT_TENANT_ID",
    "assign_plan_to_client",
    "compute_entitlements",
    "create_bonus_rule",
    "create_plan",
    "ensure_free_subscription",
    "get_client_subscription",
    "get_free_plan",
    "get_plan",
    "list_bonus_rules",
    "list_plans",
    "update_bonus_rule",
    "update_plan",
    "update_plan_modules",
    "update_role_entitlements",
]
