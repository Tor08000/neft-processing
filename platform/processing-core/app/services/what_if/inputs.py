from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.decision_memory import DecisionMemoryEntityType
from app.schemas.admin.unified_explain import UnifiedExplainView
from app.services.explain.unified import build_unified_explain
from app.services.fleet_intelligence.control import confidence as control_confidence
from app.services.fleet_intelligence.control import repository as control_repository


@dataclass(frozen=True)
class WhatIfSubject:
    type: str
    id: str


@dataclass(frozen=True)
class WhatIfContext:
    subject: WhatIfSubject
    primary_reason: str | None
    tenant_id: int | None
    client_id: str | None
    entity_type: str | None
    entity_id: str | None
    window_days: int | None
    suggested_actions: list[str]
    decision_choice: dict | None
    confidence_map: dict[str, float]

    @property
    def memory_entity_type(self) -> DecisionMemoryEntityType | None:
        if not self.entity_type:
            return None
        try:
            return DecisionMemoryEntityType(self.entity_type)
        except ValueError:
            return None


SUBJECT_TYPES = {
    "INSIGHT",
    "FUEL_TX",
    "ORDER",
    "INVOICE",
}


def build_context(db: Session, *, subject: WhatIfSubject) -> WhatIfContext:
    if subject.type == "INSIGHT":
        return _build_from_insight(db, subject=subject)
    if subject.type == "FUEL_TX":
        return _build_from_explain(db, subject=subject, fuel_tx_id=subject.id)
    if subject.type == "ORDER":
        return _build_from_explain(db, subject=subject, order_id=subject.id)
    if subject.type == "INVOICE":
        return _build_from_explain(db, subject=subject, invoice_id=subject.id)
    raise ValueError("unsupported_subject_type")


def _build_from_insight(db: Session, *, subject: WhatIfSubject) -> WhatIfContext:
    insight = control_repository.get_insight(db, insight_id=subject.id)
    if not insight:
        raise ValueError("insight_not_found")
    suggested = control_repository.list_suggested_actions(db, insight_id=subject.id)
    confidence_map = {
        action.action_code.value: control_confidence.compute_action_confidence(
            db,
            action_code=action.action_code,
        )
        for action in suggested
    }
    return WhatIfContext(
        subject=subject,
        primary_reason=str(insight.primary_reason.value) if insight.primary_reason else None,
        tenant_id=insight.tenant_id,
        client_id=insight.client_id,
        entity_type=insight.entity_type.value,
        entity_id=str(insight.entity_id),
        window_days=insight.window_days,
        suggested_actions=[action.action_code.value for action in suggested],
        decision_choice=None,
        confidence_map=confidence_map,
    )


def _build_from_explain(
    db: Session,
    *,
    subject: WhatIfSubject,
    fuel_tx_id: str | None = None,
    order_id: str | None = None,
    invoice_id: str | None = None,
) -> WhatIfContext:
    explain = build_unified_explain(
        db,
        fuel_tx_id=fuel_tx_id,
        order_id=order_id,
        invoice_id=invoice_id,
        view=UnifiedExplainView.FULL,
    )
    sections = explain.sections if isinstance(explain.sections, dict) else {}
    fleet_control = sections.get("fleet_control") if isinstance(sections.get("fleet_control"), dict) else None
    decision_choice = sections.get("decision_choice") if isinstance(sections.get("decision_choice"), dict) else None
    active_insight = fleet_control.get("active_insight") if isinstance(fleet_control, dict) else None
    entity_type = None
    entity_id = None
    window_days = None
    if isinstance(active_insight, dict):
        entity_type = active_insight.get("entity_type")
        entity_id = active_insight.get("entity_id")
        window_days = active_insight.get("window_days")
    suggested_actions: list[str] = []
    confidence_map: dict[str, float] = {}
    if isinstance(fleet_control, dict):
        suggested = fleet_control.get("suggested_actions")
        if isinstance(suggested, list):
            for item in suggested:
                if not isinstance(item, dict):
                    continue
                action_code = item.get("action_code")
                if action_code:
                    suggested_actions.append(str(action_code))
                    confidence = item.get("confidence")
                    if isinstance(confidence, (int, float)):
                        confidence_map[str(action_code)] = float(confidence)
    return WhatIfContext(
        subject=subject,
        primary_reason=str(explain.primary_reason.value) if explain.primary_reason else None,
        tenant_id=None,
        client_id=explain.subject.client_id,
        entity_type=str(entity_type) if entity_type else None,
        entity_id=str(entity_id) if entity_id else None,
        window_days=int(window_days) if window_days else None,
        suggested_actions=suggested_actions,
        decision_choice=decision_choice,
        confidence_map=confidence_map,
    )


__all__ = ["SUBJECT_TYPES", "WhatIfContext", "WhatIfSubject", "build_context"]
