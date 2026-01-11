from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from xml.etree import ElementTree

from app.models.integrations import BankTransactionDirection


def parse_1c_bank_xml(content: str) -> list[dict[str, object]]:
    root = ElementTree.fromstring(content)
    transactions: list[dict[str, object]] = []
    for doc in root.findall(".//Document"):
        date_text = doc.findtext("Date") or doc.findtext("DateIn")
        if not date_text:
            continue
        parsed = datetime.fromisoformat(date_text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        amount_text = doc.findtext("Amount") or "0"
        amount = Decimal(amount_text)
        direction_text = (doc.findtext("Direction") or "IN").upper()
        direction = BankTransactionDirection.OUT if direction_text == "OUT" else BankTransactionDirection.IN
        transactions.append(
            {
                "date": parsed,
                "amount": amount,
                "currency": doc.findtext("Currency") or "RUB",
                "direction": direction,
                "counterparty": doc.findtext("Counterparty"),
                "purpose": doc.findtext("Purpose"),
                "external_ref": doc.findtext("ExternalRef") or doc.findtext("PaymentId"),
            }
        )
    return transactions


__all__ = ["parse_1c_bank_xml"]
