import importlib
from types import SimpleNamespace

import pytest

migration = importlib.import_module("app.alembic.versions.20271120_0036_billing_job_runs_and_invoice_fields")


class DummyConnection:
    def __init__(self):
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed = []

    def exec_driver_sql(self, statement, params=None):
        self.executed.append((str(statement), params))
        return SimpleNamespace(fetchall=lambda: [], scalar=lambda: None)


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection
        self.added_columns: list[tuple[str, str, str | None]] = []

    def get_bind(self):
        return self.connection

    def add_column(self, table_name, column, schema=None):
        self.added_columns.append((table_name, column.name, schema))


def test_upgrade_invokes_enum_and_table_helpers(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection()
    op_mock = DummyOp(connection)
    monkeypatch.setattr(migration, "op", op_mock)

    enum_calls: list[tuple] = []
    enum_value_calls: list[tuple] = []
    created_tables: list[tuple[str, dict]] = []
    invoice_index_calls: list[tuple[str, tuple[str, ...], str | None]] = []

    monkeypatch.setattr(
        migration,
        "ensure_pg_enum",
        lambda conn, name, values, schema=None: enum_calls.append((name, tuple(values), schema)),
    )
    monkeypatch.setattr(
        migration,
        "ensure_pg_enum_value",
        lambda conn, name, value, schema=None: enum_value_calls.append((name, value, schema)),
    )
    monkeypatch.setattr(
        migration,
        "create_table_if_not_exists",
        lambda conn, table_name, **kwargs: created_tables.append((table_name, kwargs)),
    )
    monkeypatch.setattr(migration, "column_exists", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        migration,
        "create_index_if_not_exists",
        lambda conn, index_name, table_name, columns, schema=None: invoice_index_calls.append(
            (index_name, tuple(columns), schema)
        ),
    )

    migration.upgrade()

    assert ("billing_job_type", tuple(migration.BILLING_JOB_TYPES), migration.SCHEMA) in enum_calls
    assert ("billing_job_status", tuple(migration.BILLING_JOB_STATUSES), migration.SCHEMA) in enum_calls
    assert ("invoice_pdf_status", tuple(migration.INVOICE_PDF_STATUS), migration.SCHEMA) in enum_calls

    assert ("billing_job_type", "PDF_GENERATE", migration.SCHEMA) in enum_value_calls
    assert ("billing_job_status", "STARTED", migration.SCHEMA) in enum_value_calls
    assert ("invoice_pdf_status", "READY", migration.SCHEMA) in enum_value_calls

    created_table_names = {name for name, _kwargs in created_tables}
    assert created_table_names == {"billing_job_runs", "billing_task_links"}

    job_runs_kwargs = next(kwargs for name, kwargs in created_tables if name == "billing_job_runs")
    assert "columns" in job_runs_kwargs and "indexes" in job_runs_kwargs
    assert isinstance(job_runs_kwargs["columns"], list)
    assert {index[0] for index in job_runs_kwargs["indexes"]} >= {
        "ix_billing_job_runs_type_status",
        "ix_billing_job_runs_started_at",
    }

    assert ("invoices", "pdf_status", migration.SCHEMA) in op_mock.added_columns
    assert ("invoices", "pdf_url", migration.SCHEMA) in op_mock.added_columns
    assert ("invoices", "pdf_version", migration.SCHEMA) in op_mock.added_columns
    assert ("invoices", "sent_at", migration.SCHEMA) in op_mock.added_columns

    assert ("ix_invoices_pdf_status", ("pdf_status",), migration.SCHEMA) in invoice_index_calls
    assert ("ix_invoices_sent_at", ("sent_at",), migration.SCHEMA) in invoice_index_calls
