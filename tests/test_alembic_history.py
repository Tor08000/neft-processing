from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_alembic_history_contains_known_revisions() -> None:
    try:
        import alembic  # noqa: F401
    except ModuleNotFoundError:
        pytest.skip("alembic not installed")

    result = subprocess.run(
        [sys.executable, "scripts/check_alembic_history.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(
            "Alembic history check failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
