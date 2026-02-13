from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError


@pytest.mark.parametrize("schema", [None])
def test_geo_metrics_migration_creates_table_and_unique(schema) -> None:
    migration = importlib.import_module("app.alembic.versions.20299670_0176_geo_station_metrics_daily")
    engine = create_engine("sqlite://")

    with engine.begin() as connection:
        ctx = MigrationContext.configure(connection)
        operations = Operations(ctx)

        migration.op = operations
        migration.DB_SCHEMA = schema
        migration.upgrade()

        insp = sa.inspect(connection)
        assert "geo_station_metrics_daily" in insp.get_table_names()

        connection.execute(
            sa.text(
                """
                INSERT INTO geo_station_metrics_daily(day, station_id, tx_count, captured_count, declined_count, amount_sum, liters_sum, risk_red_count, risk_yellow_count)
                VALUES ('2026-02-12', 'station-1', 1, 1, 0, 100.00, 10.0, 0, 0)
                """
            )
        )

        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO geo_station_metrics_daily(day, station_id, tx_count, captured_count, declined_count, amount_sum, liters_sum, risk_red_count, risk_yellow_count)
                    VALUES ('2026-02-12', 'station-1', 2, 1, 1, 150.00, 12.0, 0, 0)
                    """
                )
            )
