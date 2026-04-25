import importlib
from types import SimpleNamespace

import pytest

migration = importlib.import_module(
    "app.alembic.versions.20261101_0014_billing_summary_alignment"
)


class DummyResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value

    def first(self):
        return self._value


class DummyConnection:
    def __init__(self, *, types=None, columns=None):
        self.types: set[str] = set(types or [])
        normalized_columns: dict[str, dict[str, dict]] = {}
        for table, table_columns in (columns or {}).items():
            normalized_columns[table] = {}
            for column_name, info in table_columns.items():
                normalized_columns[table][column_name] = info or {}
        self.columns = normalized_columns
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed_sql: list[str] = []

    def exec_driver_sql(self, statement, params=None):  # noqa: ARG002
        if not isinstance(statement, str):
            raise TypeError("statement must be str")

        sql = statement
        self.executed_sql.append(sql)

        if "FROM pg_type" in sql:
            type_name = params["type_name"] if isinstance(params, dict) else params[1]
            return DummyResult(1 if type_name in self.types else None)

        if "information_schema.columns" in sql:
            table_name = params["table_name"] if isinstance(params, dict) else params[1]
            column_name = params["column_name"] if isinstance(params, dict) else params[2]
            return DummyResult(1 if column_name in self.columns.get(table_name, {}) else None)

        if "CREATE TYPE" in sql:
            type_segment = sql.split("CREATE TYPE", 1)[1]
            type_name = type_segment.split("AS ENUM", 1)[0].strip().split(".")[-1].strip(";").strip('"')
            self.types.add(type_name)
            return DummyResult(None)

        return DummyResult(None)

    def execute(self, statement, params=None):  # noqa: ANN001
        return self.exec_driver_sql(str(statement), params)


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection
        self.added_columns: list[tuple[str, str]] = []

    def get_bind(self):
        return self.connection

    def drop_index(self, *args, **kwargs):  # noqa: ARG002
        return None

    def drop_constraint(self, *args, **kwargs):  # noqa: ARG002
        return None

    def alter_column(self, *args, **kwargs):  # noqa: ARG002
        return None

    def drop_column(self, table_name, column_name):
        self.connection.columns.get(table_name, {}).pop(column_name, None)

    def add_column(self, table_name, column):
        self.added_columns.append((table_name, column.name))
        self.connection.columns.setdefault(table_name, {})[column.name] = {
            "udt_name": getattr(column.type, "name", None)
        }

    def create_index(self, *args, **kwargs):  # noqa: ARG002
        return None

    def create_unique_constraint(self, *args, **kwargs):  # noqa: ARG002
        return None


def _run_upgrade(monkeypatch: pytest.MonkeyPatch, connection: DummyConnection):
    dummy_op = DummyOp(connection)
    monkeypatch.setattr(migration, "op", dummy_op)
    migration.upgrade()
    return dummy_op


def test_upgrade_creates_missing_product_type_enum_and_column(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(columns={"billing_summary": {}})

    op_calls = _run_upgrade(monkeypatch, connection)

    assert "product_type" in connection.types
    assert "product_type" in connection.columns.get("billing_summary", {})
    assert connection.columns["billing_summary"]["product_type"]["udt_name"] == "product_type"
    assert ("billing_summary", "product_type") in op_calls.added_columns


def test_upgrade_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(
        types={"product_type"},
        columns={"billing_summary": {"product_type": {"udt_name": "product_type"}}},
    )

    op_calls = _run_upgrade(monkeypatch, connection)

    assert ("billing_summary", "product_type") not in op_calls.added_columns
    assert "product_type" in connection.types
    assert any("product_type" in sql for sql in connection.executed_sql)


def test_exec_driver_sql_invoked_with_str(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(columns={"billing_summary": {}})

    _run_upgrade(monkeypatch, connection)

    assert all(isinstance(sql, str) for sql in connection.executed_sql)
