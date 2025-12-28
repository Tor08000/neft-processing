from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.fuel import FuelTransactionStatus
from app.models.legal_graph import LegalNodeType
from app.schemas.admin.unified_explain import (
    UnifiedExplainIds,
    UnifiedExplainResponse,
    UnifiedExplainResult,
    UnifiedExplainSubject,
    UnifiedExplainView,
)
from app.services.explain import formatters, sources
from app.services.explain.errors import UnifiedExplainNotFound, UnifiedExplainValidationError
from app.services.explain.snapshot import build_snapshot_payload, persist_snapshot
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
        limits_section=sections.get("limits"),
        money_section=sections.get("money"),
        documents_section=sections.get("documents"),
        driver_id=subject.driver_id,
    )

    response_payload = UnifiedExplainResponse(
        subject=subject,
        result=result,
        sections=selected_sections,
        ids=ids,
        recommendations=recommendations,
    )

    if snapshot and tenant_id is not None:
        snapshot_payload = build_snapshot_payload(response_payload.model_dump(mode="json"))
        snapshot_row = persist_snapshot(
            db,
            tenant_id=tenant_id,
            subject_type=subject.type,
            subject_id=subject.id,
            payload=snapshot_payload.snapshot_json,
        )
        response_payload.ids.snapshot_id = str(snapshot_row.id)
        response_payload.ids.snapshot_hash = snapshot_payload.snapshot_hash
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
            primary_reason=_primary_reason_from_fuel(tx),
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
        result = UnifiedExplainResult(status=order.status.value, primary_reason=None, decline_code=None)

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

        invoice_id = sources.find_invoice_id_for_order(db, order_id=str(order.id))
        if invoice_id:
            ids.invoice_id = invoice_id
            documents_section, document_ids = sources.build_documents_section(db, invoice_id=invoice_id)
            if documents_section:
                sections["documents"] = documents_section
                ids.document_ids = document_ids
            money_section = sources.build_money_section_for_invoice(db, invoice_id=invoice_id)
            if money_section:
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
        result = UnifiedExplainResult(status=invoice.status.value, primary_reason=None, decline_code=None)

        money_section = sources.build_money_section_for_invoice(db, invoice_id=str(invoice.id))
        if money_section:
            sections["money"] = money_section

        documents_section, document_ids = sources.build_documents_section(db, invoice_id=str(invoice.id))
        if documents_section:
            sections["documents"] = documents_section
            ids.document_ids = document_ids
        ids.invoice_id = str(invoice.id)

        return subject, result, sections, ids, None

    raise UnifiedExplainValidationError("explain_subject_missing")


def _primary_reason_from_fuel(tx: Any) -> str | None:
    if tx.status == FuelTransactionStatus.REVIEW_REQUIRED:
        return "RISK_REVIEW"
    if tx.decline_code:
        if str(tx.decline_code).startswith("LIMIT"):
            return "LIMIT_EXCEEDED"
        if str(tx.decline_code).startswith("RISK"):
            return "RISK_BLOCK"
    meta = tx.meta or {}
    if meta.get("limit_explain"):
        return "LIMIT_EXCEEDED"
    if meta.get("risk_explain"):
        return "RISK_BLOCK"
    return None


__all__ = ["build_unified_explain"]
