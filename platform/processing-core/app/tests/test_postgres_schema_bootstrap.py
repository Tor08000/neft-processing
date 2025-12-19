from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.db import DB_SCHEMA
from app.tests.utils import ensure_connectable, get_database_url

REQUIRED_RELATIONS = (
    "alembic_version",
    "operations",
    "accounts",
    "ledger_entries",
    "limit_configs",
)


def _make_alembic_config(db_url: str) -> Config:
    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(config_path.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.mark.integration
def test_postgres_upgrade_creates_core_relations() -> None:
    db_url = get_database_url()
    engine = ensure_connectable(db_url)

    if engine.dialect.name != "postgresql":
        pytest.skip("Postgres is required for this smoke test")

    alembic_cfg = _make_alembic_config(db_url)
    command.upgrade(alembic_cfg, "head")

    with engine.connect() as connection:
        connection.execute(sa.text("SET search_path TO :schema"), {"schema": DB_SCHEMA})
        search_path = connection.execute(sa.text("SHOW search_path")).scalar_one()
        regclasses = {
            relation: connection.execute(
                sa.text("select to_regclass(:reg)"),
                {"reg": f"{DB_SCHEMA}.{relation}"},
            ).scalar()
            for relation in REQUIRED_RELATIONS
        }

    missing = [name for name, reg in regclasses.items() if reg is None]
    assert not missing, (
        "required relations missing after alembic upgrade: "
        f"{missing}. search_path={search_path}"
    )
