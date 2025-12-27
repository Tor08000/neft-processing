from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.accounting_export_batch import AccountingExportBatch, AccountingExportState
from app.models.billing_period import BillingPeriod
from app.models.documents import ClosingPackage, ClosingPackageStatus, Document, DocumentStatus, DocumentType
from app.models.legal_graph import LegalEdge, LegalEdgeType, LegalNode, LegalNodeType


@dataclass(frozen=True)
class CompletenessResult:
    ok: bool
    missing_nodes: list[dict]
    missing_edges: list[dict]
    blocking_reasons: list[str]


def check_billing_period_completeness(
    db: Session,
    *,
    tenant_id: int,
    period_id: str,
) -> CompletenessResult:
    missing_nodes: list[dict] = []
    missing_edges: list[dict] = []
    blocking_reasons: list[str] = []

    period = db.query(BillingPeriod).filter(BillingPeriod.id == period_id).one_or_none()
    if not period:
        return CompletenessResult(
            ok=False,
            missing_nodes=[{"node_type": LegalNodeType.BILLING_PERIOD.value, "ref_id": period_id}],
            missing_edges=[],
            blocking_reasons=["billing_period_missing"],
        )

    period_node = _get_node(db, tenant_id, LegalNodeType.BILLING_PERIOD, str(period.id))
    if not period_node:
        missing_nodes.append({"node_type": LegalNodeType.BILLING_PERIOD.value, "ref_id": str(period.id)})

    period_from, period_to = _period_dates(period)
    documents = (
        db.query(Document)
        .filter(Document.period_from == period_from)
        .filter(Document.period_to == period_to)
        .all()
    )
    document_map = {doc.document_type: doc for doc in documents}

    for doc_type in (DocumentType.INVOICE, DocumentType.ACT, DocumentType.RECONCILIATION_ACT):
        doc = document_map.get(doc_type)
        if not doc:
            missing_nodes.append({"node_type": LegalNodeType.DOCUMENT.value, "document_type": doc_type.value})
            continue
        if doc.status not in {DocumentStatus.ACKNOWLEDGED, DocumentStatus.FINALIZED}:
            blocking_reasons.append(f"document_not_finalized:{doc_type.value}")
        if not _get_node(db, tenant_id, LegalNodeType.DOCUMENT, str(doc.id)):
            missing_nodes.append({"node_type": LegalNodeType.DOCUMENT.value, "ref_id": str(doc.id)})

    package = (
        db.query(ClosingPackage)
        .filter(ClosingPackage.period_from == period_from)
        .filter(ClosingPackage.period_to == period_to)
        .order_by(ClosingPackage.version.desc())
        .first()
    )
    if not package:
        missing_nodes.append({"node_type": LegalNodeType.CLOSING_PACKAGE.value})
    else:
        if package.status not in {ClosingPackageStatus.ACKNOWLEDGED, ClosingPackageStatus.FINALIZED}:
            blocking_reasons.append("closing_package_not_finalized")
        package_node = _get_node(db, tenant_id, LegalNodeType.CLOSING_PACKAGE, str(package.id))
        if not package_node:
            missing_nodes.append({"node_type": LegalNodeType.CLOSING_PACKAGE.value, "ref_id": str(package.id)})
        else:
            _check_closing_package_edges(
                db,
                tenant_id,
                package_node,
                document_map,
                period_node,
                missing_edges,
            )

    export_batches = (
        db.query(AccountingExportBatch)
        .filter(AccountingExportBatch.billing_period_id == str(period.id))
        .all()
    )
    if export_batches:
        confirmed = [batch for batch in export_batches if batch.state == AccountingExportState.CONFIRMED]
        if not confirmed:
            missing_nodes.append({"node_type": LegalNodeType.ACCOUNTING_EXPORT_BATCH.value, "status": "CONFIRMED"})
        elif period_node:
            for batch in confirmed:
                export_node = _get_node(db, tenant_id, LegalNodeType.ACCOUNTING_EXPORT_BATCH, str(batch.id))
                if not export_node:
                    missing_nodes.append(
                        {"node_type": LegalNodeType.ACCOUNTING_EXPORT_BATCH.value, "ref_id": str(batch.id)}
                    )
                    continue
                edge_exists = (
                    db.query(LegalEdge)
                    .filter(LegalEdge.tenant_id == tenant_id)
                    .filter(LegalEdge.edge_type == LegalEdgeType.CONFIRMS)
                    .filter(LegalEdge.src_node_id == export_node.id)
                    .filter(LegalEdge.dst_node_id == period_node.id)
                    .one_or_none()
                    is not None
                )
                if not edge_exists:
                    missing_edges.append(
                        {
                            "edge_type": LegalEdgeType.CONFIRMS.value,
                            "src": export_node.ref_id,
                            "dst": period_node.ref_id,
                        }
                    )

    ok = not missing_nodes and not missing_edges and not blocking_reasons
    return CompletenessResult(
        ok=ok,
        missing_nodes=missing_nodes,
        missing_edges=missing_edges,
        blocking_reasons=blocking_reasons,
    )


def _period_dates(period: BillingPeriod) -> tuple[date, date]:
    tz = ZoneInfo(period.tz)
    start_date = period.start_at.astimezone(tz).date()
    end_date = period.end_at.astimezone(tz).date()
    return start_date, end_date


def _get_node(db: Session, tenant_id: int, node_type: LegalNodeType, ref_id: str) -> LegalNode | None:
    return (
        db.query(LegalNode)
        .filter(LegalNode.tenant_id == tenant_id)
        .filter(LegalNode.node_type == node_type)
        .filter(LegalNode.ref_id == ref_id)
        .one_or_none()
    )


def _check_closing_package_edges(
    db: Session,
    tenant_id: int,
    package_node: LegalNode,
    document_map: dict[DocumentType, Document],
    period_node: LegalNode | None,
    missing_edges: list[dict],
) -> None:
    required_docs: Iterable[Document] = [
        doc
        for doc_type, doc in document_map.items()
        if doc_type in {DocumentType.INVOICE, DocumentType.ACT, DocumentType.RECONCILIATION_ACT}
    ]

    for doc in required_docs:
        doc_node = _get_node(db, tenant_id, LegalNodeType.DOCUMENT, str(doc.id))
        if not doc_node:
            continue
        edge_exists = (
            db.query(LegalEdge)
            .filter(LegalEdge.tenant_id == tenant_id)
            .filter(LegalEdge.edge_type == LegalEdgeType.INCLUDES)
            .filter(LegalEdge.src_node_id == package_node.id)
            .filter(LegalEdge.dst_node_id == doc_node.id)
            .one_or_none()
            is not None
        )
        if not edge_exists:
            missing_edges.append(
                {
                    "edge_type": LegalEdgeType.INCLUDES.value,
                    "src": package_node.ref_id,
                    "dst": doc_node.ref_id,
                }
            )

    if period_node:
        edge_exists = (
            db.query(LegalEdge)
            .filter(LegalEdge.tenant_id == tenant_id)
            .filter(LegalEdge.edge_type == LegalEdgeType.CLOSES)
            .filter(LegalEdge.src_node_id == package_node.id)
            .filter(LegalEdge.dst_node_id == period_node.id)
            .one_or_none()
            is not None
        )
        if not edge_exists:
            missing_edges.append(
                {
                    "edge_type": LegalEdgeType.CLOSES.value,
                    "src": package_node.ref_id,
                    "dst": period_node.ref_id,
                }
            )


__all__ = ["CompletenessResult", "check_billing_period_completeness"]
