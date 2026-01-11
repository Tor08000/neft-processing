from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4
from xml.etree import ElementTree

from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app.integrations.hub.artifacts import store_integration_file
from app.integrations.onec.mapping import IntegrationMappingService
from app.integrations.onec.formats.act_xml import build_act_xml
from app.integrations.onec.formats.invoice_xml import build_invoice_xml
from app.integrations.onec.formats.reconciliation_xml import build_reconciliation_xml
from app.models.client import Client
from app.models.marketplace_contracts import Contract
from app.models.documents import Document, DocumentType
from app.models.integrations import (
    IntegrationExport,
    IntegrationExportStatus,
    IntegrationType,
)
from app.models.invoice import Invoice
from app.services.audit_service import AuditService, RequestContext

logger = get_logger(__name__)


def _resolve_invoice_status(invoice: Invoice) -> str:
    if invoice.status.value in {"PAID", "PARTIALLY_PAID"}:
        return invoice.status.value
    return "SENT"


def _period_value(period_start: date, period_end: date) -> str:
    if period_start.month == period_end.month and period_start.year == period_end.year:
        return f"{period_start:%Y-%m}"
    return f"{period_start:%Y-%m-%d}/{period_end:%Y-%m-%d}"


def _invoice_totals(invoice: Invoice) -> dict[str, Decimal]:
    subtotal = Decimal(invoice.total_amount) / Decimal(100)
    vat = Decimal(invoice.tax_amount) / Decimal(100)
    total = Decimal(invoice.total_with_tax) / Decimal(100)
    return {"subtotal": subtotal, "vat": vat, "total": total}


def _contract_payload(db: Session, contract_id: str | None) -> dict[str, object] | None:
    if not contract_id:
        return None
    contract = db.query(Contract).filter(Contract.id == contract_id).one_or_none()
    if not contract:
        return None
    return {
        "id": str(contract.id),
        "number": contract.contract_number,
        "signed_at": contract.effective_from.date(),
    }


