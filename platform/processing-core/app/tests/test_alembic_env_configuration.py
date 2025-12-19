from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest
from alembic import context


class DummyConnection:
    def __init__(self) -> None:
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed: list[tuple[str, dict | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401,ARG002
        return False

    def execute(self, statement, params=None):  # noqa: D401,ARG002
        self.executed.append((str(statement), params))
        return DummyResult()


class DummyResult:
    def scalar_one_or_none(self):  # noqa: D401
        return None


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
    monkeypatch.setattr("sqlalchemy.create_engine", lambda url, **kwargs: DummyEngine(dummy_connection), raising=False)

    env = importlib.import_module("app.alembic.env")
    env.run_migrations_online()

    assert dummy_config.get_main_option("sqlalchemy.url") == target_url
    assert configure_calls["connection"] is dummy_connection
    assert configure_calls["include_schemas"] is True
    assert configure_calls["version_table_schema"] == "public"
    assert any("SET search_path TO" in sql for sql, _ in dummy_connection.executed)


def test_env_requires_database_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(context, "config", DummyConfig(), raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)

    with pytest.raises(RuntimeError):
        importlib.import_module("app.alembic.env")
