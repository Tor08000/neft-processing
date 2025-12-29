from __future__ import annotations

from dataclasses import dataclass

from app.models.fleet_intelligence_actions import (
    FIActionCode,
    FIActionTargetSystem,
    FIInsight,
    FIInsightSeverity,
    FISuggestedAction,
    FISuggestedActionStatus,
)


@dataclass(frozen=True)
class SuggestedActionTemplate:
    code: FIActionCode
    target_system: FIActionTargetSystem
    payload: dict


INSIGHT_ACTION_MAP: dict[str, list[SuggestedActionTemplate]] = {
    "DRIVER_BEHAVIOR_DEGRADING": [
        SuggestedActionTemplate(
            code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
            target_system=FIActionTargetSystem.CRM,
            payload={"feature_flag": "RISK_BLOCKING_ENABLED", "enabled": True},
        ),
        SuggestedActionTemplate(
            code=FIActionCode.SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL,
            target_system=FIActionTargetSystem.LOGISTICS,
            payload={},
        ),
    ],
    "STATION_TRUST_DEGRADING": [
        SuggestedActionTemplate(
            code=FIActionCode.SUGGEST_EXCLUDE_STATION_FROM_ROUTES,
            target_system=FIActionTargetSystem.LOGISTICS,
            payload={},
        ),
        SuggestedActionTemplate(
            code=FIActionCode.SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL,
            target_system=FIActionTargetSystem.LOGISTICS,
            payload={},
        ),
    ],
    "VEHICLE_EFFICIENCY_DEGRADING": [
        SuggestedActionTemplate(
            code=FIActionCode.SUGGEST_VEHICLE_DIAGNOSTIC,
            target_system=FIActionTargetSystem.OPS,
            payload={},
        ),
    ],
}


def suggest_actions_for_insight(insight: FIInsight) -> list[FISuggestedAction]:
    if insight.severity not in {FIInsightSeverity.HIGH, FIInsightSeverity.CRITICAL}:
        return []
    templates = INSIGHT_ACTION_MAP.get(insight.insight_type.value, [])
    return [
        FISuggestedAction(
            insight_id=insight.id,
            action_code=template.code,
            target_system=template.target_system,
            payload=template.payload,
            status=FISuggestedActionStatus.PROPOSED,
        )
        for template in templates
    ]


__all__ = ["suggest_actions_for_insight", "INSIGHT_ACTION_MAP", "SuggestedActionTemplate"]
