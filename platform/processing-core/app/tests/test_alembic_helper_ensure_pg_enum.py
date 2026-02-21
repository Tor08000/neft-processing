from __future__ import annotations

from types import SimpleNamespace

from app.alembic import helpers


class _Bind:
    def __init__(self) -> None:
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed_sql: list[str] = []

    def exec_driver_sql(self, sql: str) -> None:
        self.executed_sql.append(sql)


def test_ensure_pg_enum_handles_create_type_race_conditions() -> None:
    bind = _Bind()

    helpers.ensure_pg_enum(
        bind,
        enum_name="accounttype",
        values=["CLIENT_MAIN", "CLIENT_CREDIT", "CARD_LIMIT", "TECHNICAL"],
        schema="processing_core",
    )

    assert bind.executed_sql
    sql = bind.executed_sql[0]
    assert 'CREATE TYPE "processing_core"."accounttype" AS ENUM' in sql
    assert "WHEN duplicate_object OR unique_violation THEN" in sql
    assert "IF NOT EXISTS" not in sql
