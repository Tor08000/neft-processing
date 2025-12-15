from types import SimpleNamespace

import pytest
from sqlalchemy import String

from app.alembic import utils


class DummyInspector:
    def __init__(self, version_length: int | None, *, has_table: bool = True, has_column: bool = True):
        self.version_length = version_length
        self.has_table = has_table
        self.has_column = has_column

    def get_table_names(self) -> list[str]:
        return ["alembic_version"] if self.has_table else []

    def get_columns(self, table_name: str) -> list[dict]:
        assert table_name == "alembic_version"
        column_type = String(length=self.version_length) if self.version_length else String()
        if not self.has_column:
            return []
        return [{"name": "version_num", "type": column_type}]


class DummyConnection:
    def __init__(self, dialect_name: str = "postgresql"):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.executed_sql: list[str] = []

    def execute(self, statement):
        self.executed_sql.append(str(statement))


@pytest.mark.parametrize("current_length, expected_calls", [(32, 1), (256, 0)])
def test_ensure_alembic_version_length(monkeypatch: pytest.MonkeyPatch, current_length, expected_calls):
    connection = DummyConnection()

    def fake_inspect(conn):
        assert conn is connection
        return DummyInspector(current_length)

    monkeypatch.setattr(utils, "inspect", fake_inspect)

    utils.ensure_alembic_version_length(connection)

    assert len(connection.executed_sql) == expected_calls
    if expected_calls:
        assert "VARCHAR(128)" in connection.executed_sql[0]


def test_ensure_alembic_version_length_creates_missing_table(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection()

    def fake_inspect(conn):
        return DummyInspector(None, has_table=False)

    monkeypatch.setattr(utils, "inspect", fake_inspect)

    utils.ensure_alembic_version_length(connection)

    assert len(connection.executed_sql) == 1
    assert "CREATE TABLE IF NOT EXISTS alembic_version" in connection.executed_sql[0]


def test_ensure_alembic_version_length_adds_missing_column(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection()

    def fake_inspect(conn):
        return DummyInspector(None, has_table=True, has_column=False)

    monkeypatch.setattr(utils, "inspect", fake_inspect)

    utils.ensure_alembic_version_length(connection)

    assert len(connection.executed_sql) == 1
    assert "ADD COLUMN version_num" in connection.executed_sql[0]


def test_ensure_alembic_version_length_ignores_non_postgres(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(dialect_name="sqlite")

    def fake_inspect(conn):
        raise AssertionError("inspect should not be called for sqlite")

    monkeypatch.setattr(utils, "inspect", fake_inspect)

    utils.ensure_alembic_version_length(connection)

    assert connection.executed_sql == []
