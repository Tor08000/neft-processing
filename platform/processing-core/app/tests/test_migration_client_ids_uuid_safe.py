import importlib

import pytest


migration = importlib.import_module(
    "app.alembic.versions.20261010_0012_client_ids_uuid"
)


class DummyResult:
    def __init__(self, row):
        self.row = row

    def scalar(self):
        if isinstance(self.row, tuple):
            return self.row[0]
        return self.row

    def first(self):
        return self.row

    def mappings(self):
        return self


class DummyConnection:
    def __init__(self, tables, columns, invalid_values=None):
        self.tables = set(tables)
        self.columns = columns
        self.invalid_values = invalid_values or set()
        self.executed_sql: list[str] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed_sql.append(sql)

        if "to_regclass" in sql:
            table_name = params["table_name"] if isinstance(params, dict) else params[0]
            plain_name = str(table_name).split(".")[-1]
            return DummyResult(table_name if plain_name in self.tables else None)

        if "information_schema.columns" in sql:
            table = params["table"] if isinstance(params, dict) else params[0]
            column = params["column"] if isinstance(params, dict) else params[1]
            info = self.columns.get(table, {}).get(column)
            return DummyResult(info)

        if "NOT (" in sql and "::text ~" in sql:
            for table, column in self.invalid_values:
                if f'FROM "{table}"' in sql and f'"{column}"' in sql:
                    return DummyResult((1,))
            return DummyResult(None)

        return DummyResult(None)

    exec_driver_sql = execute


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection
        self.alter_calls: list[tuple[str, str]] = []
        self.executed_sql: list[str] = []

    def get_bind(self):
        return self.connection

    def alter_column(self, table_name, column_name, **kwargs):  # noqa: ARG002
        self.alter_calls.append((table_name, column_name))

    def execute(self, statement):
        self.executed_sql.append(str(statement))


def test_upgrade_skips_missing_tables(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(
        tables={"clients"},
        columns={
            "clients": {
                "id": {
                    "data_type": "uuid",
                    "udt_name": "uuid",
                    "is_nullable": "NO",
                    "column_default": None,
                }
            }
        },
    )

    dummy_op = DummyOp(connection)
    monkeypatch.setattr(migration, "op", dummy_op)

    monkeypatch.setattr(
        migration.context, "get_context", lambda: (_ for _ in ()).throw(AttributeError)
    )

    migration.upgrade()

    assert ("client_cards", "client_id") not in dummy_op.alter_calls
    assert all("client_id" not in call for call in dummy_op.alter_calls)
    assert any(
        "ALTER TABLE" in sql and '"clients"' in sql and 'ALTER COLUMN "id" SET DEFAULT gen_random_uuid()' in sql
        for sql in dummy_op.executed_sql
    )


def test_upgrade_does_not_use_context_log(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(tables=set(), columns={})
    dummy_op = DummyOp(connection)
    monkeypatch.setattr(migration, "op", dummy_op)

    monkeypatch.setattr(
        migration.context, "get_context", lambda: (_ for _ in ()).throw(AttributeError)
    )

    migration.upgrade()

    assert dummy_op.alter_calls == []
    assert dummy_op.executed_sql == []
