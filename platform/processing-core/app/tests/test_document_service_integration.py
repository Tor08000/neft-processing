from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import Column, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.domains.documents.models  # noqa: F401 - load overlapping document registry as in runtime

from app.db import Base
from app.models.audit_log import ActorType
from app.models.audit_log import AuditLog
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.invoice import Invoice, InvoiceStatus
from app.services import closing_documents
from app.services.document_service_client import DocumentRenderResult
from app.services.closing_documents import ClosingDocumentsService
from app.services.documents_storage import DocumentsStorage, StoredDocumentFile


def _dedupe_table_indexes(*tables) -> None:
    for table in tables:
        seen: set[tuple[str | None, tuple[str, ...]]] = set()
        for index in list(table.indexes):
            signature = (index.name, tuple(column.name for column in index.columns))
            if signature in seen:
                table.indexes.remove(index)
            else:
                seen.add(signature)


@pytest.fixture()
def db_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if "clearing_batch" not in Base.metadata.tables:
        Table("clearing_batch", Base.metadata, Column("id", String(36), primary_key=True), extend_existing=True)
    if "billing_periods" not in Base.metadata.tables:
        Table("billing_periods", Base.metadata, Column("id", String(36), primary_key=True), extend_existing=True)
    if "reconciliation_requests" not in Base.metadata.tables:
        Table("reconciliation_requests", Base.metadata, Column("id", String(36), primary_key=True), extend_existing=True)

    _dedupe_table_indexes(DocumentFile.__table__)

    Base.metadata.create_all(
        bind=engine,
        tables=[
            Invoice.__table__,
            Document.__table__,
            DocumentFile.__table__,
            AuditLog.__table__,
        ],
    )

    testing_session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    try:
        yield testing_session_local
    finally:
        engine.dispose()


def _seed_invoice(session: Session, client_id: str, period_from: date, period_to: date) -> str:
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
    return invoice_id


def test_document_service_enabled_uses_remote_metadata(monkeypatch, db_session_factory):
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

    session = db_session_factory()
    service = ClosingDocumentsService(session)

    period_from = date(2025, 1, 1)
    period_to = date(2025, 1, 31)
    _seed_invoice(session, "client-1", period_from, period_to)

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


def test_document_service_disabled_uses_local_pdf(monkeypatch, db_session_factory):
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

    session = db_session_factory()
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


def test_document_service_persists_files_with_overlapping_document_registry(monkeypatch, db_session_factory):
    monkeypatch.setattr(closing_documents.settings, "DOCUMENT_SERVICE_ENABLED", False)

    def fake_store_bytes(self, *, object_key, payload, content_type):
        return StoredDocumentFile(
            bucket="neft-docs",
            object_key=object_key,
            sha256=f"sha:{object_key.rsplit('/', 1)[-1]}",
            size_bytes=len(payload),
            content_type=content_type,
        )

    monkeypatch.setattr(DocumentsStorage, "store_bytes", fake_store_bytes)

    session = db_session_factory()
    service = ClosingDocumentsService(session)

    period_from = date(2025, 3, 1)
    period_to = date(2025, 3, 31)
    _seed_invoice(session, "client-overlap", period_from, period_to)

    document = service._create_document(
        tenant_id=1,
        client_id="client-overlap",
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
        source_entity_id="invoice-overlap",
    )

    stored_files = session.query(DocumentFile).filter(DocumentFile.document_id == document.id).all()
    assert len(stored_files) == 2
    assert {file.file_type for file in stored_files} == {DocumentFileType.PDF, DocumentFileType.XLSX}
    assert document.document_hash == next(file.sha256 for file in stored_files if file.file_type == DocumentFileType.PDF)
    session.close()


def test_create_document_reuses_existing_scope_after_partial_generation(monkeypatch, db_session_factory):
    monkeypatch.setattr(closing_documents.settings, "DOCUMENT_SERVICE_ENABLED", False)

    def fake_store_bytes(self, *, object_key, payload, content_type):
        return StoredDocumentFile(
            bucket="neft-docs",
            object_key=object_key,
            sha256=f"sha:{object_key.rsplit('/', 1)[-1]}",
            size_bytes=len(payload),
            content_type=content_type,
        )

    monkeypatch.setattr(DocumentsStorage, "store_bytes", fake_store_bytes)

    session = db_session_factory()
    service = ClosingDocumentsService(session)

    period_from = date(2025, 4, 1)
    period_to = date(2025, 4, 30)
    _seed_invoice(session, "client-resume", period_from, period_to)

    actor = closing_documents.RequestContext(
        actor_type=ActorType.SYSTEM,
        actor_id="test",
        actor_email="test@example.com",
        tenant_id=1,
    )

    first = service._create_document(
        tenant_id=1,
        client_id="client-resume",
        period_from=period_from,
        period_to=period_to,
        document_type=DocumentType.INVOICE,
        version=1,
        status=DocumentStatus.ISSUED,
        actor=actor,
        source_entity_type="invoice",
        source_entity_id="invoice-resume",
    )

    second = service._create_document(
        tenant_id=1,
        client_id="client-resume",
        period_from=period_from,
        period_to=period_to,
        document_type=DocumentType.INVOICE,
        version=1,
        status=DocumentStatus.ISSUED,
        actor=actor,
        source_entity_type="invoice",
        source_entity_id="invoice-resume",
    )

    assert second.id == first.id
    assert session.query(Document).filter(Document.client_id == "client-resume").count() == 1
    assert session.query(DocumentFile).filter(DocumentFile.document_id == first.id).count() == 2
    assert (
        session.query(AuditLog)
        .filter(AuditLog.entity_id == str(first.id))
        .filter(AuditLog.event_type == "DOCUMENT_ISSUED")
        .count()
        == 1
    )
    session.close()
