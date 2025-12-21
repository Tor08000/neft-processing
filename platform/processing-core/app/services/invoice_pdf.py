from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

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
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class InvoicePdfService:
    """Generate and store invoice PDFs."""

    def __init__(self, db: Session):
        self.db = db
        if boto3 is None:
            raise RuntimeError("boto3 is required for PDF storage")
        if any(dep is None for dep in (A4, getSampleStyleSheet, SimpleDocTemplate, Spacer, Table, Paragraph)):
            raise RuntimeError("reportlab is required for PDF generation")
        self._s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        self.bucket = settings.NEFT_INVOICE_PDF_BUCKET
        self.template_version = settings.NEFT_INVOICE_PDF_TEMPLATE_VERSION

    def _pdf_key(self, invoice: Invoice) -> str:
        billing_period = invoice.billing_period_id or "adhoc"
        return f"invoices/{invoice.client_id}/{billing_period}/{invoice.id}.pdf"

    def _render_pdf(self, invoice: Invoice) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"Invoice #{invoice.id}", styles["Title"]),
            Spacer(1, 12),
            Paragraph(f"Client: {invoice.client_id}", styles["Normal"]),
            Paragraph(f"Period: {invoice.period_from} — {invoice.period_to}", styles["Normal"]),
            Paragraph(f"Currency: {invoice.currency}", styles["Normal"]),
            Spacer(1, 12),
            Paragraph("Lines", styles["Heading2"]),
        ]

        if invoice.lines:
            headers = ["Product", "Amount", "Tax", "Quantity"]
            rows = [
                [
                    line.product_id,
                    str(int(line.line_amount or 0)),
                    str(int(line.tax_amount or 0)),
                    str(line.liters or ""),
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
            ]
        )

        doc.build(story)
        return buffer.getvalue()

    def _upload_pdf(self, payload: bytes, key: str) -> str:
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=payload, ContentType="application/pdf")
        return f"s3://{self.bucket}/{key}"

    def generate(self, invoice: Invoice, *, force: bool = False) -> Invoice:
        """Generate PDF for invoice and persist status."""

        if invoice.pdf_status == InvoicePdfStatus.READY and not force:
            return invoice

        invoice.pdf_status = InvoicePdfStatus.GENERATING
        invoice.pdf_error = None
        invoice.pdf_version = self.template_version if force or invoice.pdf_version is None else invoice.pdf_version
        invoice.pdf_generated_at = None
        self.db.add(invoice)
        self.db.flush()

        try:
            pdf_bytes = self._render_pdf(invoice)
            pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
            key = self._pdf_key(invoice)
            pdf_url = self._upload_pdf(pdf_bytes, key)

            invoice.pdf_status = InvoicePdfStatus.READY
            invoice.pdf_generated_at = datetime.now(timezone.utc)
            invoice.pdf_hash = pdf_hash
            invoice.pdf_version = self.template_version
            invoice.pdf_url = pdf_url
            self.db.add(invoice)
            logger.info(
                "invoice.pdf.generated",
                extra={
                    "invoice_id": invoice.id,
                    "client_id": invoice.client_id,
                    "pdf_url": pdf_url,
                    "pdf_hash": pdf_hash,
                },
            )
        except Exception as exc:  # noqa: BLE001
            invoice.pdf_status = InvoicePdfStatus.FAILED
            invoice.pdf_error = str(exc)
            self.db.add(invoice)
            logger.exception("invoice.pdf.failed", extra={"invoice_id": invoice.id})
            raise

        return invoice


__all__ = ["InvoicePdfService"]
