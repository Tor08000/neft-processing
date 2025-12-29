from __future__ import annotations

from collections import OrderedDict
from typing import Any, Iterable

from app.models.unified_explain import PrimaryReason
from app.schemas.admin.unified_explain import UnifiedExplainView
from app.services.explain.recommendations import (
    PRIMARY_REASON_RECOMMENDATIONS,
    RECOMMENDATION_SECTION_REQUIREMENTS,
    RECOMMENDATION_TEMPLATES,
)


FLEET_PRIORITY = [
    "executive_summary",
    "fleet_insight",
    "fleet_control",
    "decision_choice",
    "fuel_insight",
    "fleet_intelligence",
    "fleet_trends",
    "logistics",
    "navigator",
    "risk",
    "limits",
    "money",
    "crm",
    "documents",
    "graph",
]
ACCOUNTANT_PRIORITY = [
    "executive_summary",
    "money",
    "limits",
    "crm",
    "documents",
    "risk",
    "logistics",
    "navigator",
    "graph",
    "fleet_insight",
    "fleet_control",
    "decision_choice",
    "fuel_insight",
    "fleet_intelligence",
    "fleet_trends",
]
FULL_PRIORITY = [
    "executive_summary",
    "fleet_insight",
    "fleet_control",
    "decision_choice",
    "fuel_insight",
    "fleet_intelligence",
    "fleet_trends",
    "limits",
    "risk",
    "logistics",
    "navigator",
    "money",
    "crm",
    "documents",
    "graph",
]


def select_sections(sections: dict[str, Any], *, view: UnifiedExplainView) -> dict[str, Any]:
    priority = _priority_for_view(view)
    ordered = OrderedDict()
    for key in priority:
        if key in sections:
            ordered[key] = sections[key]
    return dict(ordered)


def build_recommendations(
    *,
    view: UnifiedExplainView,
    status: str,
    primary_reason: str | None,
    risk_section: dict[str, Any] | None,
    logistics_section: dict[str, Any] | None,
    navigator_section: dict[str, Any] | None,
    limits_section: dict[str, Any] | None,
    money_section: dict[str, Any] | None,
    documents_section: dict[str, Any] | None,
    driver_id: str | None,
) -> list[str]:
    available_sections = {
        name
        for name, section in {
            "risk": risk_section,
            "logistics": logistics_section,
            "limits": limits_section,
            "money": money_section,
            "documents": documents_section,
            "navigator": navigator_section,
        }.items()
        if section
    }

    if not primary_reason:
        return []
    try:
        reason = PrimaryReason(primary_reason)
    except ValueError:
        return []

    codes = PRIMARY_REASON_RECOMMENDATIONS.get(reason, [])
    recommendations: list[str] = []
    for code in codes:
        required_sections = RECOMMENDATION_SECTION_REQUIREMENTS.get(code, set())
        if required_sections and not (available_sections & required_sections):
            continue
        message = RECOMMENDATION_TEMPLATES.get(code)
        if message:
            recommendations.append(message)
    return _dedupe(recommendations)


def _priority_for_view(view: UnifiedExplainView) -> list[str]:
    if view == UnifiedExplainView.FLEET:
        return FLEET_PRIORITY
    if view == UnifiedExplainView.ACCOUNTANT:
        return ACCOUNTANT_PRIORITY
    return FULL_PRIORITY


def _dedupe(items: Iterable[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


__all__ = ["build_recommendations", "select_sections"]
