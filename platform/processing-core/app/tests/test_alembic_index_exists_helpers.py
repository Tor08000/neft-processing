from __future__ import annotations

import re
from pathlib import Path


def test_index_exists_does_not_use_table_name_kwarg():
    versions_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    assert versions_dir.is_dir(), f"versions directory missing at {versions_dir}"

    pattern = re.compile(r"index_exists\s*\([^)]*table_name\s*=", re.MULTILINE | re.DOTALL)
    offenders: list[str] = []

    for path in versions_dir.glob("*.py"):
        if pattern.search(path.read_text()):
            offenders.append(path.name)

    assert not offenders, f"index_exists called with table_name kwarg in: {', '.join(offenders)}"


def test_constraint_exists_does_not_use_table_name_kwarg():
    versions_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    assert versions_dir.is_dir(), f"versions directory missing at {versions_dir}"

    pattern = re.compile(r"constraint_exists\s*\([^)]*table_name\s*=", re.MULTILINE | re.DOTALL)
    offenders: list[str] = []

    for path in versions_dir.glob("*.py"):
        if pattern.search(path.read_text()):
            offenders.append(path.name)

    assert not offenders, f"constraint_exists called with table_name kwarg in: {', '.join(offenders)}"