def export_onec_documents(
    db: Session,
    *,
    period_start: date,
    period_end: date,
    mapping_version: str,
    seller: dict[str, str],
    actor: RequestContext,
) -> IntegrationExport:
    mapping_service = IntegrationMappingService(db, integration_type=IntegrationType.ONEC)

    invoices = (
        db.query(Invoice)
        .filter(Invoice.period_from >= period_start)
        .filter(Invoice.period_to <= period_end)
        .order_by(Invoice.created_at.asc())
        .all()
    )

    counterparts: dict[str, Client] = {}
    for invoice in invoices:
        client = db.query(Client).filter(Client.id == invoice.client_id).one_or_none()
        if client:
            counterparts[str(client.id)] = client

    exchange = ElementTree.Element("NEFTExchange")
    exchange.set("version", "1.0")

    header = ElementTree.SubElement(exchange, "Header")
    sender = ElementTree.SubElement(header, "Sender")
    sender.set("system", "NEFT")
    sender.set("env", "prod")
    ElementTree.SubElement(header, "ExportId").text = str(uuid4())
    ElementTree.SubElement(header, "ExportedAt").text = datetime.now(timezone.utc).isoformat()
    period = ElementTree.SubElement(header, "Period")
    period.set("type", "month")
    period.text = _period_value(period_start, period_end)
    currency = ElementTree.SubElement(header, "Currency")
    currency.set("default", "RUB")
    ElementTree.SubElement(header, "MappingVersion").text = mapping_version

    counterparty_root = ElementTree.SubElement(exchange, "Counterparties")
    for client_id, client in counterparts.items():
        counterparty = ElementTree.SubElement(counterparty_root, "Counterparty")
        ElementTree.SubElement(counterparty, "Id").text = client_id
        ElementTree.SubElement(counterparty, "Type").text = "CLIENT"
        ElementTree.SubElement(counterparty, "Name").text = client.name
        if client.inn:
            ElementTree.SubElement(counterparty, "INN").text = client.inn

    documents_root = ElementTree.SubElement(exchange, "Documents")

    for invoice in invoices:
        totals = _invoice_totals(invoice)
        contract_payload = _contract_payload(db, getattr(invoice, "contract_id", None))
        lines_payload = []
        for line_no, line in enumerate(invoice.lines, start=1):
            context = {
                "line": {
                    "sku": line.product_id,
                    "name": line.product_id,
                }
            }
            mapping = mapping_service.apply("INVOICE_LINE", context, version=mapping_version)
            accounting = {
                "income_account": mapping.values.get("IncomeAccount"),
                "vat_account": mapping.values.get("VATAccount"),
            }
            lines_payload.append(
                {
                    "line_no": line_no,
                    "sku": line.product_id,
                    "name": line.product_id,
                    "qty": 1,
                    "unit": "unit",
                    "price": Decimal(line.line_amount) / Decimal(100),
                    "vat_rate": "20",
                    "vat": Decimal(line.tax_amount) / Decimal(100),
                    "amount": Decimal(line.line_amount + line.tax_amount) / Decimal(100),
                    "accounting": accounting,
                }
            )

        invoice_payload = {
            "doc_id": invoice.id,
            "doc_number": invoice.number or invoice.id,
            "doc_date": invoice.period_to,
            "status": _resolve_invoice_status(invoice),
            "seller": seller,
            "buyer_ref": invoice.client_id,
            "contract": contract_payload or {},
            "period": {"type": "month", "value": _period_value(invoice.period_from, invoice.period_to)},
            "currency": invoice.currency,
            "totals": {
                "subtotal": totals["subtotal"],
                "vat": totals["vat"],
                "vat_rate": "20",
                "total": totals["total"],
            },
            "payment_terms": {"due_date": invoice.due_date, "method": "BANK_TRANSFER"},
            "lines": lines_payload,
        }
        documents_root.append(build_invoice_xml(invoice_payload))

        act_payload = {
            "doc_id": f"act-{invoice.id}",
            "doc_number": f"ACT-{invoice.number or invoice.id}",
            "doc_date": invoice.period_to,
            "status": "ISSUED",
            "seller": seller,
            "buyer_ref": invoice.client_id,
            "contract": contract_payload or {},
            "period": {"type": "month", "value": _period_value(invoice.period_from, invoice.period_to)},
            "currency": invoice.currency,
            "totals": {
                "subtotal": totals["subtotal"],
                "vat": totals["vat"],
                "vat_rate": "20",
                "total": totals["total"],
            },
            "services": [
                {
                    "line_no": line_no + 1,
                    "sku": line["sku"],
                    "name": line["name"],
                    "qty": line["qty"],
                    "unit": line["unit"],
                    "price": line["price"],
                    "vat_rate": line["vat_rate"],
                    "vat": line["vat"],
                    "amount": line["amount"],
                    "accounting": line.get("accounting"),
                }
                for line_no, line in enumerate(lines_payload)
            ],
            "base_documents": {"invoice_ref": invoice.id},
        }
        documents_root.append(build_act_xml(act_payload))

    reconciliation_docs = (
        db.query(Document)
        .filter(Document.document_type == DocumentType.RECONCILIATION_ACT)
        .filter(Document.period_from >= period_start)
        .filter(Document.period_to <= period_end)
        .all()
    )
    for doc in reconciliation_docs:
        recon_payload = {
            "doc_id": doc.id,
            "doc_number": doc.number or doc.id,
            "doc_date": doc.period_to,
            "status": doc.status.value,
        }
        documents_root.append(build_reconciliation_xml(recon_payload))

    payload_bytes = ElementTree.tostring(exchange, encoding="utf-8", xml_declaration=True)
    file_name = f"NEFT_1C_Export_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.xml"

    stored = store_integration_file(
        db,
        file_name=file_name,
        content_type="application/xml",
        payload=payload_bytes,
    )

    export = IntegrationExport(
        integration_type=IntegrationType.ONEC,
        entity_type="DOCUMENTS",
        period_start=period_start,
        period_end=period_end,
        status=IntegrationExportStatus.EXPORTED,
        file_id=stored.file_id,
    )
    db.add(export)
    db.flush()

    AuditService(db).audit(
        event_type="ONEC_EXPORT_COMPLETED",
        entity_type="integration_export",
        entity_id=str(export.id),
        action="exported",
        after={
            "export_id": str(export.id),
            "file_id": stored.file_id,
            "period_start": period_start,
            "period_end": period_end,
        },
        request_ctx=actor,
    )

    logger.info("onec_export_completed", extra={"export_id": str(export.id), "file": file_name})
    return export


__all__ = ["export_onec_documents"]
