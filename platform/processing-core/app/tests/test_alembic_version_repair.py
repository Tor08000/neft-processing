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


@pytest.mark.skipif(get_database_url().startswith("sqlite"), reason="Postgres-only test")
def test_version_missing_with_non_empty_schema_stamps_heads(monkeypatch, capsys):
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
    monkeypatch.setenv("ALEMBIC_AUTO_REPAIR", "1")
    monkeypatch.setenv("APP_ENV", "dev")

    try:
        ensure_alembic_version_consistency()
        with connectable.connect() as connection:
            versions = connection.execute(
                sa.text(f'SELECT version_num FROM "{schema}".alembic_version_core ORDER BY version_num')
            ).scalars().all()
    finally:
        with connectable.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connectable.dispose()

    assert versions
    output = capsys.readouterr().out
    assert "mode selected = STAMP" in output


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
    monkeypatch.setenv("ALEMBIC_AUTO_REPAIR", "1")
    monkeypatch.setenv("APP_ENV", "dev")

    try:
        ensure_alembic_version_consistency()
    finally:
        with connectable.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connectable.dispose()

    output = capsys.readouterr().out
    assert "mode selected = UPGRADE" in output
