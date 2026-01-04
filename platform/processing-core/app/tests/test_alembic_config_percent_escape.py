from alembic.config import Config

from .conftest import _escape_alembic_cfg_percent


def test_escape_alembic_config_percent_allows_percent_encoded_url() -> None:
    url = "postgresql://user:pass@host/db?options=-c%20search_path%3Dfoo"
    escaped = _escape_alembic_cfg_percent(url)

    assert "%3D" in url
    assert "%%3D" in escaped

    cfg = Config()
    cfg.set_main_option("sqlalchemy.url", escaped)

    assert cfg.get_main_option("sqlalchemy.url") == url
