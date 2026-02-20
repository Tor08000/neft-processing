import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.scripts.alembic_version_repair import ensure_alembic_version_consistency
from app.tests.utils import ensure_connectable, get_database_url


@pytest.mark.skipif(get_database_url().startswith("sqlite"), reason="Postgres-only test")
def test_version_missing_with_non_empty_schema_fails_without_reset(monkeypatch):
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
    monkeypatch.setenv("DB_RESET_ON_VERSION_MISSING", "0")
    monkeypatch.setenv("APP_ENV", "dev")

    try:
        with pytest.raises(RuntimeError, match="alembic_version_missing_but_schema_not_empty"):
            ensure_alembic_version_consistency()
    finally:
        with connectable.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connectable.dispose()


@pytest.mark.skipif(get_database_url().startswith("sqlite"), reason="Postgres-only test")
def test_version_missing_with_non_empty_schema_resets_with_flag(monkeypatch):
    db_url = get_database_url()
    connectable = ensure_connectable(db_url)
    schema = f"version_repair_reset_{uuid.uuid4().hex[:8]}"

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
    monkeypatch.setenv("DB_RESET_ON_VERSION_MISSING", "1")
    monkeypatch.setenv("APP_ENV", "dev")

    try:
        ensure_alembic_version_consistency()
        with connectable.connect() as connection:
            clients_reg = connection.execute(
                sa.text("SELECT to_regclass(:reg)"), {"reg": f"{schema}.clients"}
            ).scalar_one()
            versions = connection.execute(
                sa.text(f'SELECT version_num FROM "{schema}".alembic_version_core')
            ).scalars().all()
    finally:
        with connectable.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connectable.dispose()

    assert clients_reg is None
    assert versions
