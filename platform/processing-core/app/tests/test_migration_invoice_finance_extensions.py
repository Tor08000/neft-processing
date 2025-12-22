import importlib
from types import SimpleNamespace

import pytest

migration = importlib.import_module("app.alembic.versions.20271220_0038_finance_invoice_extensions")


class DummyConnection:
    def __init__(self):
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed: list[str] = []

    def exec_driver_sql(self, statement, params=None):  # noqa: D401, ARG002
        """Capture executed SQL for assertions."""
        self.executed.append(str(statement))
        return SimpleNamespace(fetchall=lambda: [], scalar=lambda: None, scalar_one_or_none=lambda: None)


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection
        self.added_columns: list[tuple[str, str, str | None]] = []

    def get_bind(self):
        return self.connection

    def add_column(self, table_name, column, schema=None):
        self.added_columns.append((table_name, column.name, schema))


@pytest.fixture()
def dummy_environment(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection()
    op_mock = DummyOp(connection)

    enum_value_calls: list[tuple[str, str, str | None]] = []
    created_indexes: list[tuple[str, tuple[str, ...], str | None]] = []

    monkeypatch.setattr(migration, "op", op_mock)
    monkeypatch.setattr(
        migration,
        "ensure_pg_enum_value",
        lambda conn, name, value, schema=None: enum_value_calls.append((name, value, schema)),
    )

    columns_present: set[str] = set()

    def column_exists(_, __, column_name, **___):
        return column_name in columns_present

    monkeypatch.setattr(migration, "column_exists", column_exists)
    monkeypatch.setattr(
        migration,
        "create_index_if_not_exists",
        lambda *args, **kwargs: created_indexes.append(
            (args[1], tuple(args[3]) if len(args) > 3 else tuple(), kwargs.get("schema"))
        ),
    )

    return op_mock, enum_value_calls, created_indexes, connection


def test_upgrade_adds_finance_columns_and_enum_values(dummy_environment):
    op_mock, enum_value_calls, created_indexes, connection = dummy_environment

    migration.upgrade()

    assert ("invoicestatus", "DELIVERED", migration.SCHEMA) in enum_value_calls
    assert ("billing_job_type", "INVOICE_SEND", migration.SCHEMA) in enum_value_calls

    added_columns = {(tbl, col) for tbl, col, _ in op_mock.added_columns}
    assert ("invoices", "due_date") in added_columns
    assert ("invoices", "amount_paid") in added_columns
    assert ("invoices", "amount_due") in added_columns
    assert ("invoices", "delivered_at") in added_columns
    assert ("invoices", "accounting_export_batch_id") in added_columns

    assert ("ix_invoices_due_date", ("due_date",), migration.SCHEMA) in created_indexes
    assert any("UPDATE" in statement.upper() and "AMOUNT_PAID" in statement.upper() for statement in connection.executed)
    assert any("UPDATE" in statement.upper() and "amount_due" in statement for statement in connection.executed)
