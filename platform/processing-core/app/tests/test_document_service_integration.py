from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.db import Base, engine, get_sessionmaker
from app.models.audit_log import ActorType
from app.models.documents import DocumentFileType, DocumentStatus, DocumentType
from app.models.invoice import Invoice, InvoiceStatus
from app.services import closing_documents
from app.services.document_service_client import DocumentRenderResult
from app.services.closing_documents import ClosingDocumentsService
from app.services.documents_storage import DocumentsStorage, StoredDocumentFile


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_invoice(client_id: str, period_from: date, period_to: date) -> str:
    session = get_sessionmaker()()
    invoice_id = str(uuid4())
    invoice = Invoice(
        id=invoice_id,
        client_id=client_id,
        number=f"INV-{invoice_id[:8]}",
        period_from=period_from,
        period_to=period_to,
        currency="RUB",
        status=InvoiceStatus.SENT,
        total_amount=10000,
        tax_amount=2000,
        total_with_tax=12000,
        amount_paid=5000,
        amount_due=7000,
        amount_refunded=0,
        issued_at=datetime.now(timezone.utc),
    )
    session.add(invoice)
    session.commit()
    session.close()
    return invoice_id


def test_document_service_enabled_uses_remote_metadata(monkeypatch):
    monkeypatch.setattr(closing_documents.settings, "DOCUMENT_SERVICE_ENABLED", True)

    render_result = DocumentRenderResult(
        bucket="neft-docs",
        object_key="documents/tenant-1/INVOICE/2025/01/doc-1/v1.pdf",
        sha256="abcd",
        size_bytes=10,
        content_type="application/pdf",
        version=1,
    )

    def fake_render(self, request):
        return render_result

    monkeypatch.setattr(closing_documents.DocumentServiceClient, "render", fake_render)

    def fake_store_bytes(self, *, object_key, payload, content_type):
        return StoredDocumentFile(
            bucket="neft-docs",
            object_key=object_key,
            sha256="xlsx",
            size_bytes=len(payload),
            content_type=content_type,
        )

    monkeypatch.setattr(DocumentsStorage, "store_bytes", fake_store_bytes)

    session = get_sessionmaker()()
    service = ClosingDocumentsService(session)

    period_from = date(2025, 1, 1)
    period_to = date(2025, 1, 31)
    _seed_invoice("client-1", period_from, period_to)

    document = service._create_document(
        tenant_id=1,
        client_id="client-1",
        period_from=period_from,
        period_to=period_to,
        document_type=DocumentType.INVOICE,
        version=1,
        status=DocumentStatus.ISSUED,
        actor=closing_documents.RequestContext(
            actor_type=ActorType.SYSTEM,
            actor_id="test",
            actor_email="test@example.com",
        ),
        source_entity_type="invoice",
        source_entity_id="invoice-1",
    )

    pdf_file = next(file for file in document.files if file.file_type == DocumentFileType.PDF)
    assert pdf_file.bucket == "neft-docs"
    assert pdf_file.object_key == render_result.object_key
    assert pdf_file.sha256 == render_result.sha256
    assert pdf_file.size_bytes == render_result.size_bytes
    assert pdf_file.content_type == render_result.content_type
    session.close()


def test_document_service_disabled_uses_local_pdf(monkeypatch):
    monkeypatch.setattr(closing_documents.settings, "DOCUMENT_SERVICE_ENABLED", False)

    stored: dict[str, StoredDocumentFile] = {}

    def fake_store_bytes(self, *, object_key, payload, content_type):
        stored[object_key] = StoredDocumentFile(
            bucket="neft-docs",
            object_key=object_key,
            sha256="local",
            size_bytes=len(payload),
            content_type=content_type,
        )
        return stored[object_key]

    monkeypatch.setattr(DocumentsStorage, "store_bytes", fake_store_bytes)

    session = get_sessionmaker()()
    service = ClosingDocumentsService(session)

    period_from = date(2025, 2, 1)
    period_to = date(2025, 2, 28)

    document = service._create_document(
        tenant_id=1,
        client_id="client-1",
        period_from=period_from,
        period_to=period_to,
        document_type=DocumentType.ACT,
        version=1,
        status=DocumentStatus.ISSUED,
        actor=closing_documents.RequestContext(
            actor_type=ActorType.SYSTEM,
            actor_id="test",
            actor_email="test@example.com",
        ),
        source_entity_type="billing_period",
    )

    pdf_file = next(file for file in document.files if file.file_type == DocumentFileType.PDF)
    assert pdf_file.object_key in stored
    session.close()
