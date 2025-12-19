import importlib
import logging
import sys
from types import SimpleNamespace

import pytest
from alembic import context


class DummyConnection:
    def __init__(self):
        self.ensure_called = False
        self.begin_called = False
        self.executed_sql: list[str] = []
        self.dialect = SimpleNamespace(name="postgresql")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401,ARG002
        return False

    def begin(self):
        return DummyTransaction(self)

    def exec_driver_sql(self, statement, params=None):  # noqa: D401,ARG002
        self.executed_sql.append(statement)
        return DummyResult(statement)

    def execute(self, statement, params=None):  # noqa: D401,ARG002
        sql = str(statement)
        self.executed_sql.append(sql)
        return DummyResult(sql)


class DummyResult:
    def __init__(self, statement: str):
        self.statement = statement

    def one(self):
        if "txid_current()" in self.statement and "pg_backend_pid()" in self.statement:
            return ("txid", "pid")
        if (
            "inet_server_addr()" in self.statement
            and "inet_server_port()" in self.statement
            and "current_database()" not in self.statement
        ):
            return ("127.0.0.1", 5432)
        if "current_database(), current_user" in self.statement and "inet_server_addr" in self.statement:
            return ("neft", "dummy_user", "127.0.0.1", 5432, "public")
        if "current_database(), current_user" in self.statement:
            return ("neft", "dummy_user")
        if "current_schema" in self.statement and "current_setting('search_path')" in self.statement:
            return ("public", "public")
        if "inet_server_addr()" in self.statement:
            return ("127.0.0.1", 5432, "neft", "dummy_user", "public")
        return ("neft",)

    def first(self):
        return ("127.0.0.1", 5432, "neft", "dummy_user", "public")

    def scalar_one(self):
        if "SHOW search_path" in self.statement:
            return "public"
        return "dummy-scalar"

    def scalar_one_or_none(self):
        if "SHOW search_path" in self.statement:
            return "public"
        return None

    def one_or_none(self):
        return None

    def __iter__(self):
        return iter([])

    def scalars(self):
        return self

    def all(self):
        return []

    def fetchall(self):
        return []


class DummyTransaction:
    def __init__(self, connection: DummyConnection):
        self.connection = connection

    def __enter__(self):
        self.connection.begin_called = True
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401,ARG002
        return False


class DummyEngine:
    def __init__(self, connection: DummyConnection):
        self.connection = connection

    def connect(self):
        return self.connection


class DummyMigrationContext:
    def __init__(self):
        self.ensure_called = False
        self.has_version_table = False
        self.configure_opts: dict | None = None
        self.connection = None

    def _has_version_table(self):
        return self.has_version_table

    def _ensure_version_table(self):
        self.ensure_called = True


