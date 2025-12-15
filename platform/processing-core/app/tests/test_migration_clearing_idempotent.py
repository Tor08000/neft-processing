import importlib
from types import SimpleNamespace

import pytest


migration = importlib.import_module("app.alembic.versions.20260110_0010_clearing")


class DummyResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class DummyConnection:
    def __init__(self):
        self.tables: set[str] = set()
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed: list[str] = []

    def exec_driver_sql(self, statement, params=None):
        self.executed.append(str(statement))
        if "to_regclass" in str(statement):
            table_name = params.get("table_name") if params else None
            return DummyResult(table_name if table_name in self.tables else None)
        return DummyResult(None)


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection
        self.created_tables: list[str] = []
        self.executed_sql: list[str] = []

    def get_bind(self):
        return self.connection

    def create_table(self, table_name, *args, **kwargs):  # noqa: ARG002
        if table_name in self.connection.tables:
            raise AssertionError(f"Table {table_name} already exists")
        self.connection.tables.add(table_name)
        self.created_tables.append(table_name)

    def execute(self, statement):
        self.executed_sql.append(str(statement))


def _run_upgrade(monkeypatch: pytest.MonkeyPatch, connection: DummyConnection):
    dummy_op = DummyOp(connection)
    monkeypatch.setattr(migration, "op", dummy_op)
    migration.upgrade()
    return dummy_op


def test_upgrade_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection()

    first_run = _run_upgrade(monkeypatch, connection)
    assert set(connection.tables) == {"clearing_batch", "clearing_batch_operation"}
    assert set(first_run.created_tables) == {"clearing_batch", "clearing_batch_operation"}

    second_run = _run_upgrade(monkeypatch, connection)
    assert not second_run.created_tables
    assert len(second_run.executed_sql) == 5
    assert all("IF NOT EXISTS" in sql for sql in second_run.executed_sql)
