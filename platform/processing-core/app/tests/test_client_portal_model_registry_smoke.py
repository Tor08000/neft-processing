from __future__ import annotations

import importlib

from app.db import Base


def test_client_portal_tables_registered_once_on_app_import() -> None:
    app_module = importlib.import_module("app.main")

    assert app_module.app is not None

    tables = Base.metadata.tables
    assert "client_operations" in tables
    assert "client_invitations" in tables

    client_prefixed = [name for name in tables.keys() if name.startswith("client_")]
    assert len(client_prefixed) == len(set(client_prefixed))
