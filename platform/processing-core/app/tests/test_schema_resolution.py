import os

import pytest

from app.db import schema as schema_module


def test_default_schema_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEFT_DB_SCHEMA", raising=False)

    resolution = schema_module.resolve_db_schema(os.environ)

    assert resolution.schema == "processing_core"
    assert resolution.search_path_sql == 'SET search_path TO "processing_core"'
    assert resolution.line() == "schema_resolved=processing_core"


def test_neft_schema_has_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEFT_DB_SCHEMA", "custom")

    resolution = schema_module.resolve_db_schema(os.environ)

    assert resolution.schema == "custom"
    assert resolution.search_path_sql == 'SET search_path TO "custom"'
