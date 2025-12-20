import importlib
from collections import defaultdict
from types import SimpleNamespace

import pytest


migration = importlib.import_module("app.alembic.versions.20261201_0017_accounts_and_ledger")


class DummyResult:
    def __init__(self, rows: list[tuple]):
        self.rows = rows

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar_one_or_none(self):
        first = self.first()
        return first[0] if first else None


class DummyConnection:
    def __init__(self):
        self.dialect = SimpleNamespace(name="postgresql")
        self.types: set[str] = set()
        self.tables: set[str] = set()
        self.indexes: set[str] = set()
        self.columns: defaultdict[str, set[str]] = defaultdict(set)
        self.statements: list[str] = []
        self.altered_columns: list[tuple[str, str]] = []

    def exec_driver_sql(self, sql: str, params=None):  # noqa: ANN001
        self.statements.append(sql)

        if "FROM pg_type" in sql and params:
            type_name = params[1]
            return DummyResult([(1,)] if type_name in self.types else [])

        if "CREATE TYPE" in sql:
            type_segment = sql.split("CREATE TYPE", 1)[1]
            type_name = type_segment.split()[0].split(".")[-1]
            if type_name not in self.types:
                self.types.add(type_name)
            return DummyResult([])

        if "FROM pg_class" in sql:
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

        return DummyResult([])

    def execute(self, statement, params=None):  # noqa: ANN001
        sql = str(statement)
        if params:
            if "index_name" in params:
                index_name = params["index_name"]
                return DummyResult([(1,)] if index_name in self.indexes else [])
            if {"table_name", "column_name"} <= set(params):
                table_name = params["table_name"]
                column_name = params["column_name"]
                return DummyResult([(1,)] if column_name in self.columns.get(table_name, set()) else [])
        return DummyResult([])


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection

    def get_bind(self):
        return self.connection

    def create_table(self, name, *columns, **__):  # noqa: ANN001
        self.connection.tables.add(name)
        for column in columns:
            column_name = getattr(column, "name", None)
            if column_name:
                self.connection.columns[name].add(column_name)

    def add_column(self, table_name, column, **__):  # noqa: ANN001
        self.connection.columns[table_name].add(column.name)

    def alter_column(self, table_name, column_name, **__):  # noqa: ANN001
        self.connection.altered_columns.append((table_name, column_name))

    def execute(self, statement, params=None):  # noqa: ANN001
        self.connection.exec_driver_sql(str(statement), params)
        return DummyResult([])

    def create_index(self, name, table_name, columns, unique=False, schema=None):  # noqa: ANN001
        qualified_table = f"{schema}.{table_name}" if schema else table_name
        sql = f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} ON {qualified_table} ({', '.join(columns)})"
        self.connection.exec_driver_sql(sql)


@pytest.fixture()
def connection(monkeypatch: pytest.MonkeyPatch) -> DummyConnection:
    conn = DummyConnection()

    dummy_op = DummyOp(conn)
    monkeypatch.setattr(migration, "op", dummy_op)
    conn.op_override = dummy_op

    def _table_exists(_, table_name: str, **__):  # noqa: ANN001
        return table_name in conn.tables

    def _column_exists(_, table_name: str, column_name: str, **__):  # noqa: ANN001
        return column_name in conn.columns.get(table_name, set())

    monkeypatch.setattr(migration, "table_exists", _table_exists)
    monkeypatch.setattr(migration, "column_exists", _column_exists)
    return conn


def test_upgrade_idempotent(connection: DummyConnection):
    migration.upgrade()
    migration.upgrade()

    assert connection.tables == {"accounts", "account_balances", "ledger_entries", "posting_batches"}
    assert connection.columns["accounts"] >= {"owner_type", "owner_id"}
    assert connection.types == {
        "accounttype",
        "accountstatus",
        "accountownertype",
        "postingbatchtype",
        "postingbatchstatus",
        "ledgerdirection",
    }
    assert connection.indexes == {
        "ix_accounts_client_id",
        "ix_accounts_card_id",
        "ix_accounts_type",
        "ix_accounts_status",
        "ix_accounts_owner_type",
        "ix_accounts_owner_id",
        "ix_ledger_entries_account_id",
        "ix_ledger_entries_operation_id",
        "ix_ledger_entries_posted_at",
        "ix_ledger_entries_posting_id",
        "ix_ledger_entries_account_operation",
        "ix_posting_batches_operation_id",
        "ix_posting_batches_idempotency_key",
    }


def test_upgrade_adds_owner_type_when_missing(connection: DummyConnection):
    connection.tables.update({"accounts", "account_balances", "ledger_entries"})
    connection.columns["accounts"].update(
        ["id", "client_id", "card_id", "tariff_id", "currency", "type", "status", "created_at", "updated_at"]
    )

    migration.upgrade()

    assert "owner_type" in connection.columns["accounts"]
    assert any("UPDATE" in sql and "accounts" in sql for sql in connection.statements)
    assert ("accounts", "owner_type") in connection.altered_columns
    assert "ix_accounts_owner_type" in connection.indexes

    indexes_before = set(connection.indexes)
    altered_before = len(connection.altered_columns)
    connection.statements.clear()

    migration.upgrade()

    assert "owner_type" in connection.columns["accounts"]
    assert "ix_accounts_owner_type" in connection.indexes
    assert indexes_before == connection.indexes
    assert altered_before == len(connection.altered_columns)


def test_upgrade_adds_owner_id_when_missing(connection: DummyConnection):
    connection.tables.update({"accounts", "account_balances", "ledger_entries"})
    connection.columns["accounts"].update(
        ["id", "client_id", "card_id", "tariff_id", "currency", "type", "status", "created_at", "updated_at", "owner_type"]
    )

    migration.upgrade()

    assert "owner_id" in connection.columns["accounts"]
    assert "ix_accounts_owner_id" in connection.indexes

    indexes_before = set(connection.indexes)
    connection.columns["accounts"].add("owner_id")

    migration.upgrade()

    assert indexes_before == connection.indexes
