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
from app.services.fleet_intelligence.policies import registry as policy_registry


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
    bundle = policy_registry.match_bundle_for_insight(insight)
    if bundle:
        return _actions_from_bundle(insight, bundle=bundle)
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


def _actions_from_bundle(insight: FIInsight, *, bundle) -> list[FISuggestedAction]:
    actions: list[FISuggestedAction] = []
    for index, step in enumerate(bundle.steps):
        payload = {
            **step.action_payload,
            "bundle_code": bundle.bundle_code,
            "step_index": index,
            "params": step.params,
        }
        actions.append(
            FISuggestedAction(
                insight_id=insight.id,
                action_code=step.action_code,
                target_system=step.target_system,
                payload=payload,
                status=FISuggestedActionStatus.PROPOSED,
            )
        )
    return actions


__all__ = ["suggest_actions_for_insight", "INSIGHT_ACTION_MAP", "SuggestedActionTemplate"]
