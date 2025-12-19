import contextlib
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import io

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db import get_engine, get_sessionmaker, reset_engine
from app.diagnostics import db_state
from app.models.card import Card
from app.services.bootstrap import ensure_default_refs

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
                engine = sa.create_engine(
                    db_url,
                    future=True,
                    pool_pre_ping=True,
                    connect_args={"prepare_threshold": 0},
                )
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
    monkeypatch.setenv("NEFT_DB_SCHEMA", schema)

    cfg = _make_alembic_config(db_url)
    script_heads = set(ScriptDirectory.from_config(cfg).get_heads())

    command.upgrade(cfg, "head")

    engine = sa.create_engine(
        db_url, future=True, pool_pre_ping=True, connect_args={"prepare_threshold": 0}
    )
    try:
        with engine.connect() as conn:
            regclasses = {table: db_state.to_regclass(conn, schema, table) for table in REQUIRED_TABLES}
            spillover_schema = "public" if schema != "public" else "nonexistent"
            spillover = {
                table: db_state.to_regclass(conn, spillover_schema, table) for table in REQUIRED_TABLES
            }
            version_values = (
                conn.execute(sa.text(f'SELECT version_num FROM "{schema}".alembic_version')).scalars().all()
                if regclasses.get("alembic_version")
                else []
            )
            cards_created = (
                conn.execute(
                    sa.text(
                        """
                        select 1
                        from information_schema.columns
                        where table_schema=:schema
                          and table_name='cards'
                          and column_name='created_at'
                        """
                    ),
                    {"schema": schema},
                ).scalar_one_or_none()
                is not None
            )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            command.current(cfg)
        current_output = buf.getvalue()
    finally:
        engine.dispose()

    return {
        "regclasses": regclasses,
        "spillover": spillover,
        "version_values": version_values,
        "script_heads": script_heads,
        "current_output": current_output,
        "cards_created": cards_created,
    }


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required for this integration test")
def test_upgrade_creates_public_tables_via_docker(monkeypatch):
    image = os.getenv("TEST_POSTGRES_IMAGE", "postgres:16")

    try:
        with _postgres_container(image) as db_url:
            results = _upgrade_and_inventory(db_url, "public", monkeypatch)
    except RuntimeError as exc:
        pytest.skip(str(exc))

    regclasses = results["regclasses"]
    missing = [name for name in REQUIRED_TABLES if regclasses[name] is None]
    spillover = [name for name in REQUIRED_TABLES if results["spillover"].get(name) is not None]

    assert not missing, f"tables missing in public schema: {missing}"
    assert not spillover, f"tables unexpectedly found outside public schema: {spillover}"
    assert set(results["version_values"]) == results["script_heads"]
    for head in results["script_heads"]:
        assert head in results["current_output"]
    assert results["cards_created"], "cards.created_at should exist after migrations"


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

    regclasses = results["regclasses"]
    missing = [name for name in REQUIRED_TABLES if regclasses[name] is None]
    in_public = [name for name in REQUIRED_TABLES if results["spillover"].get(name) is not None]

    assert not missing, f"tables missing in schema {schema}: {missing}"
    assert not in_public, f"tables should not be created in public when schema={schema}: {in_public}"
    assert set(results["version_values"]) == results["script_heads"]
    for head in results["script_heads"]:
        assert head in results["current_output"]
    assert results["cards_created"]


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required for this integration test")
def test_upgrade_places_version_table_in_target_schema(monkeypatch):
    image = os.getenv("TEST_POSTGRES_IMAGE", "postgres:16")
    target_schema = f"core_{uuid4().hex[:6]}"
    expected_revision = "20270720_0029_cards_created_at"

    try:
        with _postgres_container(image) as db_url:
            monkeypatch.setenv("DATABASE_URL", db_url)
            monkeypatch.setenv("NEFT_DB_SCHEMA", target_schema)

            cfg = _make_alembic_config(db_url)
            command.upgrade(cfg, "head")

            engine = sa.create_engine(
                db_url,
                future=True,
                pool_pre_ping=True,
                connect_args={"prepare_threshold": 0},
            )

            with engine.connect() as conn:
                version_schemas = conn.execute(
                    sa.text(
                        """
                        select table_schema
                        from information_schema.tables
                        where table_name='alembic_version'
                        order by table_schema
                        """
                    )
                ).scalars().all()
                version = conn.execute(
                    sa.text(f'SELECT version_num FROM "{target_schema}".alembic_version')
                ).scalar_one()

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                command.current(cfg)
            current_output = buf.getvalue()
    except RuntimeError as exc:
        pytest.skip(str(exc))

    assert version_schemas == [target_schema]
    assert version == expected_revision
    assert expected_revision in current_output


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required for this integration test")
def test_engine_reset_after_migrations(monkeypatch):
    image = os.getenv("TEST_POSTGRES_IMAGE", "postgres:16")
    schema = f"core_{uuid4().hex[:6]}"

    try:
        with _postgres_container(image) as db_url:
            monkeypatch.setenv("DATABASE_URL", db_url)
            monkeypatch.setenv("NEFT_DB_SCHEMA", schema)

            warm_engine = get_engine()
            with warm_engine.connect() as conn:
                conn.exec_driver_sql("select 1")

            get_sessionmaker()

            cfg = _make_alembic_config(db_url)
            command.upgrade(cfg, "head")

            reset_engine()

            session_factory = get_sessionmaker()
            with session_factory() as session:
                ensure_default_refs(session)
                card = session.query(Card).filter(Card.id == "CARD-001").one()
                assert card.created_at is not None
    except RuntimeError as exc:
        pytest.skip(str(exc))
