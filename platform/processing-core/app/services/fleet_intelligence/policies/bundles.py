from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.fleet_intelligence_actions import (
    FIActionCode,
    FIActionTargetSystem,
    FIInsightSeverity,
    FIInsightType,
)


@dataclass(frozen=True)
class ScenarioTrigger:
    insight_type: FIInsightType
    severity: FIInsightSeverity


@dataclass(frozen=True)
class ScenarioStep:
    action_code: FIActionCode
    target_system: FIActionTargetSystem
    action_payload: dict[str, Any]
    params: dict[str, Any]


@dataclass(frozen=True)
class ScenarioBundle:
    bundle_code: str
    title: str
    duration_days: int
    triggers: tuple[ScenarioTrigger, ...]
    steps: tuple[ScenarioStep, ...]
    success_criteria: tuple[dict[str, Any], ...]


DRIVER_RISK_HIGH_14D = ScenarioBundle(
    bundle_code="DRIVER_RISK_HIGH_14D",
    title="Снижение риска водителя на 14 дней",
    duration_days=14,
    triggers=(
        ScenarioTrigger(
            insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
            severity=FIInsightSeverity.HIGH,
        ),
    ),
    steps=(
        ScenarioStep(
            action_code=FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
            target_system=FIActionTargetSystem.CRM,
            action_payload={"feature_flag": "RISK_BLOCKING_ENABLED", "enabled": True},
            params={"window": "23:00-06:00"},
        ),
        ScenarioStep(
            action_code=FIActionCode.SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL,
            target_system=FIActionTargetSystem.LOGISTICS,
            action_payload={},
            params={"required": True},
        ),
        ScenarioStep(
            action_code=FIActionCode.SUGGEST_LIMIT_PROFILE_SAFE,
            target_system=FIActionTargetSystem.CRM,
            action_payload={"limit_profile_id": "safe"},
            params={"priority": "HIGH"},
        ),
    ),
    success_criteria=(
        {"metric": "driver_score", "delta": -10},
    ),
)


BUNDLES = (DRIVER_RISK_HIGH_14D,)

__all__ = ["ScenarioBundle", "ScenarioStep", "ScenarioTrigger", "BUNDLES"]
