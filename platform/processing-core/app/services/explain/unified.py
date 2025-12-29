from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.fuel import FuelTransactionStatus
from app.models.legal_graph import LegalNodeType
from app.models.unified_explain import PrimaryReason
from app.schemas.admin.unified_explain import (
    UnifiedExplainIds,
    UnifiedExplainResponse,
    UnifiedExplainResult,
    UnifiedExplainSubject,
    UnifiedExplainView,
)
from app.services.explain import formatters, sources
from app.services.explain.errors import UnifiedExplainNotFound, UnifiedExplainValidationError
from app.services.explain.actions import build_actions
from app.services.explain.escalation import (
    ESCALATION_MAP,
    audit_primary_reason_assigned,
    audit_primary_reason_escalated,
    audit_sla_expired,
    build_escalation,
)
from app.services.explain.priority import PRIMARY_REASON_PRIORITY, ensure_primary_reason_consistency
from app.services.explain.snapshot import build_snapshot_payload, persist_snapshot
from app.services.explain.sla import SLAClock, SLA_DEFINITIONS, build_sla
from app.services.audit_service import AuditService
from app.services.money_flow.states import MoneyFlowType


STATUS_MAP = {
    FuelTransactionStatus.AUTHORIZED: "AUTHORIZED",
    FuelTransactionStatus.REVIEW_REQUIRED: "REVIEW",
    FuelTransactionStatus.DECLINED: "DECLINED",
    FuelTransactionStatus.SETTLED: "SETTLED",
    FuelTransactionStatus.REVERSED: "REVERSED",
}


def build_unified_explain(
    db: Session,
    *,
    fuel_tx_id: str | None = None,
    order_id: str | None = None,
    invoice_id: str | None = None,
    view: UnifiedExplainView = UnifiedExplainView.FULL,
    depth: int = 3,
    snapshot: bool = False,
) -> UnifiedExplainResponse:
    subject, result, sections, ids, tenant_id = _build_payload(
        db,
        fuel_tx_id=fuel_tx_id,
        order_id=order_id,
        invoice_id=invoice_id,
        depth=depth,
    )
    selected_sections = formatters.select_sections(sections, view=view)
    recommendations = formatters.build_recommendations(
        view=view,
        status=result.status,
        primary_reason=result.primary_reason,
        risk_section=sections.get("risk"),
        logistics_section=sections.get("logistics"),
        navigator_section=sections.get("navigator"),
        limits_section=sections.get("limits"),
        money_section=sections.get("money"),
        documents_section=sections.get("documents"),
        driver_id=subject.driver_id,
    )
    _apply_human_readable_sections(
        selected_sections,
        view=view,
        recommendations=recommendations,
        decline_code=result.decline_code,
    )

    actions = build_actions(result.primary_reason)
    started_at = _parse_started_at(subject.ts)
    sla = build_sla(result.primary_reason, started_at=started_at)
    escalation = build_escalation(result.primary_reason)

    response_payload = UnifiedExplainResponse(
        primary_reason=result.primary_reason,
        secondary_reasons=result.secondary_reasons,
        subject=subject,
        result=result,
        sections=selected_sections,
        ids=ids,
        recommendations=recommendations,
        actions=actions,
        sla=sla,
        escalation=escalation,
    )

    if snapshot and tenant_id is not None:
        snapshot_payload = build_snapshot_payload(response_payload.model_dump(mode="json"))
        persisted_snapshot = persist_snapshot(
            db,
            tenant_id=tenant_id,
            subject_type=subject.type,
            subject_id=subject.id,
            payload=snapshot_payload.snapshot_json,
        )
        response_payload.ids.snapshot_id = str(persisted_snapshot.snapshot.id)
        response_payload.ids.snapshot_hash = snapshot_payload.snapshot_hash
        if persisted_snapshot.created:
            _audit_primary_reason(
                db,
                tenant_id=tenant_id,
                subject=subject,
                primary_reason=result.primary_reason,
                escalation_target=escalation.target if escalation else None,
                sla=sla,
            )
        db.commit()

    return response_payload


