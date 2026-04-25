import importlib
from types import SimpleNamespace

import pytest


migration = importlib.import_module(
    "app.alembic.versions.20261020_0013_operations_limits_alignment"
)


class DummyResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return list(self._rows)


class DummyConnection:
    def __init__(self, *, invalid_rows=None):
        self.invalid_rows = invalid_rows or []
        self.executed: list[str] = []
        self.dialect = SimpleNamespace(name="postgresql")

    def execute(self, statement):
        sql = str(statement)
        self.executed.append(sql)
        if "SELECT operation_type" in sql:
            return DummyResult(self.invalid_rows)
        return DummyResult()

    def exec_driver_sql(self, statement, params=None):  # noqa: ARG002
        self.executed.append(str(statement))
        return DummyResult()


class DummyInspector:
    def __init__(self, *, columns: dict[str, object], table_names: set[str] | None = None):
        self.columns = columns
        self.table_names = table_names or {"operations"}

    def get_table_names(self):
        return list(self.table_names)

    def get_columns(self, table_name: str):  # noqa: ARG002
        return [
            {"name": name, "type": column_type}
            for name, column_type in self.columns.items()
        ]

    def get_indexes(self, table_name: str, schema=None):  # noqa: ARG002
        return []

    def get_foreign_keys(self, table_name: str, schema=None):  # noqa: ARG002
        return []

    def get_pk_constraint(self, table_name: str, schema=None):  # noqa: ARG002
        return {"name": "operations_pkey", "constrained_columns": ["id"]}


class DummyBatch:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ARG002
        return False

    def add_column(self, *args, **kwargs):  # noqa: ARG002
        return None

    def drop_constraint(self, *args, **kwargs):  # noqa: ARG002
        return None

    def create_primary_key(self, *args, **kwargs):  # noqa: ARG002
        return None

    def drop_column(self, *args, **kwargs):  # noqa: ARG002
        return None


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection
        self.executed_sql: list[str] = []
        self.altered_columns: list[tuple] = []
        self.created_indexes: list[str] = []

    def get_bind(self):
        return self.connection

    def batch_alter_table(self, *args, **kwargs):  # noqa: ARG002
        return DummyBatch()

    def execute(self, statement):
        self.executed_sql.append(str(statement))
        return self.connection.execute(statement)

    def alter_column(self, table_name, column_name, **kwargs):
        self.altered_columns.append((table_name, column_name, kwargs))

    def create_index(self, name, table_name, columns, unique=False, **kwargs):  # noqa: ARG002
        self.created_indexes.append(name)
        self.executed_sql.append(
            f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} ON {table_name} ({', '.join(columns)})"
        )


@pytest.fixture(autouse=True)
def patch_enum_creation(monkeypatch: pytest.MonkeyPatch):
    enums = [
        migration.operation_type_enum,
        migration.operation_status_enum,
        migration.product_type_enum,
        migration.risk_result_enum,
        migration.limit_entity_enum,
        migration.limit_scope_enum,
        migration.fuel_product_enum,
    ]
    for enum in enums:
        monkeypatch.setattr(enum, "create", lambda bind, checkfirst=True: None)
    yield


def _run_upgrade(
    monkeypatch: pytest.MonkeyPatch,
    *,
    operation_type,
    invalid_rows=None,
):
    connection = DummyConnection(invalid_rows=invalid_rows)
    dummy_op = DummyOp(connection)
    inspector = DummyInspector(columns={"operation_type": operation_type})

    monkeypatch.setattr(migration, "op", dummy_op)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: inspector)
    monkeypatch.setattr(
        migration,
        "table_exists",
        lambda bind, table_name, schema=None: table_name == "operations",
    )
    monkeypatch.setattr(migration, "constraint_exists", lambda *args, **kwargs: True)
    monkeypatch.setattr(migration, "_add_column_if_missing", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration, "_get_operation_fks", lambda *args, **kwargs: [])
    monkeypatch.setattr(migration, "_drop_fk_constraints", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration, "_recreate_fk_constraints", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration, "_ensure_operation_status_enum", lambda *args, **kwargs: None)

    migration.upgrade()
    return dummy_op


def test_upgrade_casts_operation_type_with_using(monkeypatch: pytest.MonkeyPatch):
    op_calls = _run_upgrade(monkeypatch, operation_type=migration.sa.String())

    assert any("UPDATE operations" in sql for sql in op_calls.executed_sql)
    assert any(
        table == "operations"
        and column == "operation_type"
        and kwargs.get("postgresql_using") == "operation_type::operationtype"
        for table, column, kwargs in op_calls.altered_columns
    )
    assert any("CREATE INDEX" in sql for sql in op_calls.executed_sql)


def test_upgrade_is_idempotent_when_enum_already_set(monkeypatch: pytest.MonkeyPatch):
    operation_enum = migration.sa.Enum(name="operationtype")
    op_calls = _run_upgrade(monkeypatch, operation_type=operation_enum)

    assert not any(
        column == "operation_type" for _, column, _ in op_calls.altered_columns
    )
    assert not any("UPDATE operations" in sql for sql in op_calls.executed_sql)


def test_upgrade_fails_on_unknown_values(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(RuntimeError) as excinfo:
        _run_upgrade(
            monkeypatch,
            operation_type=migration.sa.String(),
            invalid_rows=[("UNKNOWN_TYPE", 3)],
        )

    assert "UNKNOWN_TYPE" in str(excinfo.value)
