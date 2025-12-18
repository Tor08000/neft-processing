import contextlib
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

from app.diagnostics import db_state

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


def _make_alembic_config(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@contextlib.contextmanager
def _postgres_container(image: str):
    container_name = f"neft-processing-it-{uuid4().hex[:8]}"
    port = _free_port()

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
    except subprocess.CalledProcessError as exc:  # pragma: no cover - docker failure path
        raise RuntimeError(f"docker failed to start postgres: {exc.stderr.decode(errors='ignore')}") from exc

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
        else:  # pragma: no cover - defensive skip path
            raise RuntimeError(f"postgres test container did not become ready: {last_error}")

        yield db_url
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], check=False)


def _upgrade_and_inventory(db_url: str, schema: str, monkeypatch: pytest.MonkeyPatch) -> dict[str, str | None]:
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DB_SCHEMA", schema)

    cfg = _make_alembic_config(db_url)

    command.upgrade(cfg, "head")

    with sa.create_engine(db_url, future=True, pool_pre_ping=True).connect() as conn:
        regclasses = {table: db_state.to_regclass(conn, schema, table) for table in REQUIRED_TABLES}
        spillover_schema = "public" if schema != "public" else "nonexistent"
        spillover = {
            table: db_state.to_regclass(conn, spillover_schema, table) for table in REQUIRED_TABLES
        }

    return {**regclasses, **{f"{name}_spillover": value for name, value in spillover.items()}}


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required for this integration test")
def test_upgrade_creates_public_tables_via_docker(monkeypatch):
    image = os.getenv("TEST_POSTGRES_IMAGE", "postgres:16")

    try:
        with _postgres_container(image) as db_url:
            results = _upgrade_and_inventory(db_url, "public", monkeypatch)
    except RuntimeError as exc:
        pytest.skip(str(exc))

    missing = [name for name in REQUIRED_TABLES if results[name] is None]
    spillover = [name for name in REQUIRED_TABLES if results.get(f"{name}_spillover") is not None]

    assert not missing, f"tables missing in public schema: {missing}"
    assert not spillover, f"tables unexpectedly found outside public schema: {spillover}"


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required for this integration test")
def test_upgrade_respects_custom_schema(monkeypatch):
    image = os.getenv("TEST_POSTGRES_IMAGE", "postgres:16")
    schema = f"core_{uuid4().hex[:6]}"

    try:
        with _postgres_container(image) as db_url:
            results = _upgrade_and_inventory(db_url, schema, monkeypatch)
    except RuntimeError as exc:
        pytest.skip(str(exc))

    missing = [name for name in REQUIRED_TABLES if results[name] is None]
    in_public = [name for name in REQUIRED_TABLES if results.get(f"{name}_spillover") is not None]

    assert not missing, f"tables missing in schema {schema}: {missing}"
    assert not in_public, f"tables should not be created in public when schema={schema}: {in_public}"
