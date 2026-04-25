import importlib
from types import SimpleNamespace

import pytest

migration = importlib.import_module(
    "app.alembic.versions.20261020_0013_operations_limits_alignment"
)


class DummyConnection:
    def __init__(self):
        self.dialect = SimpleNamespace(name="postgresql")
        self.indexes: set[str] = set()
        self.executed: list[str] = []

    def exec_driver_sql(self, statement):
        sql = str(statement)
        self.executed.append(sql)
        if sql.startswith("CREATE") and "INDEX" in sql:
            parts = sql.split()
            idx_pos = parts.index("INDEX")
            idx_name = parts[idx_pos + 1]
            if idx_name == "IF":
                idx_name = parts[idx_pos + 4]
            if idx_name in self.indexes and "IF NOT EXISTS" not in sql:
                raise AssertionError("Attempted to recreate index without safeguard")
            self.indexes.add(idx_name)
        return SimpleNamespace()


class DummyBatch:
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.added_columns: list[str] = []
        self.dropped_constraints: list[str] = []
        self.created_pks: list[list[str]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
        return False

    def add_column(self, column):
        self.added_columns.append(column.name)

    def drop_constraint(self, name, type_=None):  # noqa: ARG002
        self.dropped_constraints.append(name)

    def create_primary_key(self, name, columns):  # noqa: ARG002
        self.created_pks.append(list(columns))

    def drop_column(self, column_name):
        pass


class DummyOp:
    def __init__(self, connection: DummyConnection):
        self.connection = connection
        self.altered_columns: list[tuple[str, str]] = []

    def get_bind(self):
        return self.connection

    def batch_alter_table(self, table_name):
        return DummyBatch(table_name)

    def alter_column(self, table_name, column_name, **kwargs):  # noqa: ARG002
        self.altered_columns.append((table_name, column_name))

    def execute(self, statement):
        return self.connection.exec_driver_sql(statement)

    def create_index(self, name, table_name, columns, unique=False, **kwargs):  # noqa: ARG002
        sql = f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} ON {table_name} ({', '.join(columns)})"
        self.connection.exec_driver_sql(sql)

    def drop_index(self, name, table_name=None):  # noqa: ARG002
        sql = f"DROP INDEX {name}"
        self.connection.exec_driver_sql(sql)


def _prepare_migration(monkeypatch: pytest.MonkeyPatch, connection: DummyConnection):
    dummy_op = DummyOp(connection)
    monkeypatch.setattr(migration, "op", dummy_op)
    inspector = SimpleNamespace(
        get_indexes=lambda table_name, schema=None: [  # noqa: ARG005
            {"name": name} for name in sorted(connection.indexes)
        ],
        get_table_names=lambda: ["operations", "limits_rules"],
        get_columns=lambda table_name: [],  # noqa: ARG005
        get_foreign_keys=lambda table_name, schema=None: [],  # noqa: ARG005
        get_pk_constraint=lambda table_name, schema=None: {  # noqa: ARG005
            "name": "operations_pkey",
            "constrained_columns": ["id"],
        },
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: inspector)
    monkeypatch.setattr(
        migration,
        "table_exists",
        lambda bind, table_name, schema=None: table_name in {"operations", "limits_rules"},
    )
    monkeypatch.setattr(migration, "constraint_exists", lambda *args, **kwargs: True)
    monkeypatch.setattr(migration, "_add_column_if_missing", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration, "_get_operation_fks", lambda *args, **kwargs: [])
    monkeypatch.setattr(migration, "_drop_fk_constraints", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration, "_recreate_fk_constraints", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration, "_ensure_operation_type_enum", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration, "_ensure_operation_status_enum", lambda *args, **kwargs: None)

    def _noop_create(*args, **kwargs):  # noqa: ARG002
        return None

    for enum_name in (
        "operation_type_enum",
        "operation_status_enum",
        "product_type_enum",
        "risk_result_enum",
        "limit_entity_enum",
        "limit_scope_enum",
        "fuel_product_enum",
    ):
        enum_obj = getattr(migration, enum_name)
        monkeypatch.setattr(enum_obj, "create", _noop_create)

    return dummy_op


def test_upgrade_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    connection = DummyConnection()
    _prepare_migration(monkeypatch, connection)

    migration.upgrade()

    assert connection.indexes == {
        "ix_operations_status",
        "ix_operations_operation_type",
        "ix_limits_rules_entity_type",
        "ix_limits_rules_scope",
        "ix_limits_rules_product_type",
    }
    assert len([sql for sql in connection.executed if sql.startswith("CREATE")]) == 5

    connection.executed.clear()

    migration.upgrade()

    assert connection.indexes == {
        "ix_operations_status",
        "ix_operations_operation_type",
        "ix_limits_rules_entity_type",
        "ix_limits_rules_scope",
        "ix_limits_rules_product_type",
    }
    assert not [sql for sql in connection.executed if sql.startswith("CREATE")]
