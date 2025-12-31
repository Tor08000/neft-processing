from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


@pytest.mark.parametrize("path", sorted(MIGRATIONS_DIR.glob("*.py")))
def test_migrations_do_not_reference_public_fuel_tables(path: Path) -> None:
    contents = path.read_text(encoding="utf-8")
    assert "public.fuel_" not in contents, f"{path.name} references public.fuel_ tables"


@pytest.mark.parametrize("path", sorted(MIGRATIONS_DIR.glob("*fuel*.py")))
def test_fuel_migrations_do_not_force_public_schema(path: Path) -> None:
    contents = path.read_text(encoding="utf-8")
    forbidden = ("schema=\"public\"", "schema='public'", "SCHEMA = \"public\"", "SCHEMA = 'public'")
    matches = [token for token in forbidden if token in contents]
    assert not matches, f"{path.name} forces public schema via {matches}"
