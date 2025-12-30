from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

pytestmark = [pytest.mark.contracts, pytest.mark.contracts_events]

ROOT_DIR = Path(__file__).resolve()
while ROOT_DIR.name != "neft-processing" and ROOT_DIR.parent != ROOT_DIR:
    ROOT_DIR = ROOT_DIR.parent

SCHEMA_DIR = ROOT_DIR / "docs" / "contracts" / "events"


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text())


def _sample_value(schema: dict) -> object:
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), schema_type[0])
    if schema_type == "string":
        if schema.get("format") == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        return "sample"
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        return []
    if schema_type == "object":
        return {}
    return "sample"


def _sample_payload(schema: dict) -> dict:
    payload_schema = schema.get("properties", {}).get("payload", {})
    required = payload_schema.get("required", [])
    properties = payload_schema.get("properties", {})
    if not required:
        return {"sample": True}
    return {field: _sample_value(properties.get(field, {})) for field in required}


def _sample_event(event_type: str, schema: dict) -> dict:
    return {
        "event_id": "00000000-0000-0000-0000-000000000000",
        "occurred_at": "2025-01-01T00:00:00Z",
        "correlation_id": "corr-1",
        "trace_id": "trace-1",
        "schema_version": "1.0",
        "event_type": event_type,
        "payload": _sample_payload(schema),
    }


def test_event_schema_registry_validates_samples():
    assert SCHEMA_DIR.exists(), "Event schema registry missing"

    for schema_path in sorted(SCHEMA_DIR.glob("*.json")):
        schema = _load_schema(schema_path)
        event_type = schema.get("title")
        assert event_type, f"Schema {schema_path.name} missing title"

        required = set(schema.get("required", []))
        for field in {
            "event_id",
            "occurred_at",
            "correlation_id",
            "trace_id",
            "schema_version",
            "event_type",
            "payload",
        }:
            assert field in required

        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        validator.validate(_sample_event(event_type, schema))
