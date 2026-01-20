from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.immutability import ImmutableRecordError
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus, InvoiceStatus


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_document(session, *, status: DocumentStatus) -> Document:
    document = Document(
        tenant_id=1,
        client_id="client-1",
        document_type=DocumentType.INVOICE,
        period_from=date(2025, 2, 1),
        period_to=date(2025, 2, 28),
        status=status,
        version=1,
        document_hash="hash-1",
    )
    session.add(document)
    session.flush()
    session.add(
        DocumentFile(
            document_id=document.id,
            file_type=DocumentFileType.PDF,
            bucket="docs",
            object_key=f"docs/{document.id}.pdf",
            sha256="hash-1",
            size_bytes=100,
            content_type="application/pdf",
        )
    )
    session.commit()
    session.refresh(document)
    return document


def test_document_file_update_blocked_after_acknowledged():
    session = SessionLocal()
    try:
        document = _seed_document(session, status=DocumentStatus.ACKNOWLEDGED)
        file_record = (
            session.query(DocumentFile)
            .filter(DocumentFile.document_id == document.id)
            .filter(DocumentFile.file_type == DocumentFileType.PDF)
            .one()
        )
        file_record.sha256 = "hash-2"
        with pytest.raises(ImmutableRecordError):
            session.commit()
    finally:
        session.close()


def test_document_acknowledgement_delete_blocked():
    session = SessionLocal()
    try:
        document = _seed_document(session, status=DocumentStatus.ACKNOWLEDGED)
        acknowledgement = DocumentAcknowledgement(
            tenant_id=1,
            client_id=document.client_id,
            document_type=document.document_type.value,
            document_id=str(document.id),
            document_object_key=f"docs/{document.id}.pdf",
            document_hash="hash-1",
            ack_by_user_id="user-1",
            ack_by_email="user@example.com",
            ack_method="UI",
        )
        session.add(acknowledgement)
        session.commit()

        session.delete(acknowledgement)
        with pytest.raises(ImmutableRecordError):
            session.commit()
    finally:
        session.close()


def test_invoice_line_update_blocked_after_period_finalize():
    session = SessionLocal()
    try:
        period = BillingPeriod(
            period_type=BillingPeriodType.ADHOC,
            start_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
            tz="UTC",
            status=BillingPeriodStatus.FINALIZED,
        )
        session.add(period)
        session.flush()

        invoice = Invoice(
            client_id="client-1",
            period_from=period.start_at.date(),
            period_to=period.end_at.date(),
            currency="RUB",
            billing_period_id=period.id,
            total_amount=1000,
            tax_amount=0,
            total_with_tax=1000,
            amount_paid=0,
            amount_due=1000,
            status=InvoiceStatus.SENT,
            pdf_status=InvoicePdfStatus.READY,
        )
        session.add(invoice)
        session.flush()

        line = InvoiceLine(
            invoice_id=invoice.id,
            operation_id="op-1",
            product_id="FUEL",
            line_amount=1000,
            tax_amount=0,
        )
        session.add(line)
        session.commit()

        line.line_amount = 900
        with pytest.raises(ImmutableRecordError):
            session.commit()
    finally:
        session.close()


def test_invoice_total_update_blocked_after_period_lock():
    session = SessionLocal()
    try:
        period = BillingPeriod(
            period_type=BillingPeriodType.ADHOC,
            start_at=datetime(2025, 4, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 4, 1, tzinfo=timezone.utc),
            tz="UTC",
            status=BillingPeriodStatus.LOCKED,
        )
        session.add(period)
        session.flush()

        invoice = Invoice(
            client_id="client-1",
            period_from=period.start_at.date(),
            period_to=period.end_at.date(),
            currency="RUB",
            billing_period_id=period.id,
            total_amount=1000,
            tax_amount=0,
            total_with_tax=1000,
            amount_paid=0,
            amount_due=1000,
            status=InvoiceStatus.SENT,
            pdf_status=InvoicePdfStatus.READY,
        )
        session.add(invoice)
        session.commit()

        invoice.total_amount = 1200
        with pytest.raises(ImmutableRecordError):
            session.commit()
    finally:
        session.close()
