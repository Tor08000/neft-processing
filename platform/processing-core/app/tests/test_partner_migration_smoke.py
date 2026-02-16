from __future__ import annotations

from pathlib import Path


def test_partner_migration_declares_required_tables() -> None:
    migration = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20299820_0185_partner_management_v1.py"
    text = migration.read_text(encoding="utf-8")
    assert "partner_locations" in text
    assert "partner_user_roles" in text
    assert "partner_terms" in text
    assert "code" in text
