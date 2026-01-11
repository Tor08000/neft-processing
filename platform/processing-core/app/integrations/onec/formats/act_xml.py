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


def build_act_xml(act: dict[str, object]) -> ElementTree.Element:
    root = ElementTree.Element("Act")
    _text(root, "DocId", str(act.get("doc_id")))
    _text(root, "DocNumber", str(act.get("doc_number")))
    doc_date: date | None = act.get("doc_date")  # type: ignore[assignment]
    _text(root, "DocDate", doc_date.isoformat() if doc_date else None)
    _text(root, "DocType", "ACT")
    _text(root, "Status", str(act.get("status")))

    seller = ElementTree.SubElement(root, "Seller")
    seller_payload = act.get("seller") or {}
    _text(seller, "Name", str(seller_payload.get("name")) if seller_payload else None)
    _text(seller, "INN", str(seller_payload.get("inn")) if seller_payload else None)
    _text(seller, "KPP", str(seller_payload.get("kpp")) if seller_payload else None)

    _text(root, "BuyerRef", str(act.get("buyer_ref")))

    contract_payload = act.get("contract") or {}
    if contract_payload:
        contract = ElementTree.SubElement(root, "Contract")
        _text(contract, "ContractId", str(contract_payload.get("id")))
        _text(contract, "ContractNumber", str(contract_payload.get("number")))

    period_payload = act.get("period") or {}
    if period_payload:
        period = ElementTree.SubElement(root, "Period")
        period.set("type", str(period_payload.get("type", "month")))
        period.text = str(period_payload.get("value"))

    _text(root, "Currency", str(act.get("currency")))

    totals_payload = act.get("totals") or {}
    if totals_payload:
        totals = ElementTree.SubElement(root, "Totals")
        _text(totals, "Subtotal", _decimal(totals_payload.get("subtotal", "0")))
        vat_elem = ElementTree.SubElement(totals, "VAT")
        vat_elem.set("rate", str(totals_payload.get("vat_rate", "0")))
        vat_elem.text = _decimal(totals_payload.get("vat", "0"))
        _text(totals, "Total", _decimal(totals_payload.get("total", "0")))

    services_payload = act.get("services") or []
    services = ElementTree.SubElement(root, "Services")
    for service in services_payload:
        item = ElementTree.SubElement(services, "Service")
        _text(item, "LineNo", str(service.get("line_no")))
        _text(item, "SKU", str(service.get("sku")))
        _text(item, "Name", str(service.get("name")))
        qty = ElementTree.SubElement(item, "Qty")
        qty.set("unit", str(service.get("unit")))
        qty.text = str(service.get("qty"))
        _text(item, "Price", _decimal(service.get("price", "0")))
        vat_line = ElementTree.SubElement(item, "VAT")
        vat_line.set("rate", str(service.get("vat_rate", "0")))
        vat_line.text = _decimal(service.get("vat", "0"))
        _text(item, "Amount", _decimal(service.get("amount", "0")))
        accounting_payload = service.get("accounting") or {}
        if accounting_payload:
            accounting = ElementTree.SubElement(item, "Accounting")
            _text(accounting, "IncomeAccount", str(accounting_payload.get("income_account")))
            _text(accounting, "VATAccount", str(accounting_payload.get("vat_account")))

    base_documents = act.get("base_documents") or {}
    if base_documents:
        base = ElementTree.SubElement(root, "BaseDocuments")
        _text(base, "InvoiceRef", str(base_documents.get("invoice_ref")))

    return root


__all__ = ["build_act_xml"]
