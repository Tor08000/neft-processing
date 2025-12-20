import importlib
from types import SimpleNamespace

import pytest


migration = importlib.import_module("app.alembic.versions.20261201_0017_accounts_and_ledger")


class DummyResult:
    def __init__(self, rows: list[tuple]):
        self.rows = rows

    def first(self):
        return self.rows[0] if self.rows else None


class DummyConnection:
    def __init__(self):
        self.dialect = SimpleNamespace(name="postgresql")
        self.types: set[str] = set()
        self.tables: set[str] = set()
        self.indexes: set[str] = set()
        self.statements: list[str] = []

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

    def execute(self, *_args, **__):  # noqa: ANN001
        return DummyResult([])


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection

    def get_bind(self):
        return self.connection

    def create_table(self, name, *_, **__):  # noqa: ANN001
        self.connection.tables.add(name)


@pytest.fixture()
def connection(monkeypatch: pytest.MonkeyPatch) -> DummyConnection:
    conn = DummyConnection()

    dummy_op = DummyOp(conn)
    monkeypatch.setattr(migration, "op", dummy_op)

    def _table_exists(_, table_name: str, **__):  # noqa: ANN001
        return table_name in conn.tables

    monkeypatch.setattr(migration, "table_exists", _table_exists)
    return conn


def test_upgrade_idempotent(connection: DummyConnection):
    migration.upgrade()
    migration.upgrade()

    assert connection.tables == {"accounts", "account_balances", "ledger_entries", "posting_batches"}
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
