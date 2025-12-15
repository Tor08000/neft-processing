import importlib

import pytest

from .test_migration_operations_status_enum_cast import _run_upgrade

migration = importlib.import_module(
    "app.alembic.versions.20261020_0013_operations_limits_alignment"
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


def test_upgrade_drops_mutable_predicate_indexes(monkeypatch: pytest.MonkeyPatch):
    mutable_index_definition = (
        "CREATE INDEX idx_operations_recent ON public.operations "
        "USING btree (created_at) "
        "WHERE ((status = 'OPEN'::text) "
        "AND (created_at >= timezone('utc'::text, now()) - '1 day'::interval));"
    )

    op_calls = _run_upgrade(
        monkeypatch,
        status=migration.sa.String(),
        indexes=[("idx_operations_recent", mutable_index_definition)],
    )

    assert any(
        "DROP INDEX IF EXISTS idx_operations_recent" in sql
        for sql in op_calls.executed_sql
    )

    assert any(
        table == "operations"
        and column == "status"
        and kwargs.get("postgresql_using") == "status::operationstatus"
        for table, column, kwargs in op_calls.altered_columns
    )

    assert any(
        "idx_operations_active_status" in sql for sql in op_calls.executed_sql
    )
