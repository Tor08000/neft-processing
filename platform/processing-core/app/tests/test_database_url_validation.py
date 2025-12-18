from __future__ import annotations

import importlib
import sys

import pytest


def test_invalid_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "invalid-url")
    sys.modules.pop("app.db", None)

    with pytest.raises(RuntimeError, match="Invalid DATABASE_URL"):
        importlib.import_module("app.db")
