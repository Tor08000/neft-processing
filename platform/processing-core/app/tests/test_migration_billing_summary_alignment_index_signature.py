import importlib
from types import SimpleNamespace

import pytest

from app.db.schema import resolve_db_schema

migration = importlib.import_module(
    "app.alembic.versions.20261101_0014_billing_summary_alignment"
)


class DummyResult:
    def __init__(self, value=None):
        self._value = value

    def first(self):
        return self._value

    def scalar(self):
        return self._value


class DummyConnection:
    def __init__(self):
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed: list[str] = []

    def exec_driver_sql(self, statement, params=None):  # noqa: ARG002
        self.executed.append(str(statement))
        return DummyResult()

    def execute(self, statement, params=None):  # noqa: ANN001, ARG002
        self.executed.append(str(statement))
        return DummyResult()


class DummyOp:
    def __init__(self):
        self.connection = DummyConnection()
        self.create_index_calls: list[tuple[tuple, dict]] = []

    def get_bind(self):
        return self.connection

    def drop_index(self, *args, **kwargs):  # noqa: ARG002
        return None

    def drop_constraint(self, *args, **kwargs):  # noqa: ARG002
        return None

    def alter_column(self, *args, **kwargs):  # noqa: ARG002
        return None

    def drop_column(self, *args, **kwargs):  # noqa: ARG002
        return None

    def add_column(self, *args, **kwargs):  # noqa: ARG002
        return None

    def create_unique_constraint(self, *args, **kwargs):  # noqa: ARG002
        return None

    def create_index(self, *args, **kwargs):  # noqa: ARG002
        assert (
            len(args) == 3
        ), "create_index should receive only name, table and columns positionally"
        self.create_index_calls.append((args, kwargs))


def test_create_index_keyword_only_options(monkeypatch: pytest.MonkeyPatch):
    dummy_op = DummyOp()
    monkeypatch.setattr(migration, "op", dummy_op)

    migration.upgrade()
    migration.downgrade()

    assert dummy_op.create_index_calls, "create_index should have been invoked"
    for args, kwargs in dummy_op.create_index_calls:
        assert len(args) == 3, "schema and postgresql_where must be keyword-only"
        assert "schema" not in kwargs or kwargs["schema"] == resolve_db_schema().schema
