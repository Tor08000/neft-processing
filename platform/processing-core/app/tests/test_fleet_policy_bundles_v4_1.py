from uuid import uuid4

from app.models.fleet_intelligence_actions import (
    FIActionCode,
    FIInsight,
    FIInsightEntityType,
    FIInsightSeverity,
    FIInsightStatus,
    FIInsightType,
)
from app.models.unified_explain import PrimaryReason
from app.services.fleet_intelligence.control import policies as control_policies
from app.services.fleet_intelligence.policies import registry as policy_registry


def test_bundle_trigger_matched():
    insight = FIInsight(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id="driver-1",
        window_days=7,
        severity=FIInsightSeverity.HIGH,
        status=FIInsightStatus.OPEN,
        primary_reason=PrimaryReason.POLICY,
        summary="Driver risk",
    )
    bundle = policy_registry.match_bundle_for_insight(insight)
    assert bundle is not None
    assert bundle.bundle_code == "DRIVER_RISK_HIGH_14D"


def test_bundle_steps_mapped_into_suggested_actions():
    insight = FIInsight(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id="driver-1",
        window_days=7,
        severity=FIInsightSeverity.HIGH,
        status=FIInsightStatus.OPEN,
        primary_reason=PrimaryReason.POLICY,
        summary="Driver risk",
    )
    actions = control_policies.suggest_actions_for_insight(insight)
    assert [action.action_code for action in actions] == [
        FIActionCode.SUGGEST_RESTRICT_NIGHT_FUELING,
        FIActionCode.SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL,
        FIActionCode.SUGGEST_LIMIT_PROFILE_SAFE,
    ]
    assert actions[0].payload["bundle_code"] == "DRIVER_RISK_HIGH_14D"
    assert actions[0].payload["params"] == {"window": "23:00-06:00"}


def test_bundle_steps_are_deterministic():
    insight = FIInsight(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        insight_type=FIInsightType.DRIVER_BEHAVIOR_DEGRADING,
        entity_type=FIInsightEntityType.DRIVER,
        entity_id="driver-1",
        window_days=7,
        severity=FIInsightSeverity.HIGH,
        status=FIInsightStatus.OPEN,
        primary_reason=PrimaryReason.POLICY,
        summary="Driver risk",
    )
    actions = control_policies.suggest_actions_for_insight(insight)
    step_indexes = [action.payload["step_index"] for action in actions]
    assert step_indexes == [0, 1, 2]
