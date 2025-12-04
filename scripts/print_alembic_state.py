"""Print current alembic heads and database revision."""
from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext


def main() -> None:
    cfg = Config("platform/processing-core/app/alembic.ini")
    script = ScriptDirectory.from_config(cfg)

    def display(rev, context):  # type: ignore[override]
        print(f"DB revision: {rev}")
        print(f"Head revision: {script.get_current_head()}")
        return rev

    with EnvironmentContext(cfg, script, fn=display):
        script.run_env()


if __name__ == "__main__":
    main()
