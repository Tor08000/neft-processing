from __future__ import annotations

from types import SimpleNamespace

import pytest
from psycopg import errors as psycopg_errors
from sqlalchemy.exc import ProgrammingError

from app.alembic import helpers


class _Result:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _Bind:
    def __init__(self, *, row=None):
        self.dialect = SimpleNamespace(name="postgresql")
        self._row = row
        self.op_override = SimpleNamespace(create_index=self._create_index)
        self.create_called = False
        self.last_query = None
        self.last_params = None
        self.raise_on_create: Exception | None = None

    def execute(self, query, params):
        self.last_query = str(query)
        self.last_params = params
        return _Result(self._row)

    def _create_index(self, *_args, **_kwargs):
        self.create_called = True
        if self.raise_on_create is not None:
            raise self.raise_on_create


def test_create_index_if_not_exists_checks_pg_catalog_with_schema_and_relkind():
    bind = _Bind(row=(1,))

    helpers.create_index_if_not_exists(
        bind,
        "ix_dispute_events_dispute_id_created_at",
        "dispute_events",
        ["dispute_id", "created_at"],
        schema="processing_core",
    )

    assert "FROM pg_class c" in bind.last_query
    assert "JOIN pg_namespace n ON n.oid = c.relnamespace" in bind.last_query
    assert "c.relkind = 'i'" in bind.last_query
    assert bind.last_params == {
        "schema": "processing_core",
        "index_name": "ix_dispute_events_dispute_id_created_at",
    }
    assert bind.create_called is False


def test_create_index_if_not_exists_ignores_duplicate_table_race():
    bind = _Bind()
    bind.raise_on_create = psycopg_errors.DuplicateTable("already exists")

    helpers.create_index_if_not_exists(
        bind,
        "ix_dispute_events_dispute_id_created_at",
        "dispute_events",
        ["dispute_id", "created_at"],
        schema="processing_core",
    )


def test_create_index_if_not_exists_ignores_duplicate_object_programming_error():
    bind = _Bind()

    class _OrigError(Exception):
        sqlstate = "42710"

    bind.raise_on_create = ProgrammingError("CREATE INDEX", {}, _OrigError("duplicate object"))

    helpers.create_index_if_not_exists(
        bind,
        "ix_dispute_events_dispute_id_created_at",
        "dispute_events",
        ["dispute_id", "created_at"],
        schema="processing_core",
    )


def test_create_index_if_not_exists_reraises_non_duplicate_errors():
    bind = _Bind()
    bind.raise_on_create = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        helpers.create_index_if_not_exists(
            bind,
            "ix_dispute_events_dispute_id_created_at",
            "dispute_events",
            ["dispute_id", "created_at"],
            schema="processing_core",
        )
