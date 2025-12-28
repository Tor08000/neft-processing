from __future__ import annotations

from collections import OrderedDict
from typing import Any, Iterable

from app.schemas.admin.unified_explain import UnifiedExplainView


FLEET_PRIORITY = ["logistics", "navigator", "risk", "limits", "money", "documents", "graph"]
ACCOUNTANT_PRIORITY = ["money", "limits", "documents", "risk", "logistics", "navigator", "graph"]
FULL_PRIORITY = ["limits", "risk", "logistics", "navigator", "money", "documents", "graph"]


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
    limits_section: dict[str, Any] | None,
    money_section: dict[str, Any] | None,
    documents_section: dict[str, Any] | None,
    driver_id: str | None,
) -> list[str]:
    recommendations: list[str] = []
    if view == UnifiedExplainView.FLEET:
        if driver_id:
            recommendations.append("check driver")
        if logistics_section and logistics_section.get("deviation_events"):
            recommendations.append("check route deviation")
        if risk_section and risk_section.get("fraud_signals"):
            recommendations.append("station suspicious")
        if status in {"DECLINED", "REVIEW"} and primary_reason and primary_reason.startswith("RISK"):
            recommendations.append("requires override")
    elif view == UnifiedExplainView.ACCOUNTANT:
        if limits_section:
            recommendations.append("increase limit profile")
        if money_section and _money_has_invariants_failed(money_section):
            recommendations.append("billing replay compare")
        if documents_section and _documents_need_attention(documents_section.get("documents", [])):
            recommendations.append("apply contract")
        if status in {"DECLINED", "REVIEW"} and primary_reason:
            recommendations.append("check payment state")
    else:
        if limits_section:
            recommendations.append("limit profile check")
        if risk_section and risk_section.get("fraud_signals"):
            recommendations.append("review fraud signals")
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


def _money_has_invariants_failed(money_section: dict[str, Any]) -> bool:
    invariants = money_section.get("invariants")
    if isinstance(invariants, dict) and invariants.get("passed") is False:
        return True
    return False


def _documents_need_attention(documents: Iterable[dict[str, Any]]) -> bool:
    for doc in documents:
        status = doc.get("status")
        if status and status not in {"FINALIZED", "ACKNOWLEDGED"}:
            return True
    return False


__all__ = ["build_recommendations", "select_sections"]
