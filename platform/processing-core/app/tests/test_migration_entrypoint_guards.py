import os
import subprocess
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.schema import SCHEMA_RESOLUTION
from app.tests.utils import ensure_connectable, get_database_url

REQUIRED_TABLES = (
    "alembic_version_core",
    "operations",
    "accounts",
    "ledger_entries",
    "limit_configs",
)


def _render_alembic_config(database_url: str) -> Config:
    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.mark.skipif(
    get_database_url().startswith("sqlite"), reason="Smoke test requires Postgres"
)
@pytest.mark.integration
def test_upgrade_creates_required_tables():
    db_url = get_database_url()
    connectable = ensure_connectable(db_url)

    cfg = _render_alembic_config(db_url)
    script_heads = set(ScriptDirectory.from_config(cfg).get_heads())

    try:
        command.upgrade(cfg, "head")
        with connectable.connect() as connection:
            version_reg = connection.execute(
                sa.text("select to_regclass(:reg)"),
                {"reg": f"{SCHEMA_RESOLUTION.schema}.alembic_version_core"},
            ).scalar()
            missing = [
                table
                for table in REQUIRED_TABLES
                if connection.execute(
                    sa.text("select to_regclass(:reg)"), {"reg": f"{SCHEMA_RESOLUTION.schema}.{table}"}
                ).scalar()
                is None
            ]
            versions = (
                connection.execute(
                    sa.text(
                        f'SELECT version_num FROM "{SCHEMA_RESOLUTION.schema}".alembic_version_core'
                    )
                )
                .scalars()
                .all()
                if version_reg
                else []
            )
    finally:
        connectable.dispose()

    assert version_reg, "alembic_version_core table was not created by upgrade"
    assert (
        set(versions) == script_heads
    ), f"alembic_version_core contents mismatch: {versions} != {script_heads}"
    assert not missing, f"Required tables are missing after upgrade: {missing}"


@pytest.mark.skipif(
    get_database_url().startswith("sqlite"), reason="Smoke test requires Postgres"
)
def test_entrypoint_rejects_missing_version_table(tmp_path):
    db_url = get_database_url()
    connectable = ensure_connectable(db_url)
    schema = "entrypoint_guard"

    with connectable.begin() as connection:
        connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "alembic"
    stub.write_text(
        "#!/usr/bin/env sh\n"
        "case \"$1\" in\n"
        "  heads)\n"
        "    echo \"dummy_head\"\n"
        "    exit 0\n"
        "    ;;\n"
        "  *)\n"
        "    exit 0\n"
        "    ;;\n"
        "esac\n"
    )
    stub.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": db_url,
            "NEFT_DB_SCHEMA": schema,
            "ALEMBIC_CONFIG": "app/alembic.ini",
            "ENTRYPOINT_SKIP_APP": "1",
            "PATH": f"{bin_dir}:{env.get('PATH', '')}",
        }
    )

    result = subprocess.run(
        ["sh", str(Path(__file__).parents[2] / "entrypoint.sh")],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert "required tables missing after migrations" in result.stderr

    connectable.dispose()


@pytest.mark.skipif(
    get_database_url().startswith("sqlite"), reason="Smoke test requires Postgres"
)
@pytest.mark.integration
def test_entrypoint_smoke_empty_schema(tmp_path):
    db_url = get_database_url()
    connectable = ensure_connectable(db_url)
    schema = f"entrypoint_smoke_{uuid.uuid4().hex[:8]}"

    with connectable.begin() as connection:
        connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": db_url,
            "NEFT_DB_SCHEMA": schema,
            "ALEMBIC_CONFIG": "app/alembic.ini",
            "ENTRYPOINT_SKIP_APP": "1",
        }
    )

    try:
        result = subprocess.run(
            ["sh", str(Path(__file__).parents[2] / "entrypoint.sh")],
            capture_output=True,
            text=True,
            env=env,
        )
    finally:
        with connectable.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connectable.dispose()

    assert result.returncode == 0, result.stdout + result.stderr
