from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def load_known_revisions(path: Path) -> list[str]:
    revisions: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        revisions.append(stripped)
    return revisions


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    known_path = repo_root / "platform" / "processing-core" / "app" / "alembic" / "protected_revisions.txt"
    if not known_path.exists():
        print(f"Known revisions list not found: {known_path}")
        return 1

    known_revisions = load_known_revisions(known_path)
    if not known_revisions:
        print("Known revisions list is empty.")
        return 1

    cfg = Config("platform/processing-core/app/alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    available_revisions = {rev.revision for rev in script.walk_revisions() if rev.revision}

    missing = [rev for rev in known_revisions if rev not in available_revisions]
    if missing:
        print("Missing alembic revisions that were already on main:")
        for rev in missing:
            print(f"- {rev}")
        return 1

    print("Alembic history contains all known revisions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
