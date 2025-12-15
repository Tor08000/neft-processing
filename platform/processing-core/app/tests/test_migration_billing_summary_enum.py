import importlib
from types import SimpleNamespace

import pytest


migration = importlib.import_module(
    "app.alembic.versions.20260110_0009_billing_summary_extend"
)


class DummyConnection:
    def __init__(self):
        self.executed: list[str] = []
        self.dialect = SimpleNamespace(name="postgresql")

    def execute(self, statement):
        self.executed.append(str(statement))


class DummyInspector:
    def __init__(self, columns: set[str], indexes: set[str]):
        self._columns = columns
        self._indexes = indexes

    def get_columns(self, table_name: str):
        assert table_name == "billing_summary"
        return [{"name": name} for name in sorted(self._columns)]

    def get_indexes(self, table_name: str):
        assert table_name == "billing_summary"
        return [{"name": name} for name in sorted(self._indexes)]


class DummyOp:
    def __init__(self, inspector: DummyInspector):
        self._inspector = inspector
        self.bound = DummyConnection()
        self.added_columns: list[tuple[str, str]] = []
        self.created_indexes: list[str] = []
        self.dropped_columns: list[str] = []
        self.dropped_indexes: list[str] = []

    def get_bind(self):
        return self.bound

    def add_column(self, table_name, column):
        self.added_columns.append((table_name, column.name))

    def create_index(self, name, table_name, columns, unique=False):  # noqa: ARG002
        self.created_indexes.append(name)

    def drop_index(self, name, table_name=None):  # noqa: ARG002
        self.dropped_indexes.append(name)

    def drop_column(self, table_name, column_name):  # noqa: ARG002
        self.dropped_columns.append(column_name)


def _run_upgrade(monkeypatch: pytest.MonkeyPatch, inspector: DummyInspector):
    dummy_op = DummyOp(inspector)
    monkeypatch.setattr(migration, "op", dummy_op)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: inspector)

    migration.upgrade()
    return dummy_op


def _run_downgrade(monkeypatch: pytest.MonkeyPatch, inspector: DummyInspector):
    dummy_op = DummyOp(inspector)
    monkeypatch.setattr(migration, "op", dummy_op)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: inspector)

    migration.downgrade()
    return dummy_op


def test_upgrade_creates_enum_and_columns(monkeypatch: pytest.MonkeyPatch):
    inspector = DummyInspector(columns=set(), indexes=set())

    op_calls = _run_upgrade(monkeypatch, inspector)

    assert any("CREATE TYPE billing_summary_status" in sql for sql in op_calls.bound.executed)
    assert {name for _, name in op_calls.added_columns} == {
        "status",
        "generated_at",
        "finalized_at",
        "hash",
    }
    assert set(op_calls.created_indexes) == {
        "ix_billing_summary_status",
        "ix_billing_summary_generated_at",
    }


def test_upgrade_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    inspector = DummyInspector(
        columns={"status", "generated_at", "finalized_at", "hash"},
        indexes={"ix_billing_summary_status", "ix_billing_summary_generated_at"},
    )

    op_calls = _run_upgrade(monkeypatch, inspector)

    assert len(op_calls.added_columns) == 0
    assert len(op_calls.created_indexes) == 0
    # enum safeguard still runs to make sure type exists
    assert len(op_calls.bound.executed) == 1


def test_downgrade_drops_known_objects(monkeypatch: pytest.MonkeyPatch):
    inspector = DummyInspector(
        columns={"status", "generated_at", "finalized_at", "hash"},
        indexes={"ix_billing_summary_status", "ix_billing_summary_generated_at"},
    )

    op_calls = _run_downgrade(monkeypatch, inspector)

    assert set(op_calls.dropped_columns) == {
        "status",
        "generated_at",
        "finalized_at",
        "hash",
    }
    assert set(op_calls.dropped_indexes) == {
        "ix_billing_summary_status",
        "ix_billing_summary_generated_at",
    }


def test_downgrade_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    inspector = DummyInspector(columns=set(), indexes=set())

    op_calls = _run_downgrade(monkeypatch, inspector)

    assert not op_calls.dropped_columns
    assert not op_calls.dropped_indexes
    assert not op_calls.bound.executed
