import importlib
from types import SimpleNamespace

import pytest


migration = importlib.import_module("app.alembic.versions.20260110_0010_clearing")


class DummyResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value

    def first(self):
        if self._value is None:
            return None
        return (self._value,)


class DummyConnection:
    def __init__(self):
        self.tables: set[str] = set()
        self.indexes: set[str] = set()
        self.enums: set[str] = set()
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed: list[str] = []
        self.executed_params: list[tuple | dict | None] = []

    def exec_driver_sql(self, statement, params=None):
        self.executed.append(str(statement))
        self.executed_params.append(params)
        if "information_schema.tables" in str(statement):
            schema, table_name = params or (None, None)
            return DummyResult(table_name if table_name in self.tables else None)
        if "pg_class" in str(statement):
            _, index_name = params or (None, None)
            return DummyResult(1 if index_name in self.indexes else None)
        if "FROM pg_type" in str(statement):
            _, type_name = params or (None, None)
            return DummyResult(1 if type_name in self.enums else None)
        if statement.startswith("CREATE") and "INDEX" in statement:
            parts = statement.split()
            name = parts[4] if parts[1] == "UNIQUE" else parts[2]
            self.indexes.add(name)
        if statement.startswith("CREATE TYPE"):
            type_name = statement.split()[2].split(".")[-1]
            self.enums.add(type_name)
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
    create_statements = [
        sql for sql in connection.executed if sql.startswith("CREATE INDEX")
    ]
    assert create_statements
    assert all("IF NOT EXISTS" in sql for sql in create_statements)
