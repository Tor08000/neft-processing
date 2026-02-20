from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest
from alembic import context


class DummyConnection:
    def __init__(self, *, parallel_tables: list[tuple[str, str]] | None = None) -> None:
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed: list[tuple[str, dict | None]] = []
        self.parallel_tables = parallel_tables or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401,ARG002
        return False

    def execute(self, statement, params=None):  # noqa: D401,ARG002
        sql = str(statement)
        self.executed.append((sql, params))
        if "table_name LIKE 'alembic_version%'" in sql:
            return DummyResult(self.parallel_tables)
        return DummyResult()


class DummyResult:
    def __init__(self, rows=None) -> None:
        self._rows = rows or []

    def scalar_one_or_none(self):  # noqa: D401
        return None

    def scalar(self):  # noqa: D401
        return None

    def all(self):  # noqa: D401
        return self._rows


class DummyTransaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401,ARG002
        return False


class DummyEngine:
    def __init__(self, connection: DummyConnection):
        self.connection = connection
        self.disposed = False

    def connect(self):
        return self.connection

    def dispose(self):
        self.disposed = True


class DummyConfig:
    config_ini_section = "alembic"

    def __init__(self) -> None:
        self.config_file_name = None
        self.main_options: dict[str, str] = {}

    def get_section(self, name: str, default=None):
        return default or {}

    def get_main_option(self, name: str):
        return self.main_options.get(name)

    def set_main_option(self, name: str, value: str):
        self.main_options[name] = value


@pytest.fixture(autouse=True)
def restore_context():
    original_config = getattr(context, "config", None)
    original_offline_mode = context.is_offline_mode
    original_run_migrations = context.run_migrations
    original_configure = context.configure
    original_begin_transaction = context.begin_transaction
    original_get_x_argument = context.get_x_argument
    yield
    context.config = original_config
    context.is_offline_mode = original_offline_mode
    context.run_migrations = original_run_migrations
    context.configure = original_configure
    context.begin_transaction = original_begin_transaction
    context.get_x_argument = original_get_x_argument
    sys.modules.pop("app.alembic.env", None)


def test_env_configures_context(monkeypatch: pytest.MonkeyPatch):
    target_url = "postgresql+psycopg://user:secret@db:5432/neft"
    monkeypatch.setenv("DATABASE_URL", target_url)
    dummy_config = DummyConfig()
    dummy_connection = DummyConnection()
    configure_calls: dict[str, object] = {}

    monkeypatch.setattr(context, "config", dummy_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)
    monkeypatch.setattr(context, "get_x_argument", lambda as_dictionary=True: {})  # noqa: ARG005
    monkeypatch.setattr(context, "run_migrations", lambda: None, raising=False)
    monkeypatch.setattr(context, "configure", lambda **kwargs: configure_calls.update(kwargs), raising=False)
    monkeypatch.setattr(context, "begin_transaction", lambda: DummyTransaction(), raising=False)
    monkeypatch.setattr(sys, "argv", ["alembic", "upgrade", "head"])
    monkeypatch.setattr("sqlalchemy.engine_from_config", lambda section, **kwargs: DummyEngine(dummy_connection), raising=False)

    env = importlib.import_module("app.alembic.env")
    env.run_migrations_online()

    assert dummy_config.get_main_option("sqlalchemy.url") == target_url
    assert configure_calls["connection"] is dummy_connection
    assert configure_calls["include_schemas"] is True
    assert configure_calls["version_table"] == "alembic_version_core"
    assert configure_calls["version_table_schema"] == "processing_core"
    assert configure_calls["transaction_per_migration"] is True
    assert any("SET search_path TO" in sql for sql, _ in dummy_connection.executed)


def test_env_requires_database_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(context, "config", DummyConfig(), raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)

    with pytest.raises(RuntimeError):
        importlib.import_module("app.alembic.env")


def test_env_rejects_parallel_alembic_tables(monkeypatch: pytest.MonkeyPatch):
    target_url = "postgresql+psycopg://user:secret@db:5432/neft"
    monkeypatch.setenv("DATABASE_URL", target_url)
    dummy_config = DummyConfig()
    dummy_connection = DummyConnection(parallel_tables=[("public", "alembic_version")])

    monkeypatch.setattr(context, "config", dummy_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)
    monkeypatch.setattr(context, "get_x_argument", lambda as_dictionary=True: {})  # noqa: ARG005
    monkeypatch.setattr(context, "run_migrations", lambda: None, raising=False)
    monkeypatch.setattr(context, "configure", lambda **kwargs: None, raising=False)
    monkeypatch.setattr(context, "begin_transaction", lambda: DummyTransaction(), raising=False)
    monkeypatch.setattr(sys, "argv", ["alembic", "upgrade", "head"])
    monkeypatch.setattr("sqlalchemy.engine_from_config", lambda section, **kwargs: DummyEngine(dummy_connection), raising=False)

    with pytest.raises(RuntimeError, match="parallel Alembic version tables"):
        importlib.import_module("app.alembic.env")
