from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.fleet_intelligence_actions import FIActionEffectLabel, FIInsight
from app.services.fleet_intelligence.control import defaults


def build_auto_resolution_hint(
    *,
    effect_label: FIActionEffectLabel | None,
    confidence: float | None,
    threshold: float = defaults.AUTO_RESOLUTION_CONFIDENCE_THRESHOLD,
) -> dict[str, Any] | None:
    if effect_label == FIActionEffectLabel.IMPROVED and confidence is not None and confidence >= threshold:
        return {
            "code": "SUGGEST_CLOSE_INSIGHT",
            "message": "Эффект устойчиво улучшился — можно закрыть инсайт.",
            "suggested_action": "CLOSE_INSIGHT",
        }
    if effect_label == FIActionEffectLabel.NO_CHANGE:
        return {
            "code": "SUGGEST_AMPLIFY_ACTION",
            "message": "Нет изменений — усилить действие или выбрать другую меру.",
        }
    return None


def confidence_status(
    confidence: float | None,
    *,
    high_threshold: float = defaults.CONFIDENCE_STATUS_HIGH,
    medium_threshold: float = defaults.CONFIDENCE_STATUS_MEDIUM,
) -> str | None:
    if confidence is None:
        return None
    if confidence >= high_threshold:
        return "HIGH"
    if confidence >= medium_threshold:
        return "MEDIUM"
    return "LOW"


def build_confidence_recommendation(
    confidence: float | None,
    *,
    min_after_decay: float = defaults.CONFIDENCE_MIN_AFTER_DECAY,
) -> str | None:
    if confidence is None:
        return None
    if confidence < min_after_decay:
        return "Действие больше не эффективно."
    return None


def build_insight_aging(
    insight: FIInsight,
    *,
    effect_label: FIActionEffectLabel | None,
    threshold_days: int = defaults.INSIGHT_ESCALATION_NO_CHANGE_DAYS,
) -> dict[str, Any] | None:
    if not insight.created_at:
        return None
    now = datetime.now(timezone.utc)
    created_at = insight.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    days_open = max((now - created_at).days, 0)
    needs_escalation = effect_label == FIActionEffectLabel.NO_CHANGE and days_open >= threshold_days
    if not needs_escalation:
        return {"days_open": days_open, "needs_escalation": False}
    return {
        "days_open": days_open,
        "needs_escalation": True,
        "reason": "insight_no_effect_no_change",
        "escalation_target": "OPS",
    }


__all__ = [
    "build_auto_resolution_hint",
    "build_confidence_recommendation",
    "build_insight_aging",
    "confidence_status",
]
