from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.accounting_export.canonical import AccountingEntry
from app.services.accounting_export.serializer import serialize_accounting_export_json


def serialize_sap_json(
    *,
    batch_id: str,
    export_type: str,
    generated_at: datetime,
    entries: list[AccountingEntry],
    records_count: int,
) -> tuple[bytes, str]:
    meta: dict[str, Any] = {
        "batch_id": batch_id,
        "export_type": export_type,
        "format": "JSON",
        "generated_at": generated_at,
        "records_count": records_count,
    }
    return serialize_accounting_export_json(meta, entries)


__all__ = ["serialize_sap_json"]
