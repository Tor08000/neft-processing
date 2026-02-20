import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.scripts import alembic_version_repair as repair_script
from app.scripts.alembic_version_repair import ensure_alembic_version_consistency
from app.tests.utils import ensure_connectable, get_database_url


def test_empty_version_table_smoke_no_nameerror(monkeypatch, capsys):
    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return self

        def all(self):
            return list(self._rows)

    class FakeConnection:
        def execute(self, statement, params=None):
            sql = str(statement)
            if "SELECT version_num" in sql:
                return FakeResult([])
            if "FROM information_schema.tables" in sql:
                return FakeResult([])
            if "FROM information_schema.columns" in sql:
                return FakeResult([])
            return FakeResult([])

    class FakeContextManager:
        def __init__(self, connection):
            self._connection = connection

        def __enter__(self):
            return self._connection

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def __init__(self):
            self.connection = FakeConnection()

        def begin(self):
            return FakeContextManager(self.connection)

        def connect(self):
            return FakeContextManager(self.connection)

        def dispose(self):
            return None

    class FakeScript:
        def get_heads(self):
            return ["head_1"]

        def walk_revisions(self, base, head):
            class _Rev:
                down_revision = None
                revision = "base_1"

            return [_Rev()]

        def get_revision(self, _revision):
            return object()

    class FakeMigrationContext:
        def get_current_heads(self):
            return []

    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("ALEMBIC_CONFIG", str(Path(__file__).parents[1] / "alembic.ini"))
    monkeypatch.setenv("NEFT_DB_SCHEMA", "processing_core")
    monkeypatch.setattr(repair_script.sa, "create_engine", lambda _url: FakeEngine())
    monkeypatch.setattr(repair_script.ScriptDirectory, "from_config", lambda _config: FakeScript())
    monkeypatch.setattr(repair_script.MigrationContext, "configure", lambda *args, **kwargs: FakeMigrationContext())

    ensure_alembic_version_consistency()

    output = capsys.readouterr().out
    assert "mode selected = UPGRADE" in output


def test_write_decision_env_uses_shell_safe_format(monkeypatch, tmp_path):
    decision_file = tmp_path / "alembic_decision.env"
    monkeypatch.setenv("ALEMBIC_DECISION_FILE", str(decision_file))

    repair_script._write_decision_artifacts(
        repair_script.RepairDecision("UPGRADE", "fresh schema and empty version table"),
        ["alembic_version_core"],
    )

    assert decision_file.read_text(encoding="utf-8") == (
        "ALEMBIC_SCHEMA_TABLES=alembic_version_core\n"
        "ALEMBIC_MODE=UPGRADE\n"
        'ALEMBIC_REASON="fresh schema and empty version table"\n'
    )


@pytest.mark.skipif(get_database_url().startswith("sqlite"), reason="Postgres-only test")
def test_version_missing_with_non_empty_schema_fails(monkeypatch):
    db_url = get_database_url()
    connectable = ensure_connectable(db_url)
    schema = f"version_repair_fail_{uuid.uuid4().hex[:8]}"

    with connectable.begin() as connection:
        connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(
            f'CREATE TABLE "{schema}".alembic_version_core (version_num VARCHAR(128) PRIMARY KEY NOT NULL)'
        )
        connection.exec_driver_sql(
            f'CREATE TABLE "{schema}".clients (id UUID PRIMARY KEY, name VARCHAR(255) NOT NULL)'
        )

    alembic_ini = str(Path(__file__).parents[1] / "alembic.ini")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("NEFT_DB_SCHEMA", schema)
    monkeypatch.setenv("ALEMBIC_CONFIG", alembic_ini)
    try:
        with pytest.raises(RuntimeError, match="version table empty but domain tables already exist"):
            ensure_alembic_version_consistency()
    finally:
        with connectable.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connectable.dispose()


@pytest.mark.skipif(get_database_url().startswith("sqlite"), reason="Postgres-only test")
def test_version_missing_with_empty_schema_selects_upgrade_mode(monkeypatch, capsys):
    db_url = get_database_url()
    connectable = ensure_connectable(db_url)
    schema = f"version_repair_upgrade_{uuid.uuid4().hex[:8]}"

    with connectable.begin() as connection:
        connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(
            f'CREATE TABLE "{schema}".alembic_version_core (version_num VARCHAR(128) PRIMARY KEY NOT NULL)'
        )

    alembic_ini = str(Path(__file__).parents[1] / "alembic.ini")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("NEFT_DB_SCHEMA", schema)
    monkeypatch.setenv("ALEMBIC_CONFIG", alembic_ini)

    try:
        ensure_alembic_version_consistency()
    finally:
        with connectable.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connectable.dispose()

    output = capsys.readouterr().out
    assert "mode selected = UPGRADE" in output
