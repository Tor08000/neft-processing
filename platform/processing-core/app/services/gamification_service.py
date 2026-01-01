from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.subscriptions_v1 import ClientBonusState, SubscriptionPlan, SubscriptionPlanModule
from app.schemas.subscriptions import GamificationSummary


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _module_preview(db: Session, plan_id: str) -> list[dict]:
    modules = (
        db.query(SubscriptionPlanModule)
        .filter(SubscriptionPlanModule.plan_id == plan_id)
        .order_by(SubscriptionPlanModule.module_code.asc())
        .all()
    )
    return [
        {
            "module_code": module.module_code.value,
            "enabled": module.enabled,
            "tier": module.tier,
            "limits": module.limits or {},
        }
        for module in modules
    ]


def compute_preview_for_free(db: Session) -> dict | None:
    upgrade_plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.code != "FREE", SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.price_cents.desc())
        .first()
    )
    if not upgrade_plan:
        return None
    return {
        "plan_id": upgrade_plan.id,
        "plan_code": upgrade_plan.code,
        "plan_title": upgrade_plan.title,
        "modules": _module_preview(db, upgrade_plan.id),
    }


def get_client_rewards_summary(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    plan_code: str,
) -> GamificationSummary:
    state = (
        db.query(ClientBonusState)
        .filter(ClientBonusState.tenant_id == tenant_id, ClientBonusState.client_id == client_id)
        .one_or_none()
    )

    bonuses = state.active_bonuses if state and state.active_bonuses else []
    streaks = state.streaks if state and state.streaks else []
    achievements = state.achievements if state and state.achievements else []

    preview = compute_preview_for_free(db) if plan_code == "FREE" else None

    return GamificationSummary(
        as_of=_now(),
        plan_code=plan_code,
        bonuses=bonuses,
        streaks=streaks,
        achievements=achievements,
        preview=preview,
    )


__all__ = ["compute_preview_for_free", "get_client_rewards_summary"]
