"""Utility to verify alembic head matches database state."""
from __future__ import annotations

import sys
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext


def main() -> int:
    cfg = Config("platform/processing-core/app/alembic.ini")
    script = ScriptDirectory.from_config(cfg)

    def check_revision(rev: str, context) -> str:  # type: ignore[override]
        head_revision = script.get_current_head()
        if rev != head_revision:
            raise SystemExit(f"Database revision {rev} does not match head {head_revision}")
        return rev

    with EnvironmentContext(cfg, script, fn=check_revision):
        script.run_env()
    print("Migration state is clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
