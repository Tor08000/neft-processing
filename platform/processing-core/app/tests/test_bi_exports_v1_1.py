from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from io import StringIO

from app.models.bi import BiExportBatch, BiExportFormat, BiExportKind, BiExportStatus
from app.services.bi.exports.manifest import build_manifest
from app.services.bi.exports.serializers import render_csv, render_jsonl


def test_render_csv_stable_columns_and_dates():
    headers = ["tenant_id", "occurred_at", "payload"]
    rows = [
        {
            "tenant_id": 42,
            "occurred_at": datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            "payload": {"key": "value"},
        }
    ]

    payload = list(csv.reader(StringIO(render_csv(headers, rows).decode("utf-8"))))

    assert payload[0] == ["tenant_id", "occurred_at", "payload"]
    assert payload[1][0] == "42"
    assert payload[1][1] == "2024-01-02T03:04:05+00:00"
    assert payload[1][2] == "{\"key\":\"value\"}"


def test_render_jsonl_valid_lines():
    headers = ["tenant_id", "occurred_at"]
    rows = [
        {"tenant_id": 7, "occurred_at": datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)},
        {"tenant_id": 8, "occurred_at": datetime(2024, 5, 6, 7, 8, 10, tzinfo=timezone.utc)},
    ]

    payload = render_jsonl(headers, rows).decode("utf-8").strip().split("\n")

    parsed = [json.loads(line) for line in payload]
    assert parsed[0]["tenant_id"] == 7
    assert parsed[0]["occurred_at"] == "2024-05-06T07:08:09+00:00"
    assert parsed[1]["tenant_id"] == 8


def test_manifest_contains_schema_fields():
    export = BiExportBatch(
        tenant_id=1,
        kind=BiExportKind.ORDERS,
        scope_type=None,
        scope_id=None,
        date_from=date(2024, 1, 1),
        date_to=date(2024, 1, 2),
        format=BiExportFormat.JSONL,
        status=BiExportStatus.CREATED,
    )
    headers = ["tenant_id", "order_id", "status", "occurred_at"]

    manifest = build_manifest(export, headers=headers, sha256="abc", row_count=2)

    assert manifest["dataset"] == "orders"
    assert manifest["format"] == "JSONL"
    assert manifest["sha256"] == "abc"
    field_names = [field["name"] for field in manifest["fields"]]
    assert field_names == headers
