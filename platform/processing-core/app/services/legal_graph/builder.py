from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import Date
from sqlalchemy.orm import Session

from app.models.accounting_export_batch import AccountingExportBatch, AccountingExportType
from app.models.billing_period import BillingPeriod
from app.models.documents import ClosingPackage, Document, DocumentFile
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice
from app.models.refund_request import RefundRequest
from app.models.legal_graph import LegalEdgeType, LegalNodeType
from app.models.risk_decision import RiskDecision
from app.models.risk_types import RiskSubjectType
from app.services.audit_service import RequestContext
from app.services.legal_graph.registry import LegalGraphRegistry

@dataclass(frozen=True)
class GraphContext:
    tenant_id: int
    request_ctx: RequestContext | None = None


class LegalGraphBuilder:
    def __init__(self, db: Session, *, context: GraphContext) -> None:
        self.db = db
        self.context = context
        self.registry = LegalGraphRegistry(db, request_ctx=context.request_ctx)

    def ensure_document_graph(self, document: Document) -> None:
        node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.DOCUMENT,
            ref_id=str(document.id),
            ref_table="documents",
            hash_value=document.document_hash,
        ).node

        invoice_node = None
        if document.source_entity_type == "invoice" and document.source_entity_id:
            invoice_node = self.registry.get_or_create_node(
                tenant_id=self.context.tenant_id,
                node_type=LegalNodeType.INVOICE,
                ref_id=str(document.source_entity_id),
                ref_table="invoices",
            ).node
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=node.id,
                dst_node_id=invoice_node.id,
                edge_type=LegalEdgeType.GENERATED_FROM,
            )
            invoice = (
                self.db.query(Invoice)
                .filter(Invoice.id == document.source_entity_id)
                .one_or_none()
            )
            if invoice and invoice.billing_period_id:
                self._link_document_to_period(node.id, str(invoice.billing_period_id))

        period_id = self._resolve_billing_period_for_document(document)
        if period_id:
            self._link_document_to_period(node.id, period_id)

        self._link_document_replacement(document, node_id=node.id)
        self._link_document_files(document, node_id=node.id)

        risk_decision = self._latest_risk_decision(subject_type=RiskSubjectType.DOCUMENT, subject_id=str(document.id))
        if risk_decision:
            decision_node = self.registry.get_or_create_node(
                tenant_id=self.context.tenant_id,
                node_type=LegalNodeType.RISK_DECISION,
                ref_id=str(risk_decision.id),
                ref_table="risk_decisions",
            ).node
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=node.id,
                dst_node_id=decision_node.id,
                edge_type=LegalEdgeType.SIGNED_BY,
            )

        if invoice_node:
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=node.id,
                dst_node_id=invoice_node.id,
                edge_type=LegalEdgeType.CONFIRMS,
            )

    def ensure_document_ack_graph(self, *, document: Document, acknowledgement, meta: dict | None = None) -> None:
        document_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.DOCUMENT,
            ref_id=str(document.id),
            ref_table="documents",
            hash_value=document.document_hash,
        ).node
        ack_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.DOCUMENT_ACK,
            ref_id=str(acknowledgement.id),
            ref_table="document_acknowledgements",
            meta=meta,
        ).node
        self.registry.link(
            tenant_id=self.context.tenant_id,
            src_node_id=document_node.id,
            dst_node_id=ack_node.id,
            edge_type=LegalEdgeType.SIGNED_BY,
            meta=meta,
        )

    def ensure_closing_package_graph(
        self,
        package: ClosingPackage,
        documents: dict[str, Document] | None = None,
    ) -> None:
        package_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.CLOSING_PACKAGE,
            ref_id=str(package.id),
            ref_table="closing_packages",
        ).node

        document_ids = [
            package.invoice_document_id,
            package.act_document_id,
            package.recon_document_id,
        ]
        doc_list = list(documents.values()) if documents else self._load_documents(document_ids)
        for doc in doc_list:
            doc_node = self.registry.get_or_create_node(
                tenant_id=self.context.tenant_id,
                node_type=LegalNodeType.DOCUMENT,
                ref_id=str(doc.id),
                ref_table="documents",
                hash_value=doc.document_hash,
            ).node
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=package_node.id,
                dst_node_id=doc_node.id,
                edge_type=LegalEdgeType.INCLUDES,
            )

        period_id = self._resolve_billing_period_for_package(package, doc_list)
        if period_id:
            period_node = self.registry.get_or_create_node(
                tenant_id=self.context.tenant_id,
                node_type=LegalNodeType.BILLING_PERIOD,
                ref_id=str(period_id),
                ref_table="billing_periods",
            ).node
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=package_node.id,
                dst_node_id=period_node.id,
                edge_type=LegalEdgeType.CLOSES,
            )

    def ensure_settlement_allocation_graph(
        self,
        allocation: InvoiceSettlementAllocation,
        *,
        invoice: Invoice,
        source: InvoicePayment | CreditNote | RefundRequest | None,
    ) -> None:
        allocation_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.SETTLEMENT_ALLOCATION,
            ref_id=str(allocation.id),
            ref_table="invoice_settlement_allocations",
        ).node

        invoice_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.INVOICE,
            ref_id=str(invoice.id),
            ref_table="invoices",
        ).node
        self.registry.link(
            tenant_id=self.context.tenant_id,
            src_node_id=allocation_node.id,
            dst_node_id=invoice_node.id,
            edge_type=LegalEdgeType.ALLOCATES,
            meta={
                "allocation_type": allocation.source_type.value,
                "amount": allocation.amount,
                "currency": allocation.currency,
                "applied_at": allocation.applied_at.isoformat() if allocation.applied_at else None,
            },
        )

        if allocation.settlement_period_id:
            period_node = self.registry.get_or_create_node(
                tenant_id=self.context.tenant_id,
                node_type=LegalNodeType.BILLING_PERIOD,
                ref_id=str(allocation.settlement_period_id),
                ref_table="billing_periods",
            ).node
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=allocation_node.id,
                dst_node_id=period_node.id,
                edge_type=LegalEdgeType.RELATES_TO,
            )

        if source:
            source_type = {
                SettlementSourceType.PAYMENT: LegalNodeType.PAYMENT,
                SettlementSourceType.CREDIT_NOTE: LegalNodeType.CREDIT_NOTE,
                SettlementSourceType.REFUND: LegalNodeType.REFUND,
            }[allocation.source_type]
            source_node = self.registry.get_or_create_node(
                tenant_id=self.context.tenant_id,
                node_type=source_type,
                ref_id=str(source.id),
                ref_table=source.__tablename__,
            ).node
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=allocation_node.id,
                dst_node_id=source_node.id,
                edge_type=LegalEdgeType.GENERATED_FROM,
            )

            if allocation.source_type == SettlementSourceType.PAYMENT:
                self.registry.link(
                    tenant_id=self.context.tenant_id,
                    src_node_id=source_node.id,
                    dst_node_id=invoice_node.id,
                    edge_type=LegalEdgeType.SETTLES,
                )

    def ensure_accounting_export_graph(self, batch: AccountingExportBatch) -> None:
        export_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.ACCOUNTING_EXPORT_BATCH,
            ref_id=str(batch.id),
            ref_table="accounting_export_batches",
        ).node

        if batch.billing_period_id:
            period_node = self.registry.get_or_create_node(
                tenant_id=self.context.tenant_id,
                node_type=LegalNodeType.BILLING_PERIOD,
                ref_id=str(batch.billing_period_id),
                ref_table="billing_periods",
            ).node
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=export_node.id,
                dst_node_id=period_node.id,
                edge_type=LegalEdgeType.EXPORTS,
            )

        if batch.export_type == AccountingExportType.CHARGES:
            invoices = (
                self.db.query(Invoice)
                .filter(Invoice.billing_period_id == str(batch.billing_period_id))
                .all()
            )
            for invoice in invoices:
                invoice_node = self.registry.get_or_create_node(
                    tenant_id=self.context.tenant_id,
                    node_type=LegalNodeType.INVOICE,
                    ref_id=str(invoice.id),
                    ref_table="invoices",
                ).node
                self.registry.link(
                    tenant_id=self.context.tenant_id,
                    src_node_id=export_node.id,
                    dst_node_id=invoice_node.id,
                    edge_type=LegalEdgeType.EXPORTS,
                )
        elif batch.export_type == AccountingExportType.SETTLEMENT:
            allocations = (
                self.db.query(InvoiceSettlementAllocation)
                .filter(InvoiceSettlementAllocation.settlement_period_id == str(batch.billing_period_id))
                .all()
            )
            for allocation in allocations:
                allocation_node = self.registry.get_or_create_node(
                    tenant_id=self.context.tenant_id,
                    node_type=LegalNodeType.SETTLEMENT_ALLOCATION,
                    ref_id=str(allocation.id),
                    ref_table="invoice_settlement_allocations",
                ).node
                self.registry.link(
                    tenant_id=self.context.tenant_id,
                    src_node_id=export_node.id,
                    dst_node_id=allocation_node.id,
                    edge_type=LegalEdgeType.EXPORTS,
                )

    def ensure_invoice_graph(self, invoice: Invoice) -> None:
        invoice_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.INVOICE,
            ref_id=str(invoice.id),
            ref_table="invoices",
        ).node
        if invoice.billing_period_id:
            period_node = self.registry.get_or_create_node(
                tenant_id=self.context.tenant_id,
                node_type=LegalNodeType.BILLING_PERIOD,
                ref_id=str(invoice.billing_period_id),
                ref_table="billing_periods",
            ).node
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=invoice_node.id,
                dst_node_id=period_node.id,
                edge_type=LegalEdgeType.RELATES_TO,
            )

    def ensure_risk_decision_graph(self, risk_decision: RiskDecision) -> dict[str, Any]:
        decision_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.RISK_DECISION,
            ref_id=str(risk_decision.id),
            ref_table="risk_decisions",
        ).node

        target_type = {
            RiskSubjectType.DOCUMENT: LegalNodeType.DOCUMENT,
            RiskSubjectType.INVOICE: LegalNodeType.INVOICE,
            RiskSubjectType.PAYMENT: LegalNodeType.PAYMENT,
            RiskSubjectType.EXPORT: LegalNodeType.ACCOUNTING_EXPORT_BATCH,
        }.get(risk_decision.subject_type)
        if not target_type:
            return {
                "status": "unsupported_subject",
                "risk_decision_node_id": str(decision_node.id),
                "subject_type": risk_decision.subject_type.value,
                "subject_id": str(risk_decision.subject_id),
            }

        target_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=target_type,
            ref_id=str(risk_decision.subject_id),
        ).node
        edge = self.registry.link(
            tenant_id=self.context.tenant_id,
            src_node_id=target_node.id,
            dst_node_id=decision_node.id,
            edge_type=LegalEdgeType.GATED_BY_RISK,
            meta={
                "outcome": risk_decision.outcome.value,
                "score": risk_decision.score,
                "policy_id": risk_decision.policy_id,
                "threshold_set_id": risk_decision.threshold_set_id,
            },
        )
        return {
            "status": "written",
            "risk_decision_node_id": str(decision_node.id),
            "target_node_id": str(target_node.id),
            "edge_id": str(edge.edge.id),
            "edge_type": LegalEdgeType.GATED_BY_RISK.value,
            "target_type": target_type.value,
            "target_ref_id": str(risk_decision.subject_id),
        }

    def _resolve_billing_period_for_document(self, document: Document) -> str | None:
        invoice = (
            self.db.query(Invoice)
            .filter(Invoice.client_id == document.client_id)
            .filter(Invoice.period_from == document.period_from)
            .filter(Invoice.period_to == document.period_to)
            .order_by(Invoice.issued_at.desc())
            .first()
        )
        if invoice and invoice.billing_period_id:
            return str(invoice.billing_period_id)
        period = (
            self.db.query(BillingPeriod)
            .filter(BillingPeriod.start_at.cast(Date) == document.period_from)
            .filter(BillingPeriod.end_at.cast(Date) == document.period_to)
            .order_by(BillingPeriod.start_at.desc())
            .first()
        )
        if period:
            return str(period.id)
        return None

    def _resolve_billing_period_for_package(
        self,
        package: ClosingPackage,
        documents: Iterable[Document],
    ) -> str | None:
        invoice_doc = next((doc for doc in documents if doc.document_type.value == "INVOICE"), None)
        if invoice_doc and invoice_doc.source_entity_id:
            invoice = (
                self.db.query(Invoice)
                .filter(Invoice.id == invoice_doc.source_entity_id)
                .one_or_none()
            )
            if invoice and invoice.billing_period_id:
                return str(invoice.billing_period_id)
        invoice = (
            self.db.query(Invoice)
            .filter(Invoice.client_id == package.client_id)
            .filter(Invoice.period_from == package.period_from)
            .filter(Invoice.period_to == package.period_to)
            .order_by(Invoice.issued_at.desc())
            .first()
        )
        if invoice and invoice.billing_period_id:
            return str(invoice.billing_period_id)
        return None

    def _link_document_to_period(self, document_node_id: str, period_id: str) -> None:
        period_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.BILLING_PERIOD,
            ref_id=str(period_id),
            ref_table="billing_periods",
        ).node
        self.registry.link(
            tenant_id=self.context.tenant_id,
            src_node_id=document_node_id,
            dst_node_id=period_node.id,
            edge_type=LegalEdgeType.GENERATED_FROM,
        )

    def _link_document_replacement(self, document: Document, *, node_id: str) -> None:
        if not document.version or document.version <= 1:
            return
        previous = (
            self.db.query(Document)
            .filter(Document.tenant_id == document.tenant_id)
            .filter(Document.client_id == document.client_id)
            .filter(Document.document_type == document.document_type)
            .filter(Document.period_from == document.period_from)
            .filter(Document.period_to == document.period_to)
            .filter(Document.version == document.version - 1)
            .one_or_none()
        )
        if not previous:
            return
        previous_node = self.registry.get_or_create_node(
            tenant_id=self.context.tenant_id,
            node_type=LegalNodeType.DOCUMENT,
            ref_id=str(previous.id),
            ref_table="documents",
            hash_value=previous.document_hash,
        ).node
        self.registry.link(
            tenant_id=self.context.tenant_id,
            src_node_id=node_id,
            dst_node_id=previous_node.id,
            edge_type=LegalEdgeType.REPLACES,
        )

    def _link_document_files(self, document: Document, *, node_id: str) -> None:
        files = (
            self.db.query(DocumentFile)
            .filter(DocumentFile.document_id == document.id)
            .all()
        )
        for file in files:
            file_node = self.registry.get_or_create_node(
                tenant_id=self.context.tenant_id,
                node_type=LegalNodeType.DOCUMENT_FILE,
                ref_id=str(file.id),
                ref_table="document_files",
                hash_value=file.sha256,
            ).node
            self.registry.link(
                tenant_id=self.context.tenant_id,
                src_node_id=node_id,
                dst_node_id=file_node.id,
                edge_type=LegalEdgeType.INCLUDES,
            )

    def _latest_risk_decision(self, *, subject_type: RiskSubjectType, subject_id: str) -> RiskDecision | None:
        return (
            self.db.query(RiskDecision)
            .filter(RiskDecision.subject_type == subject_type)
            .filter(RiskDecision.subject_id == subject_id)
            .order_by(RiskDecision.decided_at.desc())
            .first()
        )

    def _load_documents(self, document_ids: Iterable[str | None]) -> list[Document]:
        ids = [doc_id for doc_id in document_ids if doc_id]
        if not ids:
            return []
        return self.db.query(Document).filter(Document.id.in_(ids)).all()


__all__ = ["GraphContext", "LegalGraphBuilder"]
