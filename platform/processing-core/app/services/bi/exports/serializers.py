from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from io import StringIO
from typing import Any


def _normalize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _format_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _normalize_datetime(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _format_csv_value(value: Any) -> str:
    normalized = _format_value(value)
    if normalized is None:
        return ""
    if isinstance(normalized, (dict, list)):
        return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    return str(normalized)


def render_csv(headers: list[str], rows: list[dict[str, Any]]) -> bytes:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_format_csv_value(row.get(header)) for header in headers])
    return output.getvalue().encode("utf-8")


def render_jsonl(headers: list[str], rows: list[dict[str, Any]]) -> bytes:
    lines: list[str] = []
    for row in rows:
        ordered = {header: _format_value(row.get(header)) for header in headers}
        lines.append(json.dumps(ordered, ensure_ascii=False, separators=(",", ":")))
    return ("\n".join(lines) + "\n").encode("utf-8") if lines else b""

