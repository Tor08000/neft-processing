from __future__ import annotations

import pytest

from app.config import settings
from app.utils.strict_import import import_router


def test_import_router_optional_in_dev_returns_none(monkeypatch, caplog) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "dev")

    with caplog.at_level("WARNING"):
        router = import_router("app.api.v1.endpoints.module_does_not_exist")

    assert router is None
    assert "Optional module skipped in DEV" in caplog.text


def test_import_router_optional_in_prod_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "prod")

    with pytest.raises(ModuleNotFoundError):
        import_router("app.api.v1.endpoints.module_does_not_exist")


def test_import_router_mandatory_in_dev_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "dev")

    with pytest.raises(ModuleNotFoundError):
        import_router("app.api.v1.endpoints.module_does_not_exist", mandatory=True)
