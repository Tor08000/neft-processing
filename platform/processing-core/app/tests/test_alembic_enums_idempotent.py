from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.db import DB_SCHEMA
from app.tests.utils import ensure_connectable, get_database_url

POSTING_BATCH_ENUM = "postingbatchtype"
POSTING_BATCH_VALUES = [
    "AUTH",
    "HOLD",
    "COMMIT",
    "CAPTURE",
    "REFUND",
    "REVERSAL",
    "ADJUSTMENT",
    "DISPUTE_HOLD",
    "DISPUTE_RELEASE",
]


def _make_alembic_config(db_url: str) -> Config:
    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(config_path.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.mark.integration
def test_alembic_upgrade_is_idempotent_and_preserves_enums() -> None:
    db_url = get_database_url()
    engine = ensure_connectable(db_url)
    if engine.dialect.name != "postgresql":
        pytest.skip("Postgres is required for end-to-end Alembic idempotence")
    alembic_cfg = _make_alembic_config(db_url)

    command.upgrade(alembic_cfg, "head")
    command.upgrade(alembic_cfg, "head")

    with engine.connect() as connection:
        connection.execute(sa.text("SET search_path TO :schema"), {"schema": DB_SCHEMA})
        enum_count = connection.execute(
            sa.text(
                """
                SELECT count(*)
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = :schema AND t.typname = :enum_name
                """
            ),
            {"schema": DB_SCHEMA, "enum_name": POSTING_BATCH_ENUM},
        ).scalar_one()
        assert enum_count == 1

        labels = connection.execute(
            sa.text(
                """
                SELECT e.enumlabel
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = :schema AND t.typname = :enum_name
                ORDER BY e.enumsortorder
                """
            ),
            {"schema": DB_SCHEMA, "enum_name": POSTING_BATCH_ENUM},
        ).scalars().all()

        assert set(labels) == set(POSTING_BATCH_VALUES)
        assert len(labels) == len(set(POSTING_BATCH_VALUES))
