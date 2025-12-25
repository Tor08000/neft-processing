from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from io import StringIO
from typing import Any


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _canonical_json(data: Any) -> str:
    normalized = _normalize_json_payload(data)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize_json_payload(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(key): _normalize_json_payload(data[key]) for key in sorted(data)}
    if isinstance(data, list):
        return [_normalize_json_payload(item) for item in data]
    return _normalize_value(data)


def _csv_value(value: Any) -> str:
    normalized = _normalize_value(value)
    if normalized is None:
        return ""
    return str(normalized)


def _serialize_csv(rows: list[dict[str, Any]], *, columns: list[str]) -> bytes:
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_csv_value(row.get(column)) for column in columns])
    return output.getvalue().encode("utf-8")


def serialize_charges_csv(rows: list[dict[str, Any]]) -> bytes:
    columns = [
        "period_id",
        "invoice_id",
        "invoice_number",
        "client_id",
        "issued_at",
        "period_from",
        "period_to",
        "currency",
        "total_amount",
        "tax_amount",
        "total_with_tax",
        "status",
        "pdf_hash",
        "external_number",
    ]
    return _serialize_csv(rows, columns=columns)


def serialize_settlement_csv(rows: list[dict[str, Any]]) -> bytes:
    columns = [
        "settlement_period_id",
        "invoice_id",
        "source_type",
        "source_id",
        "amount",
        "currency",
        "applied_at",
        "charge_period_id",
        "provider",
        "external_ref",
    ]
    return _serialize_csv(rows, columns=columns)


def serialize_accounting_export_json(
    header: dict[str, Any],
    records: list[dict[str, Any]],
) -> tuple[bytes, str]:
    records_payload = _normalize_json_payload(records)
    records_checksum = hashlib.sha256(_canonical_json(records_payload).encode("utf-8")).hexdigest()
    payload = {"header": {**header, "checksum": records_checksum}, "records": records_payload}
    return _canonical_json(payload).encode("utf-8"), records_checksum


__all__ = [
    "serialize_accounting_export_json",
    "serialize_charges_csv",
    "serialize_settlement_csv",
]
