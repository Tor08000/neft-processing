from __future__ import annotations

import pytest

from app.scripts import db_repair


class _Script:
    def get_heads(self):
        return ("20260221_0001_users_schema_guard",)


def test_db_repair_unknown_revision_fails_without_reset(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("AUTH_DB_RECOVERY", raising=False)
    monkeypatch.delenv("DEV_DB_RECOVERY", raising=False)
    monkeypatch.delenv("AUTH_ALEMBIC_AUTO_REPAIR", raising=False)

    monkeypatch.setattr(db_repair, "make_alembic_config", lambda: object())
    monkeypatch.setattr(db_repair, "get_script_directory", lambda _cfg: _Script())
    monkeypatch.setattr(db_repair, "fetch_db_revision", lambda _dsn: "20260216_01")
    monkeypatch.setattr(db_repair, "is_db_revision_known", lambda _script, _rev: False)

    with pytest.raises(RuntimeError, match="unknown to this build"):
        db_repair.run()


def test_db_repair_unknown_revision_reset_restricted_to_dev(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_DB_RECOVERY", "reset")

    monkeypatch.setattr(db_repair, "make_alembic_config", lambda: object())
    monkeypatch.setattr(db_repair, "get_script_directory", lambda _cfg: _Script())
    monkeypatch.setattr(db_repair, "fetch_db_revision", lambda _dsn: "20260216_01")
    monkeypatch.setattr(db_repair, "is_db_revision_known", lambda _script, _rev: False)

    with pytest.raises(RuntimeError, match="outside dev mode"):
        db_repair.run()


class _Cursor:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql):
        self.calls.append(sql)


class _Connection:
    def __init__(self, calls):
        self.calls = calls
        self.autocommit = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _Cursor(self.calls)


def test_db_repair_ensures_public_alembic_version_before_upgrade(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")

    executed_sql = []
    events = []

    monkeypatch.setattr(db_repair, "make_alembic_config", lambda: object())
    monkeypatch.setattr(db_repair, "get_script_directory", lambda _cfg: _Script())

    revisions = iter((None, "20260221_0001_users_schema_guard"))
    monkeypatch.setattr(db_repair, "fetch_db_revision", lambda _dsn: next(revisions))
    monkeypatch.setattr(db_repair, "is_db_revision_known", lambda _script, _rev: True)

    def _connect(_dsn):
        events.append("connect")
        return _Connection(executed_sql)

    monkeypatch.setattr(db_repair.psycopg, "connect", _connect)

    def _upgrade(_cfg, _rev):
        events.append("upgrade")

    monkeypatch.setattr(db_repair.command, "upgrade", _upgrade)

    db_repair.run()

    assert events == ["connect", "upgrade"]
    assert executed_sql == [
        "CREATE TABLE IF NOT EXISTS public.alembic_version (version_num TEXT NOT NULL)",
        "ALTER TABLE public.alembic_version ALTER COLUMN version_num TYPE TEXT",
    ]
