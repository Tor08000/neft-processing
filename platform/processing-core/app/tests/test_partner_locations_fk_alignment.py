from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.tests.utils import ensure_connectable, get_database_url

TARGET_REVISION = "20299820_0185_partner_management_v1"
PREV_REVISION = "20299810_0184_event_outbox"


def _make_alembic_config(db_url: str) -> Config:
    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(config_path.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.mark.integration
def test_partner_locations_fk_matches_partners_id_type_for_legacy_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    schema = f"processing_core_partner_fk_{uuid4().hex[:8]}"
    db_url = get_database_url()
    monkeypatch.setenv("NEFT_DB_SCHEMA", schema)
    engine = ensure_connectable(db_url)

    if engine.dialect.name != "postgresql":
        pytest.skip("Postgres is required for FK alignment migration test")

    alembic_cfg = _make_alembic_config(db_url)

    command.upgrade(alembic_cfg, PREV_REVISION)

    with engine.begin() as connection:
        connection.execute(sa.text(f'ALTER TABLE "{schema}".partners ALTER COLUMN id TYPE text USING id::text'))

    command.upgrade(alembic_cfg, TARGET_REVISION)

    with engine.connect() as connection:
        partner_id_type = connection.execute(
            sa.text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = 'partners'
                  AND column_name = 'id'
                """
            ),
            {"schema": schema},
        ).scalar_one()
        location_partner_id_type = connection.execute(
            sa.text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = 'partner_locations'
                  AND column_name = 'partner_id'
                """
            ),
            {"schema": schema},
        ).scalar_one()
        fk_exists = connection.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace ns ON ns.oid = t.relnamespace
                WHERE ns.nspname = :schema
                  AND t.relname = 'partner_locations'
                  AND c.contype = 'f'
                  AND c.conname = 'partner_locations_partner_id_fkey'
                """
            ),
            {"schema": schema},
        ).scalar_one_or_none()

    assert location_partner_id_type == partner_id_type
    assert fk_exists == 1
