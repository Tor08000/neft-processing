from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def load_protected_revisions(path: Path) -> list[str]:
    revisions: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        revisions.append(stripped)
    return revisions


def main() -> int:
    protected_path = Path(__file__).with_name("protected_revisions.txt")
    if not protected_path.exists():
        print(f"Protected revisions list not found: {protected_path}")
        return 1

    protected_revisions = load_protected_revisions(protected_path)
    if not protected_revisions:
        print("Protected revisions list is empty.")
        return 1

    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(alembic_ini))
    script = ScriptDirectory.from_config(cfg)
    available_revisions = {rev.revision for rev in script.walk_revisions() if rev.revision}

    missing = [rev for rev in protected_revisions if rev not in available_revisions]
    if missing:
        print("Missing alembic revisions that were already on main:")
        for rev in missing:
            print(f"- {rev}")
        return 1

    print("Alembic history contains all protected revisions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
