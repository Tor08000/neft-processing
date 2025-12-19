import os

import pytest

from app.db import schema as schema_module


def test_default_schema_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEFT_DB_SCHEMA", raising=False)
    monkeypatch.delenv("DB_SCHEMA", raising=False)

    resolution = schema_module.resolve_db_schema(os.environ)

    assert resolution.schema == "public"
    assert resolution.source == "default"
    assert resolution.search_path == "public"
    assert resolution.line() == "schema_resolved=public source=default"


def test_neft_schema_has_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEFT_DB_SCHEMA", "custom")
    monkeypatch.setenv("DB_SCHEMA", "legacy")

    resolution = schema_module.resolve_db_schema(os.environ)

    assert resolution.schema == "custom"
    assert resolution.source == "NEFT_DB_SCHEMA"
    assert resolution.search_path == "custom,public"


def test_db_schema_still_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEFT_DB_SCHEMA", raising=False)
    monkeypatch.setenv("DB_SCHEMA", "compat")

    resolution = schema_module.resolve_db_schema(os.environ)

    assert resolution.schema == "compat"
    assert resolution.source == "DB_SCHEMA"
    assert resolution.search_path == "compat,public"
