import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

REQUIRED_TABLES = (
    "alembic_version",
    "operations",
    "accounts",
    "ledger_entries",
    "limit_configs",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required for this integration test")
def test_upgrade_creates_public_tables_via_docker(monkeypatch):
    container_name = f"neft-processing-it-{uuid4().hex[:8]}"
    port = _free_port()
    image = os.getenv("TEST_POSTGRES_IMAGE", "postgres:16")

    try:
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                container_name,
                "-e",
                "POSTGRES_PASSWORD=neft",
                "-e",
                "POSTGRES_USER=neft",
                "-e",
                "POSTGRES_DB=neft",
                "-p",
                f"{port}:5432",
                image,
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"docker failed to start postgres: {exc.stderr.decode(errors='ignore')}")

    db_url = f"postgresql+psycopg://neft:neft@localhost:{port}/neft"

    try:
        deadline = time.time() + 60
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                engine = sa.create_engine(db_url, future=True, pool_pre_ping=True)
                with engine.connect() as conn:
                    conn.exec_driver_sql("select 1")
                break
            except Exception as exc:  # noqa: BLE001 - integration wait loop
                last_error = exc
                time.sleep(1)
        else:
            pytest.skip(f"postgres test container did not become ready: {last_error}")

        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("DB_SCHEMA", "public")

        cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", db_url)

        command.upgrade(cfg, "head")

        with sa.create_engine(db_url, future=True, pool_pre_ping=True).connect() as conn:
            missing = {
                table: conn.exec_driver_sql("select to_regclass(:reg)", {"reg": f"public.{table}"}).scalar()
                for table in REQUIRED_TABLES
            }
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], check=False)

    assert all(missing.values()), f"tables missing in public schema: {sorted(table for table, reg in missing.items() if reg is None)}"
