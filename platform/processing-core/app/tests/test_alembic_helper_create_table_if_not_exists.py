from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.alembic import helpers


def test_create_table_if_not_exists_spreads_keyword_columns(monkeypatch: pytest.MonkeyPatch):
    created_tables: list[tuple[str, tuple, dict]] = []
    created_indexes: list[tuple[str, tuple[str, ...], str | None]] = []

    engine = sa.create_engine("sqlite://")
    with engine.connect() as bind:
        monkeypatch.setattr(
            bind,
            "op_override",
            SimpleNamespace(create_table=lambda name, *cols, **kwargs: created_tables.append((name, cols, kwargs))),
            raising=False,
        )
        monkeypatch.setattr(helpers, "table_exists", lambda *_args, **_kwargs: False)
        monkeypatch.setattr(
            helpers,
            "create_index_if_not_exists",
            lambda conn, index_name, table_name, columns, schema=None: created_indexes.append(
                (index_name, tuple(columns), schema)
            ),
        )

        helpers.create_table_if_not_exists(
            bind,
            "sample_table",
            schema="billing",
            columns=[sa.Column("id", sa.Integer())],
            indexes=[("ix_sample_table_id", ["id"])],
        )

    assert created_tables, "Table creation should be invoked"
    table_name, cols, kwargs = created_tables[0]
    assert table_name == "sample_table"
    assert [col.name for col in cols] == ["id"]
    assert "columns" not in kwargs
    assert kwargs["schema"] is None

    assert created_indexes == [("ix_sample_table_id", ("id",), None)]


def test_create_table_if_not_exists_skips_indexes_when_table_exists(monkeypatch: pytest.MonkeyPatch):
    created_tables: list[tuple[str, tuple, dict]] = []
    created_indexes: list[tuple[str, tuple[str, ...], str | None]] = []

    engine = sa.create_engine("sqlite://")
    with engine.connect() as bind:
        monkeypatch.setattr(
            bind,
            "op_override",
            SimpleNamespace(create_table=lambda name, *cols, **kwargs: created_tables.append((name, cols, kwargs))),
            raising=False,
        )
        monkeypatch.setattr(helpers, "table_exists", lambda *_args, **_kwargs: True)
        monkeypatch.setattr(
            helpers,
            "create_index_if_not_exists",
            lambda conn, index_name, table_name, columns, schema=None: created_indexes.append(
                (index_name, tuple(columns), schema)
            ),
        )

        helpers.create_table_if_not_exists(
            bind,
            "sample_table",
            schema="billing",
            columns=[sa.Column("id", sa.Integer())],
            indexes=[("ix_sample_table_id", ["id"]), ("ix_sample_table_other", ["id", "name"])],
        )

    assert not created_tables
    assert not created_indexes
