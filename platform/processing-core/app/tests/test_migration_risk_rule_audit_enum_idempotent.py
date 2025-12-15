from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest


migration = importlib.import_module("app.alembic.versions.20261125_0016_risk_rule_audit")


class DummyResult:
    def __init__(self, rows: list[tuple]):
        self.rows = rows

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar(self):
        first = self.first()
        return first[0] if first else None


class DummyConnection:
    def __init__(self):
        self.dialect = SimpleNamespace(name="postgresql")
        self.types: set[str] = set()
        self.tables: set[str] = set()
        self.indexes: set[str] = set()
        self.statements: list[str] = []

    def exec_driver_sql(self, sql: str, params=None):  # noqa: ANN001
        self.statements.append(sql)
        if "FROM pg_type" in sql:
            type_name = params[1]
            return DummyResult([(1,)] if type_name in self.types else [])

        if sql.startswith("CREATE TYPE"):
            type_name = sql.split()[2].split(".")[-1]
            if type_name in self.types:
                raise AssertionError("Enum type recreated without guard")
            self.types.add(type_name)
            return DummyResult([])

        if sql.startswith("SELECT 1") and "pg_class" in sql:
            index_name = params[1]
            return DummyResult([(1,)] if index_name in self.indexes else [])

        if sql.startswith("CREATE") and "INDEX" in sql:
            parts = sql.split()
            if parts[1] == "UNIQUE":
                name = parts[4]
            elif parts[2] == "IF":
                name = parts[5]
            else:
                name = parts[2]
            if name in self.indexes and "IF NOT EXISTS" not in sql:
                raise AssertionError("Duplicate index creation attempted")
            self.indexes.add(name)
            return DummyResult([])

        if sql.startswith("DROP INDEX"):
            parts = sql.split()
            name = parts[-1].split(".")[-1]
            self.indexes.discard(name)
            return DummyResult([])

        return DummyResult([])


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection

    def get_bind(self):
        return self.connection

    def create_table(self, name, *_, **__):  # noqa: ANN001
        self.connection.tables.add(name)

    def drop_table(self, name, **__):  # noqa: ANN001
        self.connection.tables.discard(name)

    def create_index(self, name, table_name, columns, unique=False, **kwargs):  # noqa: ANN001
        sql = (
            f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} "
            f"ON {table_name} ({', '.join(columns)})"
        )
        self.connection.exec_driver_sql(sql)

    def drop_index(self, name, table_name=None, **kwargs):  # noqa: ANN001
        self.connection.exec_driver_sql(f"DROP INDEX {name}")


@pytest.fixture()
def connection(monkeypatch: pytest.MonkeyPatch) -> DummyConnection:
    conn = DummyConnection()

    dummy_op = DummyOp(conn)
    monkeypatch.setattr(migration, "op", dummy_op)

    def _table_exists(_, table_name: str, **__):  # noqa: ANN001
        return table_name in conn.tables

    monkeypatch.setattr(migration, "table_exists", _table_exists)
    return conn


def test_upgrade_is_idempotent(connection: DummyConnection):
    migration.upgrade()
    migration.upgrade()

    assert "risk_rule_audits" in connection.tables
    assert connection.types == {"riskruleauditaction"}
    create_type_statements = [sql for sql in connection.statements if sql.startswith("CREATE TYPE")]
    assert len(create_type_statements) == 1
    assert connection.indexes == {
        "ix_risk_rule_audits_rule_id",
        "ix_risk_rule_audits_action",
        "ix_risk_rule_audits_performed_at",
    }
