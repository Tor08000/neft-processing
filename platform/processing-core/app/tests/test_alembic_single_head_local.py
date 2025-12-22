from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_single_head_local(monkeypatch):
    """Ensure we keep a single alembic head in-tree without requiring docker."""

    repo_root = Path(__file__).resolve().parents[4]
    app_root = repo_root / "platform" / "processing-core" / "app"
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite:///dummy.db"))

    sys.path.extend(
        [
            str(app_root),
            str(repo_root / "platform" / "processing-core"),
            str(repo_root / "shared" / "python"),
        ]
    )

    cfg = Config(str(app_root / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()

    assert len(heads) == 1, f"Expected exactly one alembic head, got {len(heads)}: {heads}"
