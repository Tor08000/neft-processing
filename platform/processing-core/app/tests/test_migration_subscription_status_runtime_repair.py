import importlib
from types import SimpleNamespace

import pytest

migration = importlib.import_module("app.alembic.versions.20300220_0215_subscription_status_runtime_repair")


class DummyConnection:
    def __init__(self, dialect_name: str = "postgresql"):
        self.dialect = SimpleNamespace(name=dialect_name)


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection

    def get_bind(self) -> DummyConnection:
        return self.connection


def test_upgrade_ensures_legacy_runtime_subscription_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = DummyConnection()
    op_mock = DummyOp(connection)
    calls: list[tuple] = []

    monkeypatch.setattr(migration, "op", op_mock)

    def _ensure_pg_enum_value(conn, enum_name: str, value: str, schema: str):  # noqa: ANN001
        calls.append((conn, enum_name, value, schema))

    monkeypatch.setattr(migration, "ensure_pg_enum_value", _ensure_pg_enum_value)

    migration.upgrade()

    assert calls == [
        (connection, "subscription_status", value, migration.SCHEMA)
        for value in migration.LEGACY_RUNTIME_STATUSES
    ]


def test_upgrade_noop_on_non_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = DummyConnection(dialect_name="sqlite")
    op_mock = DummyOp(connection)

    monkeypatch.setattr(migration, "op", op_mock)

    called = False

    def _ensure_pg_enum_value(conn, enum_name: str, value: str, schema: str):  # noqa: ANN001
        nonlocal called
        called = True

    monkeypatch.setattr(migration, "ensure_pg_enum_value", _ensure_pg_enum_value)

    migration.upgrade()

    assert not called