def _build_payload(
    db: Session,
    *,
    fuel_tx_id: str | None,
    order_id: str | None,
    invoice_id: str | None,
    depth: int,
) -> tuple[UnifiedExplainSubject, UnifiedExplainResult, dict[str, Any], UnifiedExplainIds, int | None]:
    ids = UnifiedExplainIds(
        risk_decision_id=None,
        ledger_transaction_id=None,
        invoice_id=None,
        document_ids=[],
        money_flow_event_ids=[],
        snapshot_id=None,
        snapshot_hash=None,
    )
    sections: dict[str, Any] = {}

    if fuel_tx_id:
        tx = sources.get_fuel_tx(db, fuel_tx_id=fuel_tx_id)
        if not tx:
            raise UnifiedExplainNotFound("fuel_tx_not_found")

        subject = UnifiedExplainSubject(
            type="FUEL_TX",
            id=str(tx.id),
            ts=tx.occurred_at.isoformat(),
            client_id=tx.client_id,
            vehicle_id=str(tx.vehicle_id) if tx.vehicle_id else None,
            driver_id=str(tx.driver_id) if tx.driver_id else None,
        )
        result = UnifiedExplainResult(
            status=STATUS_MAP.get(tx.status, tx.status.value),
            decline_code=tx.decline_code,
        )

        ids.risk_decision_id = str(tx.risk_decision_id) if tx.risk_decision_id else None
        ids.ledger_transaction_id = str(tx.ledger_transaction_id) if tx.ledger_transaction_id else None

        limit_section = sources.build_limits_section(tx)
        if limit_section:
            sections["limits"] = limit_section

        risk_section = sources.build_risk_section(db, tx=tx)
        if risk_section:
            sections["risk"] = risk_section

        fleet_intelligence_section = sources.build_fleet_intelligence_section(
            db,
            tenant_id=tx.tenant_id,
            client_id=tx.client_id,
            driver_id=str(tx.driver_id) if tx.driver_id else None,
            vehicle_id=str(tx.vehicle_id) if tx.vehicle_id else None,
            station_id=str(tx.station_id) if tx.station_id else None,
            window_days=7,
        )
        if fleet_intelligence_section:
            sections["fleet_intelligence"] = fleet_intelligence_section

        fleet_control_section = sources.build_fleet_control_section(
            db,
            tenant_id=tx.tenant_id,
            client_id=tx.client_id,
            driver_id=str(tx.driver_id) if tx.driver_id else None,
            vehicle_id=str(tx.vehicle_id) if tx.vehicle_id else None,
            station_id=str(tx.station_id) if tx.station_id else None,
        )
        if fleet_control_section:
            sections["fleet_control"] = fleet_control_section

        fleet_insight_section = sources.build_fleet_insight_section(
            db,
            tenant_id=tx.tenant_id,
            client_id=tx.client_id,
            driver_id=str(tx.driver_id) if tx.driver_id else None,
            vehicle_id=str(tx.vehicle_id) if tx.vehicle_id else None,
            station_id=str(tx.station_id) if tx.station_id else None,
            window_days=7,
        )
        if fleet_insight_section:
            sections["fleet_insight"] = fleet_insight_section

        fleet_trends_section = sources.build_fleet_trends_section(
            db,
            tenant_id=tx.tenant_id,
            driver_id=str(tx.driver_id) if tx.driver_id else None,
            vehicle_id=str(tx.vehicle_id) if tx.vehicle_id else None,
            station_id=str(tx.station_id) if tx.station_id else None,
        )
        if fleet_trends_section:
            sections["fleet_trends"] = fleet_trends_section

        link = sources.get_fuel_link(db, fuel_tx_id=str(tx.id))
        if link:
            sections["logistics"] = sources.build_logistics_section(
                db,
                order_id=str(link.order_id),
                occurred_at=tx.occurred_at,
                client_id=tx.client_id,
                vehicle_id=str(tx.vehicle_id) if tx.vehicle_id else None,
                driver_id=str(tx.driver_id) if tx.driver_id else None,
                link=link,
            )
            navigator_section = sources.build_navigator_section(
                db,
                order_id=str(link.order_id),
                route_id=str(link.route_id) if link.route_id else None,
            )
            if navigator_section:
                sections["navigator"] = navigator_section

        money_section = sources.build_money_section_for_fuel(db, fuel_tx_id=str(tx.id))
        if money_section:
            money_summary = sources.build_money_summary_for_fuel(db, fuel_tx_id=str(tx.id))
            if money_summary:
                money_section.update(money_summary)
            sections["money"] = money_section
            ids.money_flow_event_ids = sources.load_money_flow_event_ids(
                db, flow_type=MoneyFlowType.FUEL_TX, flow_ref_id=str(tx.id)
            )

        invoice_id = sources.find_invoice_id_for_fuel(db, fuel_tx_id=str(tx.id))
        if invoice_id:
            ids.invoice_id = invoice_id
            documents_section, document_ids = sources.build_documents_section(db, invoice_id=invoice_id)
            if documents_section:
                sections["documents"] = documents_section
                ids.document_ids = document_ids

        graph_section = sources.build_graph_section(
            db,
            tenant_id=tx.tenant_id,
            node_type=LegalNodeType.FUEL_TRANSACTION,
            ref_id=str(tx.id),
            depth=depth,
        )
        if graph_section:
            sections["graph"] = graph_section

        _apply_primary_reasons(
            result,
            sections=sections,
            decline_code=tx.decline_code,
        )
        crm_section = sources.build_crm_section(db, tenant_id=tx.tenant_id, client_id=tx.client_id)
        if crm_section:
            sections["crm"] = crm_section
        return subject, result, sections, ids, tx.tenant_id

    if order_id:
        order = sources.get_order(db, order_id=order_id)
        if not order:
            raise UnifiedExplainNotFound("order_not_found")

        subject = UnifiedExplainSubject(
            type="LOGISTICS_ORDER",
            id=str(order.id),
            ts=order.created_at.isoformat(),
            client_id=order.client_id,
            vehicle_id=str(order.vehicle_id) if order.vehicle_id else None,
            driver_id=str(order.driver_id) if order.driver_id else None,
        )
        result = UnifiedExplainResult(status=order.status.value, decline_code=None)

        link = sources.get_order_link(db, order_id=str(order.id))
        logistics_section = sources.build_logistics_section(
            db,
            order_id=str(order.id),
            occurred_at=order.actual_start_at or order.planned_start_at,
            client_id=order.client_id,
            vehicle_id=str(order.vehicle_id) if order.vehicle_id else None,
            driver_id=str(order.driver_id) if order.driver_id else None,
            link=link,
        )
        if logistics_section:
            sections["logistics"] = logistics_section

        navigator_section = sources.build_navigator_section(
            db,
            order_id=str(order.id),
            route_id=str(link.route_id) if link and link.route_id else None,
        )
        if navigator_section:
            sections["navigator"] = navigator_section

        fleet_insight_section = sources.build_fleet_insight_section(
            db,
            tenant_id=order.tenant_id,
            client_id=order.client_id,
            driver_id=str(order.driver_id) if order.driver_id else None,
            vehicle_id=str(order.vehicle_id) if order.vehicle_id else None,
            station_id=None,
            window_days=7,
        )
        if fleet_insight_section:
            sections["fleet_insight"] = fleet_insight_section

        invoice_id = sources.find_invoice_id_for_order(db, order_id=str(order.id))
        if invoice_id:
            ids.invoice_id = invoice_id
            documents_section, document_ids = sources.build_documents_section(db, invoice_id=invoice_id)
            if documents_section:
                sections["documents"] = documents_section
                ids.document_ids = document_ids
            money_section = sources.build_money_section_for_invoice(db, invoice_id=invoice_id)
            if money_section:
                money_summary = sources.build_money_summary_for_invoice(db, invoice_id=invoice_id)
                if money_summary:
                    money_section.update(money_summary)
                sections["money"] = money_section

        graph_section = sources.build_graph_section(
            db,
            tenant_id=order.tenant_id,
            node_type=LegalNodeType.LOGISTICS_ORDER,
            ref_id=str(order.id),
            depth=depth,
        )
        if graph_section:
            sections["graph"] = graph_section

        _apply_primary_reasons(
            result,
            sections=sections,
            decline_code=None,
        )
        crm_section = sources.build_crm_section(db, tenant_id=order.tenant_id, client_id=order.client_id)
        if crm_section:
            sections["crm"] = crm_section
        return subject, result, sections, ids, order.tenant_id

    if invoice_id:
        invoice = sources.get_invoice(db, invoice_id=invoice_id)
        if not invoice:
            raise UnifiedExplainNotFound("invoice_not_found")

        subject = UnifiedExplainSubject(
            type="INVOICE",
            id=str(invoice.id),
            ts=invoice.created_at.isoformat(),
            client_id=invoice.client_id,
            vehicle_id=None,
            driver_id=None,
        )
        result = UnifiedExplainResult(status=invoice.status.value, decline_code=None)

        money_section = sources.build_money_section_for_invoice(db, invoice_id=str(invoice.id))
        if money_section:
            money_summary = sources.build_money_summary_for_invoice(db, invoice_id=str(invoice.id))
            if money_summary:
                money_section.update(money_summary)
            sections["money"] = money_section

        documents_section, document_ids = sources.build_documents_section(db, invoice_id=str(invoice.id))
        if documents_section:
            sections["documents"] = documents_section
            ids.document_ids = document_ids
        ids.invoice_id = str(invoice.id)

        fleet_insight_section = sources.build_fleet_insight_section(
            db,
            tenant_id=None,
            client_id=invoice.client_id,
            driver_id=None,
            vehicle_id=None,
            station_id=None,
            window_days=7,
        )
        if fleet_insight_section:
            sections["fleet_insight"] = fleet_insight_section

        _apply_primary_reasons(
            result,
            sections=sections,
            decline_code=None,
        )
        crm_section = sources.build_crm_section(db, tenant_id=None, client_id=invoice.client_id)
        if crm_section:
            sections["crm"] = crm_section
        return subject, result, sections, ids, None

    raise UnifiedExplainValidationError("explain_subject_missing")


