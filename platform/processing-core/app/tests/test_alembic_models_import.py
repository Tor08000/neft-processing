import importlib
import sys

import pytest


@pytest.mark.usefixtures("clear_env_module")
@pytest.mark.usefixtures("restore_context")
def test_env_import_registers_models_once(monkeypatch):
    from alembic import context

    dummy_config = type(
        "DummyConfig",
        (),
        {
            "config_ini_section": "alembic",
            "config_file_name": None,
            "get_section": lambda self, name: {},
            "get_main_option": lambda self, name: None,
            "set_main_option": lambda self, name, value: None,
        },
    )()

    monkeypatch.setattr(context, "config", dummy_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)
    monkeypatch.setattr(context, "run_migrations", lambda: None, raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ALEMBIC_SKIP_RUN", "1")
    sys.modules.pop("app.alembic.env", None)

    env = importlib.import_module("app.alembic.env")

    assert env.Base.metadata.tables, "Metadata should not be empty after env import"
    assert "client_groups" in env.Base.metadata.tables
    assert not any(
        name == "models" or name.startswith("models.") for name in sys.modules
    ), "Unexpected models.* aliases detected"


@pytest.fixture
def clear_env_module():
    yield
    sys.modules.pop("app.alembic.env", None)


@pytest.fixture
def restore_context():
    from alembic import context

    original_config = getattr(context, "config", None)
    original_offline_mode = context.is_offline_mode
    original_run_migrations = context.run_migrations
    original_configure = context.configure
    yield
    if original_config is None:
        context.config = None
    else:
        context.config = original_config
    context.is_offline_mode = original_offline_mode
    context.run_migrations = original_run_migrations
    context.configure = original_configure
