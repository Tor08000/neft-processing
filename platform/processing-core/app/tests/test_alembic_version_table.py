from types import SimpleNamespace

import pytest
from sqlalchemy import String

from app.alembic import utils


class DummyInspector:
    def __init__(self, version_length: int | None):
        self.version_length = version_length

    def get_table_names(self) -> list[str]:
        return ["alembic_version"]

    def get_columns(self, table_name: str) -> list[dict]:
        assert table_name == "alembic_version"
        column_type = String(length=self.version_length) if self.version_length else String()
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


def test_ensure_alembic_version_length_ignores_non_postgres(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(dialect_name="sqlite")

    def fake_inspect(conn):
        raise AssertionError("inspect should not be called for sqlite")

    monkeypatch.setattr(utils, "inspect", fake_inspect)

    utils.ensure_alembic_version_length(connection)

    assert connection.executed_sql == []
