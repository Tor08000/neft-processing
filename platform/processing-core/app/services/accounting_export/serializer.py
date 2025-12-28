from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from io import StringIO
from collections.abc import Callable
from typing import Any, Iterable

from app.services.accounting_export.canonical import AccountingEntry, entry_to_dict


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


def _serialize_csv(
    rows: Iterable[dict[str, Any]],
    *,
    columns: list[str],
    delimiter: str = ",",
    preamble: str | None = None,
) -> bytes:
    output = StringIO()
    if preamble:
        output.write(preamble.rstrip("\n") + "\n")
    writer = csv.writer(output, lineterminator="\n", delimiter=delimiter)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_csv_value(row.get(column)) for column in columns])
    return output.getvalue().encode("utf-8")


def _sorted_entries(entries: Iterable[AccountingEntry]) -> list[AccountingEntry]:
    return sorted(
        entries,
        key=lambda entry: (
            entry.entry_id,
            entry.document_id,
            entry.source_id or "",
        ),
    )


def serialize_entries_csv(
    entries: Iterable[AccountingEntry],
    *,
    columns: list[str],
    delimiter: str = ";",
    preamble: str | None = None,
    row_builder: Callable[[AccountingEntry], dict[str, Any]] | None = None,
) -> bytes:
    rows = [
        (row_builder(entry) if row_builder else entry_to_dict(entry))
        for entry in _sorted_entries(entries)
    ]
    return _serialize_csv(rows, columns=columns, delimiter=delimiter, preamble=preamble)


def serialize_accounting_export_json(
    meta: dict[str, Any],
    entries: Iterable[AccountingEntry],
) -> tuple[bytes, str]:
    entries_payload = [entry_to_dict(entry) for entry in _sorted_entries(entries)]
    normalized_entries = _normalize_json_payload(entries_payload)
    records_checksum = hashlib.sha256(_canonical_json(normalized_entries).encode("utf-8")).hexdigest()
    payload = {"meta": {**meta, "sha256": records_checksum}, "entries": normalized_entries}
    return _canonical_json(payload).encode("utf-8"), records_checksum


def serialize_metadata_json(payload: dict[str, Any]) -> bytes:
    return _canonical_json(payload).encode("utf-8")


__all__ = [
    "serialize_accounting_export_json",
    "serialize_entries_csv",
    "serialize_metadata_json",
]
