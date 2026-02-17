import importlib

import pytest

migration = importlib.import_module(
    "app.alembic.versions.20261020_0013a_operations_limits_alignment_alias"
)


class DummyConnection:
    def __init__(self):
        self.executed: list[tuple[str, dict | None]] = []

    def exec_driver_sql(self, statement, params=None):  # noqa: ANN001
        self.executed.append((str(statement), params))
        raise AssertionError("alias migration should not run SQL")


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self._connection = connection

    def get_bind(self):
        return self._connection


@pytest.mark.parametrize("fn_name", ["upgrade", "downgrade"])
def test_alias_migration_is_noop(monkeypatch: pytest.MonkeyPatch, fn_name: str) -> None:
    connection = DummyConnection()
    monkeypatch.setattr(migration, "op", DummyOp(connection), raising=False)

    getattr(migration, fn_name)()

    assert connection.executed == []
