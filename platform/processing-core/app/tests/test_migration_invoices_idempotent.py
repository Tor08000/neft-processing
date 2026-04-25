import importlib

import pytest
import sqlalchemy as sa

migration = importlib.import_module("app.alembic.versions.20270115_0020_invoices")


class DummyConnection:
    def __init__(self):
        self.dialect = type("dialect", (), {"name": "postgresql"})()


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self._connection = connection

    def get_bind(self):
        return self._connection

    def create_index(self, *args, **kwargs):  # noqa: D401, ARG002
        """Ensure raw op.create_index is never invoked."""
        raise AssertionError("Raw op.create_index should not be used")


@pytest.fixture()
def dummy_environment(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection()
    op = DummyOp(connection)
    created_indexes: set[str] = set()
    created_tables: set[str] = set()

    def create_table_if_not_exists(bind, table_name, *args, **kwargs):  # noqa: ARG001
        created_tables.add(table_name)

    def create_index_if_not_exists(bind, index_name, table_name, columns, **kwargs):  # noqa: ARG001
        if index_name in created_indexes:
            return
        created_indexes.add(index_name)

    monkeypatch.setattr(migration, "op", op)
    monkeypatch.setattr(migration, "ensure_pg_enum", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration,
        "safe_enum",
        lambda *args, **kwargs: sa.Enum(*migration.INVOICE_STATUS_VALUES, name="invoicestatus", native_enum=False),
    )
    monkeypatch.setattr(migration, "create_table_if_not_exists", create_table_if_not_exists)
    monkeypatch.setattr(migration, "create_index_if_not_exists", create_index_if_not_exists)

    return created_indexes, created_tables


def test_upgrade_is_idempotent(dummy_environment):
    created_indexes, created_tables = dummy_environment

    migration.upgrade()
    migration.upgrade()

    assert created_tables == {"invoices", "invoice_lines"}
    assert created_indexes == {
        "ix_invoices_client_id",
        "ix_invoices_status",
        "ix_invoices_period_from",
        "ix_invoices_period_to",
        "ix_invoice_lines_invoice_id",
    }
