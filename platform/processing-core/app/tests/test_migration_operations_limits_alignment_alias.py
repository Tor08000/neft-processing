import importlib
from types import SimpleNamespace

import pytest

migration = importlib.import_module(
    "app.alembic.versions.20261020_0013a_operations_limits_alignment_alias"
)


class DummyResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class DummyConnection:
    def __init__(
        self,
        *,
        version_num: str | None,
        table_exists: bool = True,
        dialect_name: str = "postgresql",
    ):
        self.version_num = version_num
        self.table_exists = table_exists
        self.dialect = SimpleNamespace(name=dialect_name)
        self.executed: list[tuple[str, dict | None]] = []

    def exec_driver_sql(self, statement, params=None):  # noqa: ANN001
        raw_sql = str(statement)
        sql = raw_sql.strip()
        self.executed.append((raw_sql, params))

        if "to_regclass" in sql:
            return DummyResult("alembic_version_core" if self.table_exists else None)

        if "SELECT version_num" in sql:
            return DummyResult(self.version_num)

        if sql.startswith("UPDATE alembic_version_core"):
            if self.table_exists and self.version_num == params["expected"]:
                self.version_num = params["new"]
            return DummyResult(None)

        raise AssertionError(f"Unexpected SQL: {sql}")


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self._connection = connection

    def get_bind(self):
        return self._connection


@pytest.mark.parametrize(
    "version_num, expected",
    [
        ("20261020_0013", "20261020_0013_operations_limits_alignment"),
        ("20261020_0013_operations_limits_alignment", "20261020_0013_operations_limits_alignment"),
        ("unexpected", "unexpected"),
        (None, None),
    ],
)
def test_upgrade_is_idempotent(monkeypatch: pytest.MonkeyPatch, version_num, expected):  # noqa: ANN001
    connection = DummyConnection(version_num=version_num)
    monkeypatch.setattr(migration, "op", DummyOp(connection))

    migration.upgrade()

    assert connection.version_num == expected


def test_upgrade_noop_when_table_missing(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(version_num=None, table_exists=False)
    monkeypatch.setattr(migration, "op", DummyOp(connection))

    migration.upgrade()

    assert connection.version_num is None


def test_downgrade_updates_only_matching_revision(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(version_num="20261020_0013_operations_limits_alignment")
    monkeypatch.setattr(migration, "op", DummyOp(connection))

    migration.downgrade()

    assert connection.version_num == "20261020_0013"


def test_downgrade_skips_non_postgres(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection(
        version_num="20261020_0013_operations_limits_alignment",
        dialect_name="sqlite",
    )
    monkeypatch.setattr(migration, "op", DummyOp(connection))

    migration.downgrade()

    assert connection.version_num == "20261020_0013_operations_limits_alignment"