class DummyConfig:
    config_ini_section = "alembic"

    def __init__(self):
        self.config_file_name = None
        self.main_options: dict[str, str] = {}
        self.sections = {self.config_ini_section: {}}
        self.cmd_opts = None

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
    migration_context = DummyMigrationContext()
    configure_calls: dict[str, object] = {}

    monkeypatch.setenv("DATABASE_URL", target_url)
    monkeypatch.setattr(context, "config", dummy_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)
    monkeypatch.setattr(context, "get_x_argument", lambda as_dictionary=True: {})  # noqa: ARG005
    monkeypatch.setattr(context, "script", SimpleNamespace(get_heads=lambda: ["head"]), raising=False)
    monkeypatch.setattr(context, "run_migrations", lambda: None, raising=False)

    def fake_engine_from_config(config_section, prefix, poolclass):  # noqa: ARG001
        return DummyEngine(dummy_connection)

    def fake_ensure_alembic_version_length(connection):
        connection.ensure_called = True

    def fake_configure(**kwargs):
        configure_calls.update(kwargs)

    def fake_migration_context_configure(connection, opts):  # noqa: ARG002
        migration_context.connection = connection
        migration_context.configure_opts = opts
        return migration_context

    class DummyInspector:
        def __init__(self, connection: DummyConnection):
            self.connection = connection

        def get_table_names(self, schema=None):  # noqa: ARG002
            return ["alembic_version"]

    caplog.set_level(logging.INFO, logger="app.alembic.env")

    monkeypatch.setattr("sqlalchemy.engine_from_config", fake_engine_from_config, raising=False)
    monkeypatch.setattr("sqlalchemy.event.listen", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.alembic.utils.ensure_alembic_version_length", fake_ensure_alembic_version_length
    )
    monkeypatch.setattr("alembic.runtime.migration.MigrationContext.configure", fake_migration_context_configure)
    monkeypatch.setattr("alembic.context.configure", fake_configure)
    monkeypatch.setattr("alembic.context.begin_transaction", lambda: DummyTransaction(dummy_connection))
    monkeypatch.setattr("sqlalchemy.inspect", lambda conn: DummyInspector(conn), raising=False)

    importlib.import_module("app.alembic.env")

    assert dummy_config.get_main_option("sqlalchemy.url") == target_url
    assert any("postgresql+psycopg://user:***@db:5432/neft" in message for message in caplog.messages)
    assert configure_calls.get("connection") is dummy_connection
    assert configure_calls.get("as_sql") is False
    assert configure_calls.get("version_table") == "alembic_version"
    assert configure_calls.get("version_table_schema") == "public"
    assert configure_calls.get("include_schemas") is True
    assert any("connected to db=neft user=dummy_user schema=public" in message for message in caplog.messages)
    assert any("Set search_path for migrations to" in message for message in caplog.messages)
    assert dummy_connection.executed_sql[0].startswith("SELECT current_database()")
    assert any(sql.startswith("SET search_path TO") for sql in dummy_connection.executed_sql)
    assert dummy_connection.ensure_called is True
    assert dummy_connection.begin_called is True


@pytest.mark.usefixtures("clear_env_module")
@pytest.mark.usefixtures("restore_context")
def test_env_fails_if_version_table_missing(monkeypatch):
    dummy_config = DummyConfig()
    dummy_connection = DummyConnection()
    migration_context = DummyMigrationContext()

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:supersecret@db:5432/neft")
    monkeypatch.setattr(context, "config", dummy_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)
    monkeypatch.setattr(context, "get_x_argument", lambda as_dictionary=True: {})  # noqa: ARG005
    monkeypatch.setattr(context, "script", SimpleNamespace(get_heads=lambda: ["head"]), raising=False)
    monkeypatch.setattr(context, "run_migrations", lambda: None, raising=False)

    def fake_engine_from_config(config_section, prefix, poolclass):  # noqa: ARG001
        return DummyEngine(dummy_connection)

    def fake_ensure_alembic_version_length(connection):  # noqa: ARG001
        connection.ensure_called = True

    def fake_configure(**kwargs):  # noqa: ARG001
        return None

    def fake_migration_context_configure(connection, opts):  # noqa: ARG002
        migration_context.connection = connection
        migration_context.configure_opts = opts
        return migration_context

    monkeypatch.setattr("sqlalchemy.engine_from_config", fake_engine_from_config, raising=False)
    monkeypatch.setattr("sqlalchemy.event.listen", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.alembic.utils.ensure_alembic_version_length", fake_ensure_alembic_version_length
    )
    monkeypatch.setattr(
        "app.diagnostics.db_state.to_regclass", lambda _conn, _schema, name: _schema if name == "operations" else None
    )
    monkeypatch.setattr("alembic.runtime.migration.MigrationContext.configure", fake_migration_context_configure)
    monkeypatch.setattr(
        "sqlalchemy.inspect", lambda conn: SimpleNamespace(get_table_names=lambda schema=None: [])
    )
    monkeypatch.setattr("alembic.context.configure", fake_configure, raising=False)
    monkeypatch.setattr("alembic.context.begin_transaction", lambda: DummyTransaction(dummy_connection))

    with pytest.raises(RuntimeError):
        importlib.import_module("app.alembic.env")


@pytest.mark.usefixtures("clear_env_module")
@pytest.mark.usefixtures("restore_context")
def test_env_requires_database_url(monkeypatch):
    dummy_config = DummyConfig()

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(context, "config", dummy_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)

    with pytest.raises(RuntimeError):
        importlib.import_module("app.alembic.env")


