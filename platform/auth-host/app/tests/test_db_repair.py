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
