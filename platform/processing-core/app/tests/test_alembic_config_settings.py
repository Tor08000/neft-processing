from pathlib import Path

from alembic.config import Config


def test_alembic_config_includes_version_table_settings():
    config_path = Path(__file__).parents[1] / "alembic.ini"
    cfg = Config(str(config_path))

    assert cfg.get_main_option("version_table") == "alembic_version_core"
    assert cfg.get_main_option("version_table_schema") == "processing_core"
