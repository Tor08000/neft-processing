from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
except ImportError:  # pragma: no cover - optional dependency
    A4 = None
    getSampleStyleSheet = SimpleDocTemplate = Spacer = Table = Paragraph = None

from app.models.audit_log import ActorType
from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus
from app.services.audit_service import AuditService, RequestContext
from app.services.billing_metrics import metrics as billing_metrics
from app.services.s3_storage import S3Storage
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class InvoicePdfService:
    """Generate and store invoice PDFs."""

    def __init__(self, db: Session):
        self.db = db
        if any(dep is None for dep in (A4, getSampleStyleSheet, SimpleDocTemplate, Spacer, Table, Paragraph)):
            raise RuntimeError("reportlab is required for PDF generation")
        self.storage = S3Storage()
        self.storage.ensure_bucket()
        self.template_version = settings.NEFT_INVOICE_PDF_TEMPLATE_VERSION

    def _pdf_key(self, invoice: Invoice) -> str:
        if invoice.pdf_object_key:
            return invoice.pdf_object_key
        return f"invoices/{invoice.id}.pdf"

    def _render_pdf(self, invoice: Invoice) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph("NEFT", styles["Title"]),
            Spacer(1, 12),
            Paragraph(f"Invoice #{invoice.id}", styles["Heading2"]),
            Paragraph(f"Client: {invoice.client_id}", styles["Normal"]),
            Paragraph(f"Period: {invoice.period_from} — {invoice.period_to}", styles["Normal"]),
            Paragraph(f"Currency: {invoice.currency}", styles["Normal"]),
            Spacer(1, 12),
            Paragraph("Lines", styles["Heading2"]),
        ]
        if invoice.external_number:
            story.insert(4, Paragraph(f"External #: {invoice.external_number}", styles["Normal"]))

        if invoice.lines:
            headers = ["Product", "Amount", "Tax", "Quantity", "Unit price"]
            rows = [
                [
                    line.product_id,
                    str(int(line.line_amount or 0)),
                    str(int(line.tax_amount or 0)),
                    str(line.liters or ""),
                    str(line.unit_price or ""),
                ]
                for line in invoice.lines
            ]
            table = Table([headers, *rows])
            story.append(table)
        else:
            story.append(Paragraph("No lines", styles["Italic"]))

        story.extend(
            [
                Spacer(1, 12),
                Paragraph(f"Total: {invoice.total_amount}", styles["Normal"]),
                Paragraph(f"Tax: {invoice.tax_amount}", styles["Normal"]),
                Paragraph(f"Total with tax: {invoice.total_with_tax}", styles["Normal"]),
                Paragraph(f"Generated at: {datetime.now(timezone.utc).isoformat()}", styles["Normal"]),
            ]
        )

        doc.build(story)
        return buffer.getvalue()

    def _lock_invoice(self, invoice_id: str) -> Invoice:
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        if getattr(self.db.bind.dialect, "name", "") == "postgresql":
            stmt = stmt.with_for_update()
        invoice = self.db.execute(stmt).scalar_one()
        return invoice

    def generate(self, invoice: Invoice, *, force: bool = False) -> Invoice:
        """Generate PDF for invoice and persist status."""

        locked = self._lock_invoice(invoice.id)
        if locked.pdf_status == InvoicePdfStatus.READY and not force:
            return locked

        key = self._pdf_key(locked)
        if not force and self.storage.exists(key):
            locked.pdf_status = InvoicePdfStatus.READY
            locked.pdf_generated_at = locked.pdf_generated_at or datetime.now(timezone.utc)
            locked.pdf_object_key = key
            locked.pdf_url = locked.pdf_url or self.storage.public_url(key)
            self.db.add(locked)
            return locked

        locked.pdf_status = InvoicePdfStatus.GENERATING
        locked.pdf_error = None
        locked.pdf_generated_at = None
        locked.pdf_url = None
        locked.pdf_version = locked.pdf_version or 1
        locked.pdf_object_key = key
        self.db.add(locked)
        self.db.flush()

        try:
            pdf_bytes = self._render_pdf(locked)
            pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
            pdf_url = self.storage.put_bytes(key, pdf_bytes, content_type="application/pdf")

            locked.pdf_status = InvoicePdfStatus.READY
            locked.pdf_generated_at = datetime.now(timezone.utc)
            locked.pdf_hash = pdf_hash
            locked.pdf_url = pdf_url
            self.db.add(locked)
            AuditService(self.db).audit(
                event_type="INVOICE_PDF_UPLOADED",
                entity_type="invoice",
                entity_id=locked.id,
                action="CREATE",
                after={
                    "pdf_url": pdf_url,
                    "pdf_hash": pdf_hash,
                    "pdf_object_key": locked.pdf_object_key,
                },
                request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id="invoice_pdf"),
            )
            logger.info(
                "invoice.pdf.generated",
                extra={
                    "invoice_id": locked.id,
                    "client_id": locked.client_id,
                    "pdf_url": pdf_url,
                    "pdf_hash": pdf_hash,
                },
            )
            billing_metrics.mark_pdf_generated()
        except Exception as exc:  # noqa: BLE001
            locked.pdf_status = InvoicePdfStatus.FAILED
            locked.pdf_error = str(exc)[:2048]
            self.db.add(locked)
            logger.exception("invoice.pdf.failed", extra={"invoice_id": locked.id})
            billing_metrics.mark_pdf_error()
            raise

        return locked


__all__ = ["InvoicePdfService"]
