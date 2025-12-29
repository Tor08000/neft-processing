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


def _sample_event(event_type: str) -> dict:
    return {
        "event_id": "00000000-0000-0000-0000-000000000000",
        "occurred_at": "2025-01-01T00:00:00Z",
        "correlation_id": "corr-1",
        "trace_id": "trace-1",
        "schema_version": "1.0",
        "event_type": event_type,
        "payload": {"sample": True},
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
        validator.validate(_sample_event(event_type))
