from __future__ import annotations

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.diagnostics.db_state import ConnectionInventory
from app.scripts import migration_diagnostics


def _inventory(*, versions: list[str], parallel_tables: list[tuple[str, str]]) -> ConnectionInventory:
    return ConnectionInventory(
        server_addr="127.0.0.1",
        server_port=5432,
        current_database="neft",
        current_user="neft",
        search_path="processing_core,public",
        schemas=["processing_core", "public"],
        tables=[("processing_core", table_name) for table_name in sorted(REQUIRED_CORE_TABLES)],
        alembic_versions=versions,
        parallel_alembic_version_tables=parallel_tables,
        schema="processing_core",
    )


def test_main_logs_parallel_tables_when_core_version_missing(monkeypatch, capsys):
    monkeypatch.setattr(
        migration_diagnostics,
        "collect_inventory",
        lambda: _inventory(versions=[], parallel_tables=[("public", "alembic_version")]),
    )
    monkeypatch.setattr(
        migration_diagnostics,
        "_read_parallel_versions",
        lambda _tables: {"public.alembic_version": ["20260101_0008"]},
    )

    result = migration_diagnostics.main()

    assert result == 2
    output = capsys.readouterr().out
    assert "parallel version table detected: public.alembic_version; contents=['20260101_0008']" in output


def test_main_ok_when_version_present_and_no_missing_tables(monkeypatch, capsys):
    monkeypatch.setattr(
        migration_diagnostics,
        "collect_inventory",
        lambda: _inventory(versions=["head"], parallel_tables=[]),
    )

    result = migration_diagnostics.main()

    assert result == 0
    output = capsys.readouterr().out
    assert "core tables present after migrations" in output