def _apply_primary_reasons(
    result: UnifiedExplainResult,
    *,
    sections: dict[str, Any],
    decline_code: str | None,
) -> None:
    detected_reasons = _collect_reasons(sections=sections, decline_code=decline_code)
    primary_reason, secondary_reasons = resolve_primary_reasons(detected_reasons)
    result.primary_reason = ensure_primary_reason_consistency(primary_reason, sections=sections)
    result.secondary_reasons = secondary_reasons


def _apply_human_readable_sections(
    sections: dict[str, Any],
    *,
    view: UnifiedExplainView,
    recommendations: list[str],
    decline_code: str | None,
) -> None:
    if view == UnifiedExplainView.FLEET:
        logistics = sections.get("logistics")
        if isinstance(logistics, dict):
            where = logistics.get("where", {})
            threshold = logistics.get("threshold", {})
            stop_payload = where.get("stop") if isinstance(where, dict) else None
            stop_label = None
            if isinstance(stop_payload, dict):
                stop_label = stop_payload.get("name") or stop_payload.get("id")
            distance_km = where.get("distance_km") if isinstance(where, dict) else None
            time_delta = logistics.get("time_delta_minutes")
            where_parts = []
            if stop_label:
                where_parts.append(f"остановка {stop_label}")
            if distance_km is not None:
                where_parts.append(f"{distance_km} км")
            if time_delta is not None:
                where_parts.append(f"{time_delta} мин")
            where_text = ", ".join(where_parts) if where_parts else "—"

            rule_parts = []
            if isinstance(threshold, dict):
                if threshold.get("max_deviation_km") is not None:
                    rule_parts.append(f"порог {threshold['max_deviation_km']} км")
                if threshold.get("stop_radius_m") is not None:
                    rule_parts.append(f"радиус {threshold['stop_radius_m']} м")
                if threshold.get("allowed_window_min") is not None:
                    rule_parts.append(f"окно {threshold['allowed_window_min']} мин")
            rule_text = ", ".join(rule_parts) if rule_parts else "—"

            logistics["summary"] = {
                "where": where_text,
                "rule": rule_text,
                "recommendation": recommendations[0] if recommendations else None,
            }
    if view == UnifiedExplainView.ACCOUNTANT:
        limits = sections.get("limits")
        if isinstance(limits, dict):
            limit_info = limits.get("limit") if isinstance(limits.get("limit"), dict) else {}
            limits["summary"] = {
                "limit_value": limits.get("limit_value"),
                "period": limit_info.get("period") if isinstance(limit_info, dict) else None,
                "reason": "Превышен лимит" if decline_code and str(decline_code).startswith("LIMIT_") else None,
                "recommendation": recommendations[0] if recommendations else None,
            }
        fleet_insight = sections.get("fleet_insight")
        if isinstance(fleet_insight, dict):
            primary = fleet_insight.get("primary_insight")
            if isinstance(primary, dict):
                fleet_insight["primary_insight"] = {
                    "summary": primary.get("summary"),
                    "actions": primary.get("actions"),
                }
            fleet_insight.pop("secondary_insights", None)


