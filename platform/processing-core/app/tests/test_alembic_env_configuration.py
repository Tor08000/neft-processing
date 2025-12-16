import importlib
import logging
import sys

import pytest
from alembic import context


class DummyTransaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401,ARG002
        return False


class DummyConnection:
    def __init__(self):
        self.ensure_called = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401,ARG002
        return False


class DummyEngine:
    def __init__(self, connection: DummyConnection):
        self.connection = connection

    def connect(self):
        return self.connection


class DummyConfig:
    config_ini_section = "alembic"

    def __init__(self):
        self.config_file_name = None
        self.main_options: dict[str, str] = {}
        self.sections = {self.config_ini_section: {}}

    def get_section(self, name: str):
        return self.sections.get(name, {})

    def get_main_option(self, name: str):
        return self.main_options.get(name)

    def set_main_option(self, name: str, value: str):
        self.main_options[name] = value


@pytest.mark.usefixtures("clear_env_module")
@pytest.mark.usefixtures("restore_context")
def test_env_uses_database_url_and_online_path(monkeypatch, caplog):
    target_url = "postgresql+psycopg://user:supersecret@db:5432/neft"
    dummy_config = DummyConfig()
    dummy_connection = DummyConnection()
    configure_calls: dict[str, object] = {}

    monkeypatch.setenv("DATABASE_URL", target_url)
    monkeypatch.setattr(context, "config", dummy_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)
    monkeypatch.setattr(context, "begin_transaction", lambda: DummyTransaction(), raising=False)
    monkeypatch.setattr(context, "run_migrations", lambda: None, raising=False)

    def fake_engine_from_config(config_section, prefix, poolclass):  # noqa: ARG001
        return DummyEngine(dummy_connection)

    def fake_ensure_alembic_version_length(connection):
        connection.ensure_called = True

    def fake_configure(**kwargs):
        configure_calls.update(kwargs)

    caplog.set_level(logging.INFO, logger="app.alembic.env")

    monkeypatch.setattr("sqlalchemy.engine_from_config", fake_engine_from_config, raising=False)
    monkeypatch.setattr(
        "app.alembic.utils.ensure_alembic_version_length", fake_ensure_alembic_version_length
    )
    monkeypatch.setattr(context, "configure", fake_configure, raising=False)

    importlib.import_module("app.alembic.env")

    assert dummy_config.get_main_option("sqlalchemy.url") == target_url
    assert any("postgresql+psycopg://user:***@db:5432/neft" in message for message in caplog.messages)
    assert configure_calls.get("connection") is dummy_connection
    assert configure_calls.get("as_sql") is False
    assert dummy_connection.ensure_called is True


@pytest.fixture
def clear_env_module():
    yield
    sys.modules.pop("app.alembic.env", None)


@pytest.fixture
def restore_context():
    original_config = getattr(context, "config", None)
    original_offline_mode = context.is_offline_mode
    original_begin = context.begin_transaction
    original_run_migrations = context.run_migrations
    original_configure = context.configure
    yield
    if original_config is None:
        context.config = None
    else:
        context.config = original_config
    context.is_offline_mode = original_offline_mode
    context.begin_transaction = original_begin
    context.run_migrations = original_run_migrations
    context.configure = original_configure
