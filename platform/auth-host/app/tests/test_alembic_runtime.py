from __future__ import annotations

from app.alembic_runtime import should_reset_for_broken_revision


def test_should_reset_for_broken_revision_with_explicit_reset(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_DB_RECOVERY", "reset")
    assert should_reset_for_broken_revision(db_revision="20260216_01", revision_known=False)


def test_should_reset_for_broken_revision_with_auto_repair(monkeypatch) -> None:
    monkeypatch.delenv("AUTH_DB_RECOVERY", raising=False)
    monkeypatch.setenv("AUTH_ALEMBIC_AUTO_REPAIR", "1")
    assert should_reset_for_broken_revision(db_revision="20260216_01", revision_known=False)


def test_should_not_reset_for_known_revision(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_DB_RECOVERY", "reset")
    assert not should_reset_for_broken_revision(db_revision="20260221_0001_users_schema_guard", revision_known=True)
