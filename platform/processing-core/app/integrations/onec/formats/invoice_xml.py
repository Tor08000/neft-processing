from __future__ import annotations

from datetime import date
from decimal import Decimal
from xml.etree import ElementTree


def _text(parent: ElementTree.Element, tag: str, value: str | None) -> ElementTree.Element:
    elem = ElementTree.SubElement(parent, tag)
    if value is not None:
        elem.text = value
    return elem


def _decimal(value: Decimal | str | int) -> str:
    return f"{Decimal(str(value)):.2f}"


def build_invoice_xml(invoice: dict[str, object]) -> ElementTree.Element:
    root = ElementTree.Element("Invoice")
    _text(root, "DocId", str(invoice.get("doc_id")))
    _text(root, "DocNumber", str(invoice.get("doc_number")))
    doc_date: date | None = invoice.get("doc_date")  # type: ignore[assignment]
    _text(root, "DocDate", doc_date.isoformat() if doc_date else None)
    _text(root, "DocType", "INVOICE")
    _text(root, "Status", str(invoice.get("status")))

    seller = ElementTree.SubElement(root, "Seller")
    seller_payload = invoice.get("seller") or {}
    _text(seller, "Name", str(seller_payload.get("name")) if seller_payload else None)
    _text(seller, "INN", str(seller_payload.get("inn")) if seller_payload else None)
    _text(seller, "KPP", str(seller_payload.get("kpp")) if seller_payload else None)

    _text(root, "BuyerRef", str(invoice.get("buyer_ref")))

    contract_payload = invoice.get("contract") or {}
    if contract_payload:
        contract = ElementTree.SubElement(root, "Contract")
        _text(contract, "ContractId", str(contract_payload.get("id")))
        _text(contract, "ContractNumber", str(contract_payload.get("number")))
        contract_date: date | None = contract_payload.get("signed_at")  # type: ignore[assignment]
        _text(contract, "SignedAt", contract_date.isoformat() if contract_date else None)

    period_payload = invoice.get("period") or {}
    if period_payload:
        period = ElementTree.SubElement(root, "Period")
        period.set("type", str(period_payload.get("type", "month")))
        period.text = str(period_payload.get("value"))

    _text(root, "Currency", str(invoice.get("currency")))

    totals_payload = invoice.get("totals") or {}
    if totals_payload:
        totals = ElementTree.SubElement(root, "Totals")
        _text(totals, "Subtotal", _decimal(totals_payload.get("subtotal", "0")))
        vat_elem = ElementTree.SubElement(totals, "VAT")
        vat_elem.set("rate", str(totals_payload.get("vat_rate", "0")))
        vat_elem.text = _decimal(totals_payload.get("vat", "0"))
        _text(totals, "Total", _decimal(totals_payload.get("total", "0")))

    payment_payload = invoice.get("payment_terms") or {}
    if payment_payload:
        payment = ElementTree.SubElement(root, "PaymentTerms")
        due_date: date | None = payment_payload.get("due_date")  # type: ignore[assignment]
        _text(payment, "DueDate", due_date.isoformat() if due_date else None)
        _text(payment, "Method", str(payment_payload.get("method")))

    lines_payload = invoice.get("lines") or []
    lines = ElementTree.SubElement(root, "Lines")
    for line in lines_payload:
        item = ElementTree.SubElement(lines, "Line")
        _text(item, "LineNo", str(line.get("line_no")))
        _text(item, "SKU", str(line.get("sku")))
        _text(item, "Name", str(line.get("name")))
        qty = ElementTree.SubElement(item, "Qty")
        qty.set("unit", str(line.get("unit")))
        qty.text = str(line.get("qty"))
        _text(item, "Price", _decimal(line.get("price", "0")))
        vat_line = ElementTree.SubElement(item, "VAT")
        vat_line.set("rate", str(line.get("vat_rate", "0")))
        vat_line.text = _decimal(line.get("vat", "0"))
        _text(item, "Amount", _decimal(line.get("amount", "0")))
        accounting_payload = line.get("accounting") or {}
        if accounting_payload:
            accounting = ElementTree.SubElement(item, "Accounting")
            _text(accounting, "IncomeAccount", str(accounting_payload.get("income_account")))
            _text(accounting, "VATAccount", str(accounting_payload.get("vat_account")))

    return root


__all__ = ["build_invoice_xml"]
