from __future__ import annotations

import importlib


def test_model_registry_has_unique_table_keys(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    db = importlib.import_module("app.db")
    import_all_models = importlib.import_module("app.models.registry").import_all_models

    import_all_models()

    table_keys = list(db.Base.metadata.tables.keys())
    assert len(table_keys) == len(set(table_keys))

    assert table_keys.count("notification_outbox") == 1

    mapped_outbox_models = [
        mapper.class_.__name__
        for mapper in db.Base.registry.mappers
        if getattr(mapper.local_table, "name", None) == "notification_outbox"
    ]
    assert sorted(mapped_outbox_models) == ["NotificationMessage"]
