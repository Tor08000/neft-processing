from __future__ import annotations

from typing import Any

from app.models.fleet_intelligence_actions import FIInsight
from app.services.fleet_intelligence.policies import bundles


def match_bundle_for_insight(insight: FIInsight) -> bundles.ScenarioBundle | None:
    for bundle in bundles.BUNDLES:
        for trigger in bundle.triggers:
            if insight.insight_type == trigger.insight_type and insight.severity == trigger.severity:
                return bundle
    return None


def serialize_bundle(bundle: bundles.ScenarioBundle) -> dict[str, Any]:
    return {
        "bundle_code": bundle.bundle_code,
        "title": bundle.title,
        "duration_days": bundle.duration_days,
        "steps": [
            {"action": step.action_code.value, "params": step.params}
            for step in bundle.steps
        ],
        "success_criteria": list(bundle.success_criteria),
    }


__all__ = ["match_bundle_for_insight", "serialize_bundle"]
