from __future__ import annotations

import pytest

pytest.importorskip("neft_integration_hub")

from neft_integration_hub import db as db_module


def test_service_specific_auto_create_schema_overrides_global_toggle(monkeypatch):
    monkeypatch.setenv("NEFT_AUTO_CREATE_SCHEMA", "true")
    monkeypatch.delenv("INTEGRATION_HUB_AUTO_CREATE_SCHEMA", raising=False)
    assert db_module.should_auto_create_schema() is True

    monkeypatch.setenv("INTEGRATION_HUB_AUTO_CREATE_SCHEMA", "false")
    assert db_module.should_auto_create_schema() is False

    monkeypatch.setenv("INTEGRATION_HUB_AUTO_CREATE_SCHEMA", "true")
    assert db_module.should_auto_create_schema() is True
