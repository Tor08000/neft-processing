from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.audit_log import AuditVisibility
from app.models.documents import (
    ClosingPackage,
    ClosingPackageStatus,
    Document,
    DocumentFile,
    DocumentFileType,
    DocumentStatus,
    DocumentType,
)
from app.models.finance import CreditNote, InvoicePayment
from app.models.invoice import Invoice
from app.services.audit_service import AuditService, RequestContext
from app.services.documents_generator import DocumentsGenerator
from app.services.documents_storage import DocumentsStorage


@dataclass(frozen=True)
class ClosingPackageResult:
    package: ClosingPackage
    documents: dict[DocumentType, Document]


class ClosingDocumentsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.generator = DocumentsGenerator()
        self.storage = DocumentsStorage()

    def generate_package(
        self,
        *,
        tenant_id: int,
        client_id: str,
        period_from: date,
        period_to: date,
        force_new_version: bool,
        actor: RequestContext,
    ) -> ClosingPackageResult:
        existing = self._latest_package(tenant_id, client_id, period_from, period_to)
        if existing and existing.status == ClosingPackageStatus.ISSUED and not force_new_version:
            docs = self._load_documents(existing)
            return ClosingPackageResult(package=existing, documents=docs)

        version = 1
        if existing:
            version = existing.version + 1

        invoice = self._resolve_invoice(client_id, period_from, period_to)
        invoice_id = str(invoice.id) if invoice else None

        document_map: dict[DocumentType, Document] = {}
        document_map[DocumentType.INVOICE] = self._create_document(
            tenant_id=tenant_id,
            client_id=client_id,
            period_from=period_from,
            period_to=period_to,
            document_type=DocumentType.INVOICE,
            version=version,
            status=DocumentStatus.ISSUED,
            actor=actor,
            source_entity_type="invoice",
            source_entity_id=invoice_id,
            number=invoice.number if invoice else None,
        )
        document_map[DocumentType.ACT] = self._create_document(
            tenant_id=tenant_id,
            client_id=client_id,
            period_from=period_from,
            period_to=period_to,
            document_type=DocumentType.ACT,
            version=version,
            status=DocumentStatus.ISSUED,
            actor=actor,
            source_entity_type="billing_period",
        )
        document_map[DocumentType.RECONCILIATION_ACT] = self._create_document(
            tenant_id=tenant_id,
            client_id=client_id,
            period_from=period_from,
            period_to=period_to,
            document_type=DocumentType.RECONCILIATION_ACT,
            version=version,
            status=DocumentStatus.ISSUED,
            actor=actor,
            source_entity_type="billing_period",
        )

        package = ClosingPackage(
            tenant_id=tenant_id,
            client_id=client_id,
            period_from=period_from,
            period_to=period_to,
            status=ClosingPackageStatus.ISSUED,
            version=version,
            invoice_document_id=document_map[DocumentType.INVOICE].id,
            act_document_id=document_map[DocumentType.ACT].id,
            recon_document_id=document_map[DocumentType.RECONCILIATION_ACT].id,
            created_at=datetime.now(timezone.utc),
            generated_at=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc),
        )
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)

        AuditService(self.db).audit(
            event_type="CLOSING_PACKAGE_ISSUED",
            entity_type="closing_package",
            entity_id=str(package.id),
            action="CREATE",
            visibility=AuditVisibility.PUBLIC,
            after={
                "version": package.version,
                "status": package.status.value,
                "document_ids": {
                    "invoice": str(document_map[DocumentType.INVOICE].id),
                    "act": str(document_map[DocumentType.ACT].id),
                    "reconciliation": str(document_map[DocumentType.RECONCILIATION_ACT].id),
                },
            },
            request_ctx=actor,
        )

        if force_new_version and existing:
            AuditService(self.db).audit(
                event_type="REGENERATION_FORCED",
                entity_type="closing_package",
                entity_id=str(package.id),
                action="CREATE",
                visibility=AuditVisibility.INTERNAL,
                after={"previous_id": str(existing.id), "version": package.version},
                request_ctx=actor,
            )

        return ClosingPackageResult(package=package, documents=document_map)

    def _latest_package(
        self, tenant_id: int, client_id: str, period_from: date, period_to: date
    ) -> ClosingPackage | None:
        return (
            self.db.query(ClosingPackage)
            .filter(ClosingPackage.tenant_id == tenant_id)
            .filter(ClosingPackage.client_id == client_id)
            .filter(ClosingPackage.period_from == period_from)
            .filter(ClosingPackage.period_to == period_to)
            .order_by(desc(ClosingPackage.version))
            .first()
        )

    def finalize_package(self, package: ClosingPackage, *, actor: RequestContext) -> ClosingPackage:
        if package.status == ClosingPackageStatus.FINALIZED:
            return package
        if package.status != ClosingPackageStatus.ACKNOWLEDGED:
            raise ValueError("closing_package_not_acknowledged")

        documents = self._load_documents(package)
        not_finalized = [
            document.document_type.value
            for document in documents.values()
            if document.status != DocumentStatus.FINALIZED
        ]
        if not_finalized:
            raise ValueError("documents_not_finalized")

        package.status = ClosingPackageStatus.FINALIZED
        self.db.commit()

        AuditService(self.db).audit(
            event_type="CLOSING_PACKAGE_FINALIZED",
            entity_type="closing_package",
            entity_id=str(package.id),
            action="UPDATE",
            visibility=AuditVisibility.PUBLIC,
            after={
                "status": package.status.value,
                "version": package.version,
                "document_ids": {
                    "invoice": str(package.invoice_document_id) if package.invoice_document_id else None,
                    "act": str(package.act_document_id) if package.act_document_id else None,
                    "reconciliation": str(package.recon_document_id) if package.recon_document_id else None,
                },
            },
            request_ctx=actor,
        )

        return package

    def _resolve_invoice(self, client_id: str, period_from: date, period_to: date) -> Invoice | None:
        return (
            self.db.query(Invoice)
            .filter(Invoice.client_id == client_id)
            .filter(Invoice.period_from == period_from)
            .filter(Invoice.period_to == period_to)
            .order_by(desc(Invoice.issued_at))
            .first()
        )

    def _create_document(
        self,
        *,
        tenant_id: int,
        client_id: str,
        period_from: date,
        period_to: date,
        document_type: DocumentType,
        version: int,
        status: DocumentStatus,
        actor: RequestContext,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
        number: str | None = None,
    ) -> Document:
        document = Document(
            tenant_id=tenant_id,
            client_id=client_id,
            document_type=document_type,
            period_from=period_from,
            period_to=period_to,
            status=status,
            version=version,
            number=number,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            generated_at=datetime.now(timezone.utc),
            created_by_actor_type=actor.actor_type.value if actor.actor_type else None,
            created_by_actor_id=actor.actor_id,
            created_by_email=actor.actor_email,
            meta=self._build_meta(client_id, period_from, period_to, document_type),
        )
        self.db.add(document)
        self.db.flush()

        payload = self._generate_payload(document_type, client_id, period_from, period_to, source_entity_id)
        pdf_file = self._store_file(document, DocumentFileType.PDF, payload.pdf_bytes)
        xlsx_file = self._store_file(
            document,
            DocumentFileType.XLSX,
            payload.xlsx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        document.document_hash = pdf_file.sha256
        document.files.extend([pdf_file, xlsx_file])
        self.db.commit()
        self.db.refresh(document)

        pdf_hash = next(
            (file.sha256 for file in document.files if file.file_type == DocumentFileType.PDF),
            None,
        )
        AuditService(self.db).audit(
            event_type="DOCUMENT_ISSUED",
            entity_type="document",
            entity_id=str(document.id),
            action="CREATE",
            visibility=AuditVisibility.PUBLIC,
            after={
                "document_type": document.document_type.value,
                "version": document.version,
                "file_types": [file.file_type.value for file in document.files],
                "document_hash": pdf_hash,
            },
            request_ctx=actor,
        )

        return document

    def _build_meta(
        self,
        client_id: str,
        period_from: date,
        period_to: date,
        document_type: DocumentType,
    ) -> dict:
        if document_type == DocumentType.RECONCILIATION_ACT:
            return self._reconciliation_meta(client_id, period_from, period_to)
        return {"client_id": client_id, "period": {"from": str(period_from), "to": str(period_to)}}

    def _reconciliation_meta(self, client_id: str, period_from: date, period_to: date) -> dict:
        opening_balance = 0
        invoices_total = (
            self.db.query(Invoice)
            .filter(Invoice.client_id == client_id)
            .filter(Invoice.period_from == period_from)
            .filter(Invoice.period_to == period_to)
            .with_entities(Invoice.total_with_tax)
            .all()
        )
        invoiced_amount = sum(int(row[0] or 0) for row in invoices_total)
        payments_amount = self._sum_amounts(
            self.db.query(InvoicePayment)
            .join(Invoice, InvoicePayment.invoice_id == Invoice.id)
            .filter(Invoice.client_id == client_id)
            .filter(Invoice.period_from == period_from)
            .filter(Invoice.period_to == period_to)
            .with_entities(InvoicePayment.amount)
        )
        refunds_amount = self._sum_amounts(
            self.db.query(CreditNote)
            .join(Invoice, CreditNote.invoice_id == Invoice.id)
            .filter(Invoice.client_id == client_id)
            .filter(Invoice.period_from == period_from)
            .filter(Invoice.period_to == period_to)
            .with_entities(CreditNote.amount)
        )
        closing_balance = opening_balance + invoiced_amount - payments_amount - refunds_amount
        return {
            "client_id": client_id,
            "period": {"from": str(period_from), "to": str(period_to)},
            "opening_balance": opening_balance,
            "invoiced_amount": invoiced_amount,
            "payments_amount": payments_amount,
            "refunds_amount": refunds_amount,
            "closing_balance": closing_balance,
        }

    @staticmethod
    def _sum_amounts(query: Iterable[tuple]) -> int:
        return sum(int(row[0] or 0) for row in query)

    def _generate_payload(
        self,
        document_type: DocumentType,
        client_id: str,
        period_from: date,
        period_to: date,
        invoice_id: str | None,
    ):
        if document_type == DocumentType.INVOICE:
            return self.generator.generate_invoice(
                invoice_id=invoice_id or "", client_id=client_id, period_from=period_from, period_to=period_to
            )
        if document_type == DocumentType.ACT:
            return self.generator.generate_act(client_id=client_id, period_from=period_from, period_to=period_to)
        if document_type == DocumentType.RECONCILIATION_ACT:
            return self.generator.generate_reconciliation_act(
                client_id=client_id, period_from=period_from, period_to=period_to
            )
        raise ValueError("unsupported_document_type")

    def _store_file(
        self,
        document: Document,
        file_type: DocumentFileType,
        payload: bytes,
        *,
        content_type: str = "application/pdf",
    ) -> DocumentFile:
        object_key = self.storage.build_object_key(
            client_id=document.client_id,
            period_from=document.period_from,
            period_to=document.period_to,
            version=document.version,
            document_type=document.document_type,
            file_type=file_type,
        )
        stored = self.storage.store_bytes(object_key=object_key, payload=payload, content_type=content_type)
        return DocumentFile(
            document_id=document.id,
            file_type=file_type,
            bucket=stored.bucket,
            object_key=stored.object_key,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            content_type=stored.content_type,
        )

    def _load_documents(self, package: ClosingPackage) -> dict[DocumentType, Document]:
        docs = {}
        if package.invoice_document_id:
            invoice_doc = self.db.query(Document).filter(Document.id == package.invoice_document_id).one()
            docs[DocumentType.INVOICE] = invoice_doc
        if package.act_document_id:
            act_doc = self.db.query(Document).filter(Document.id == package.act_document_id).one()
            docs[DocumentType.ACT] = act_doc
        if package.recon_document_id:
            recon_doc = self.db.query(Document).filter(Document.id == package.recon_document_id).one()
            docs[DocumentType.RECONCILIATION_ACT] = recon_doc
        return docs
