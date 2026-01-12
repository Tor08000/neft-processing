from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

MIGRATIONS_DIR = BASE_DIR / "app" / "alembic" / "versions"
MIGRATION_FILES = [path for path in sorted(MIGRATIONS_DIR.glob("*.py")) if path.name != "__init__.py"]


def _load_module(path: Path) -> None:
    module_name = f"alembic_revision_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


@pytest.mark.parametrize("path", MIGRATION_FILES)
def test_alembic_migrations_import_cleanly(path: Path) -> None:
    try:
        _load_module(path)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"{path.name} raised ModuleNotFoundError: {exc}") from exc


@pytest.mark.parametrize("path", MIGRATION_FILES)
def test_alembic_migrations_do_not_import_app_package(path: Path) -> None:
    contents = path.read_text(encoding="utf-8")
    assert "from app." not in contents, f"{path.name} contains forbidden 'from app.' import"
    assert "import app." not in contents, f"{path.name} contains forbidden 'import app.' import"