def _collect_reasons(
    *,
    sections: dict[str, Any],
    decline_code: str | None,
) -> set[PrimaryReason]:
    reasons: set[PrimaryReason] = set()

    if _has_limit_reason(decline_code=decline_code, sections=sections):
        reasons.add(PrimaryReason.LIMIT)
    if _has_risk_reason(sections=sections):
        reasons.add(PrimaryReason.RISK)
    if _has_logistics_reason(sections=sections):
        reasons.add(PrimaryReason.LOGISTICS)
    if _has_money_reason(sections=sections):
        reasons.add(PrimaryReason.MONEY)
    if _has_policy_reason(decline_code=decline_code, sections=sections):
        reasons.add(PrimaryReason.POLICY)

    return reasons


def resolve_primary_reasons(
    detected_reasons: set[PrimaryReason],
) -> tuple[PrimaryReason, list[PrimaryReason]]:
    primary_reason = PrimaryReason.UNKNOWN
    for reason in PRIMARY_REASON_PRIORITY:
        if reason in detected_reasons:
            primary_reason = reason
            break
    if primary_reason == PrimaryReason.UNKNOWN:
        return primary_reason, []

    secondary_reasons = [
        reason for reason in PRIMARY_REASON_PRIORITY if reason in detected_reasons and reason != primary_reason
    ]
    return primary_reason, secondary_reasons


