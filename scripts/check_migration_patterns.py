from __future__ import annotations

import re
import sys
from pathlib import Path


def find_migration_dirs(repo_root: Path) -> list[Path]:
    return [path for path in repo_root.rglob("alembic/versions") if path.is_dir()]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    migration_dirs = find_migration_dirs(repo_root)

    if not migration_dirs:
        print("No migration directories found.")
        return 0

    pattern_public = re.compile(r"CREATE\s+(UNIQUE\s+)?INDEX\s+public\.", re.IGNORECASE)
    pattern_index = re.compile(r"CREATE\s+(UNIQUE\s+)?INDEX", re.IGNORECASE)

    violations: list[str] = []

    for migration_dir in migration_dirs:
        for path in migration_dir.rglob("*.py"):
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="utf-8", errors="replace")

            for line_number, line in enumerate(content.splitlines(), start=1):
                if pattern_public.search(line) or pattern_index.search(line):
                    violations.append(f"{path}:{line_number}: {line.strip()}")

    if violations:
        print("Found disallowed CREATE INDEX statements in migrations:")
        for violation in violations:
            print(violation)
        return 1

    print("No disallowed CREATE INDEX statements found in migrations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
