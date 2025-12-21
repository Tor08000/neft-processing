from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    import boto3
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
except ImportError:  # pragma: no cover - optional dependency
    A4 = None
    getSampleStyleSheet = SimpleDocTemplate = Spacer = Table = Paragraph = None

from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus
from app.services.billing_metrics import metrics as billing_metrics
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class InvoicePdfStorage:
    """Storage helper for invoice PDFs (MinIO/S3)."""

    def __init__(self):
        if boto3 is None:
            raise RuntimeError("boto3 is required for PDF storage")

        self.bucket = settings.NEFT_S3_BUCKET or settings.NEFT_INVOICE_PDF_BUCKET
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.NEFT_S3_ACCESS_KEY,
            aws_secret_access_key=settings.NEFT_S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )

    def put_pdf(self, key: str, payload: bytes) -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=payload, ContentType="application/pdf")
        return f"s3://{self.bucket}/{key}"

    def get_presigned_url(self, key: str, expires: int = 3600) -> Optional[str]:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )
        except Exception:  # pragma: no cover - optional presign failure
            logger.warning("invoice.pdf.presign_failed", extra={"key": key})
            return None


class InvoicePdfService:
    """Generate and store invoice PDFs."""

    def __init__(self, db: Session):
        self.db = db
        if any(dep is None for dep in (A4, getSampleStyleSheet, SimpleDocTemplate, Spacer, Table, Paragraph)):
            raise RuntimeError("reportlab is required for PDF generation")
        self.storage = InvoicePdfStorage()
        self.template_version = settings.NEFT_INVOICE_PDF_TEMPLATE_VERSION

    def _pdf_key(self, invoice: Invoice) -> str:
        billing_period = invoice.billing_period_id or "adhoc"
        return f"invoices/{invoice.client_id}/{billing_period}/{invoice.id}/v{invoice.pdf_version}.pdf"

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

        locked.pdf_status = InvoicePdfStatus.GENERATING
        locked.pdf_error = None
        locked.pdf_generated_at = None
        locked.pdf_version = (locked.pdf_version or 1) + 1 if force else (locked.pdf_version or 1)
        self.db.add(locked)
        self.db.flush()

        try:
            pdf_bytes = self._render_pdf(locked)
            pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
            key = self._pdf_key(locked)
            pdf_url = self.storage.put_pdf(key, pdf_bytes)

            locked.pdf_status = InvoicePdfStatus.READY
            locked.pdf_generated_at = datetime.now(timezone.utc)
            locked.pdf_hash = pdf_hash
            locked.pdf_url = pdf_url
            self.db.add(locked)
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


__all__ = ["InvoicePdfService", "InvoicePdfStorage"]
