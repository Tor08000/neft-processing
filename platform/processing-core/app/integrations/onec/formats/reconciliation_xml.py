from __future__ import annotations

from datetime import date
from xml.etree import ElementTree


def _text(parent: ElementTree.Element, tag: str, value: str | None) -> ElementTree.Element:
    elem = ElementTree.SubElement(parent, tag)
    if value is not None:
        elem.text = value
    return elem


def build_reconciliation_xml(payload: dict[str, object]) -> ElementTree.Element:
    root = ElementTree.Element("ReconciliationAct")
    _text(root, "DocId", str(payload.get("doc_id")))
    _text(root, "DocNumber", str(payload.get("doc_number")))
    doc_date: date | None = payload.get("doc_date")  # type: ignore[assignment]
    _text(root, "DocDate", doc_date.isoformat() if doc_date else None)
    _text(root, "DocType", "RECONCILIATION_ACT")
    _text(root, "Status", str(payload.get("status")))
    return root


__all__ = ["build_reconciliation_xml"]
