import importlib
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import ProgrammingError


migration = importlib.import_module(
    "app.alembic.versions.20261020_0013_operations_limits_alignment"
)


class DummyResult:
    def __init__(self, *, exists: bool):
        self._exists = exists

    def first(self):
        return (1,) if self._exists else None


class DummyBind:
    def __init__(self, *, existing_columns: set[str]):
        self.existing_columns = existing_columns
        self.dialect = SimpleNamespace(name="postgresql")
        self.last_params: dict[str, str] | None = None

    def execute(self, statement, params):
        self.last_params = params
        return DummyResult(exists=params["column_name"] in self.existing_columns)


class DummyOp:
    def __init__(self, *, fail_with_duplicate: bool = False):
        self.add_calls: list[tuple[str, str, str]] = []
        self.fail_with_duplicate = fail_with_duplicate

    def add_column(self, table_name, column, schema=None):
        self.add_calls.append((table_name, column.name, schema))
        if not self.fail_with_duplicate:
            return

        duplicate_exc = migration.psycopg_errors.DuplicateColumn(
            'column "risk_result" of relation "operations" already exists'
        )
        raise ProgrammingError(
            statement="ALTER TABLE processing_core.operations ADD COLUMN risk_result",
            params=None,
            orig=duplicate_exc,
        )


@pytest.mark.parametrize("column_name", ["risk_result", "Risk_Result"])
def test_add_column_if_missing_skips_existing_column(
    monkeypatch: pytest.MonkeyPatch, column_name: str
):
    bind = DummyBind(existing_columns={column_name})
    dummy_op = DummyOp()
    monkeypatch.setattr(migration, "op", dummy_op)

    migration._add_column_if_missing(
        bind,
        "operations",
        migration.sa.Column(column_name, migration.risk_result_enum, nullable=True),
    )

    assert bind.last_params == {
        "schema": migration.SCHEMA,
        "table_name": "operations",
        "column_name": column_name,
    }
    assert dummy_op.add_calls == []


def test_add_column_if_missing_ignores_duplicate_column_error(
    monkeypatch: pytest.MonkeyPatch,
):
    bind = DummyBind(existing_columns=set())
    dummy_op = DummyOp(fail_with_duplicate=True)
    monkeypatch.setattr(migration, "op", dummy_op)

    migration._add_column_if_missing(
        bind,
        "operations",
        migration.sa.Column("risk_result", migration.risk_result_enum, nullable=True),
    )

    assert dummy_op.add_calls == [("operations", "risk_result", migration.SCHEMA)]
