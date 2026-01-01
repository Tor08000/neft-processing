from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.subscriptions_v1 import Achievement, Bonus, ClientProgress, Streak, SubscriptionPlan, SubscriptionPlanModule
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


def _plan_matches(plan_codes: list[str] | None, plan_code: str) -> bool:
    if not plan_codes:
        return True
    return plan_code in plan_codes


def _load_available_achievements(db: Session, plan_code: str) -> list[Achievement]:
    query = db.query(Achievement).filter(Achievement.is_active.is_(True))
    return [item for item in query.order_by(Achievement.created_at.desc()).all() if _plan_matches(item.plan_codes, plan_code)]


def _load_available_streaks(db: Session, plan_code: str) -> list[Streak]:
    query = db.query(Streak).filter(Streak.is_active.is_(True))
    return [item for item in query.order_by(Streak.created_at.desc()).all() if _plan_matches(item.plan_codes, plan_code)]


def _load_available_bonuses(db: Session, plan_code: str) -> list[Bonus]:
    query = db.query(Bonus).filter(Bonus.is_active.is_(True))
    return [item for item in query.order_by(Bonus.created_at.desc()).all() if _plan_matches(item.plan_codes, plan_code)]


def get_client_rewards_summary(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    plan_code: str,
) -> GamificationSummary:
    state = (
        db.query(ClientProgress)
        .filter(ClientProgress.tenant_id == tenant_id, ClientProgress.client_id == client_id)
        .one_or_none()
    )

    bonuses = state.bonuses if state and state.bonuses else []
    streaks = state.streaks if state and state.streaks else []
    achievements = state.achievements if state and state.achievements else []

    available = {
        "achievements": [
            {"code": item.code, "title": item.title, "description": item.description, "hidden": item.is_hidden}
            for item in _load_available_achievements(db, plan_code)
        ],
        "streaks": [
            {"code": item.code, "title": item.title, "description": item.description}
            for item in _load_available_streaks(db, plan_code)
        ],
        "bonuses": [
            {"code": item.code, "title": item.title, "description": item.description, "reward": item.reward}
            for item in _load_available_bonuses(db, plan_code)
        ],
    }

    preview = compute_preview_for_free(db) if plan_code == "FREE" else None
    if plan_code == "FREE":
        preview = {**(preview or {}), "available": available}
    else:
        bonuses = bonuses or available["bonuses"]
        streaks = streaks or available["streaks"]
        achievements = achievements or available["achievements"]

    return GamificationSummary(
        as_of=_now(),
        plan_code=plan_code,
        bonuses=bonuses,
        streaks=streaks,
        achievements=achievements,
        preview=preview,
    )


__all__ = ["compute_preview_for_free", "get_client_rewards_summary"]