def _parse_started_at(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    normalized = timestamp.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _audit_primary_reason(
    db: Session,
    *,
    tenant_id: int | None,
    subject: UnifiedExplainSubject,
    primary_reason: PrimaryReason,
    escalation_target: str | None,
    sla: SLAClock | None,
) -> None:
    if primary_reason not in SLA_DEFINITIONS and primary_reason not in ESCALATION_MAP:
        return

    audit_service = AuditService(db)
    entity_type = "unified_explain"
    entity_id = subject.id
    audit_primary_reason_assigned(
        audit_service,
        entity_type=entity_type,
        entity_id=entity_id,
        tenant_id=tenant_id,
        primary_reason=primary_reason,
        target=escalation_target,
    )
    if escalation_target:
        audit_primary_reason_escalated(
            audit_service,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
            primary_reason=primary_reason,
            target=escalation_target,
        )
    audit_sla_expired(
        audit_service,
        entity_type=entity_type,
        entity_id=entity_id,
        tenant_id=tenant_id,
        primary_reason=primary_reason,
        target=escalation_target,
        sla=sla,
    )


def _has_limit_reason(*, decline_code: str | None, sections: dict[str, Any]) -> bool:
    if decline_code and str(decline_code).startswith("LIMIT_"):
        return True
    return bool(sections.get("limits"))


def _has_risk_reason(*, sections: dict[str, Any]) -> bool:
    risk_section = sections.get("risk")
    if not isinstance(risk_section, dict):
        return False
    decision = risk_section.get("decision")
    if not decision:
        return False
    decision_value = str(decision).upper()
    return decision_value in {"BLOCK", "REVIEW", "REVIEW_REQUIRED", "ALLOW_WITH_REVIEW"}


def _has_logistics_reason(*, sections: dict[str, Any]) -> bool:
    logistics_section = sections.get("logistics")
    if not isinstance(logistics_section, dict):
        return False
    deviation_events = logistics_section.get("deviation_events", [])
    if isinstance(deviation_events, list) and deviation_events:
        return True
    risk_signals = logistics_section.get("risk_signals", [])
    if isinstance(risk_signals, list):
        for signal in risk_signals:
            if str(signal.get("signal_type", "")).upper() in {"FUEL_OFF_ROUTE", "ETA_ANOMALY"}:
                return True
    return False


def _has_money_reason(*, sections: dict[str, Any]) -> bool:
    money_section = sections.get("money")
    if not isinstance(money_section, dict):
        return False
    flow_state = money_section.get("flow_state")
    if flow_state and str(flow_state).upper() in {"FAILED", "BLOCKED"}:
        return True
    invariants = money_section.get("invariants")
    if isinstance(invariants, dict) and invariants.get("passed") is False:
        return True
    return False


def _has_policy_reason(*, decline_code: str | None, sections: dict[str, Any]) -> bool:
    if decline_code and str(decline_code).upper() == "ACCESS_DENIED":
        return True
    policy_section = sections.get("policy")
    return bool(policy_section)


__all__ = ["build_unified_explain", "resolve_primary_reasons"]