@pytest.fixture
def clear_env_module():
    yield
    sys.modules.pop("app.alembic.env", None)


@pytest.fixture
def restore_context():
    original_config = getattr(context, "config", None)
    original_offline_mode = context.is_offline_mode
    original_run_migrations = context.run_migrations
    original_configure = context.configure
    original_script = getattr(context, "script", None)
    yield
    if original_config is None:
        context.config = None
    else:
        context.config = original_config
    context.is_offline_mode = original_offline_mode
    context.run_migrations = original_run_migrations
    context.configure = original_configure
    if original_script is None:
        context.script = None
    else:
        context.script = original_script


@pytest.mark.usefixtures("clear_env_module")
@pytest.mark.usefixtures("restore_context")
def test_env_uses_execute_for_parameterized_sql(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:supersecret@db:5432/neft")
    monkeypatch.setenv("ALEMBIC_SKIP_RUN", "1")
    monkeypatch.setattr(context, "config", DummyConfig(), raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)
    monkeypatch.setattr(context, "get_x_argument", lambda as_dictionary=True: {})  # noqa: ARG005

    importlib.import_module("app.alembic.env")
    from app.alembic import env  # noqa: WPS433

    class GuardResult:
        def __init__(self, statement: str):
            self.statement = statement

        def scalar_one_or_none(self):
            if "information_schema.columns" in self.statement:
                return 1
            if "information_schema.tables" in self.statement:
                return 3
            return None

        def scalar_one(self):
            if "information_schema.tables" in self.statement:
                return 3
            raise AssertionError(f"Unexpected scalar_one call for {self.statement}")

    class GuardConnection(DummyConnection):
        def __init__(self):
            super().__init__()
            self.execute_calls: list[tuple[str, dict | None]] = []

        def exec_driver_sql(self, statement, params=None):  # noqa: D401,ARG002
            if params and ":" in statement:
                raise AssertionError("exec_driver_sql should not receive params for bind statements")
            return super().exec_driver_sql(statement, params=params)

        def execute(self, statement, params=None):  # noqa: D401,ARG002
            sql = str(statement)
            self.execute_calls.append((sql, params))
            return GuardResult(sql)

    connection = GuardConnection()

    operations_regclass = env.regclass(connection, "public.operations")
    table_count = env._schema_table_count(connection, "public")  # noqa: SLF001

    assert operations_regclass is None
    assert table_count == 3
    assert connection.executed_sql == []
    assert len(connection.execute_calls) == 2


@pytest.mark.usefixtures("clear_env_module")
@pytest.mark.usefixtures("restore_context")
def test_env_rejects_exec_driver_sql_with_params(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:supersecret@db:5432/neft")
    monkeypatch.setenv("ALEMBIC_SKIP_RUN", "1")
    dummy_config = DummyConfig()
    monkeypatch.setattr(context, "config", dummy_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)
    monkeypatch.setattr(context, "get_x_argument", lambda as_dictionary=True: {})  # noqa: ARG005
    monkeypatch.setattr(context, "script", SimpleNamespace(get_heads=lambda: ["head"]), raising=False)
    monkeypatch.setattr(context, "run_migrations", lambda: None, raising=False)

    class GuardConnection(DummyConnection):
        def exec_driver_sql(self, statement, params=None):  # noqa: D401,ARG002
            if params is not None:
                raise AssertionError("exec_driver_sql should not receive params")
            if ":" in str(statement):
                raise AssertionError("exec_driver_sql should not handle bound parameter placeholders")
            return super().exec_driver_sql(statement, params=params)

    guard_connection = GuardConnection()

    monkeypatch.setattr("sqlalchemy.engine_from_config", lambda *_args, **_kwargs: DummyEngine(guard_connection))
    monkeypatch.setattr("sqlalchemy.event.listen", lambda *args, **kwargs: None)
    monkeypatch.setattr("alembic.context.configure", lambda **kwargs: None)
    monkeypatch.setattr("alembic.context.begin_transaction", lambda: DummyTransaction(guard_connection))
    monkeypatch.setattr("app.alembic.utils.ensure_alembic_version_length", lambda connection: None)

    import app.alembic.env as env  # noqa: WPS433

    env.run_migrations_online()
