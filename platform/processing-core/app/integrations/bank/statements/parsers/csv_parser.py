from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO

from app.models.integrations import BankTransactionDirection


def parse_csv(content: str) -> list[dict[str, object]]:
    reader = csv.DictReader(StringIO(content))
    transactions: list[dict[str, object]] = []
    for row in reader:
        raw_date = row.get("date") or row.get("Date")
        if not raw_date:
            continue
        parsed = datetime.fromisoformat(raw_date)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        amount = Decimal(str(row.get("amount") or row.get("Amount")))
        direction = str(row.get("direction") or row.get("Direction") or "IN").upper()
        direction_enum = (
            BankTransactionDirection.OUT if direction == "OUT" else BankTransactionDirection.IN
        )
        transactions.append(
            {
                "date": parsed,
                "amount": amount,
                "currency": row.get("currency") or row.get("Currency") or "RUB",
                "direction": direction_enum,
                "counterparty": row.get("counterparty") or row.get("Counterparty"),
                "purpose": row.get("purpose") or row.get("Purpose"),
                "external_ref": row.get("external_ref") or row.get("ExternalRef"),
            }
        )
    return transactions


__all__ = ["parse_csv"]
